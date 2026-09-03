"""Test a registry entry's rights claim before anything is acquired from it.

A ``source_repositories`` row is a claim: *this field carries the rights
determination, and these exact values mean the item is clearable*. Adding the
row does not make the claim true. The probe samples real items, prints the raw
value of the declared field for each, and reports how often it matched.

The failure this catches is quiet and expensive: a field named wrongly, or one
whose values drifted, reads as "nothing is eligible" during discovery, and the
reason is about the registry rather than about any item. Both were real on the
first probe — the Internet Archive entry named `metadata.rights`, which exists
on no item, and the Library of Congress entry named a field loc.gov does not
serve for text at all.

Presence is reported, not enforced beyond zero: several repositories record a
determination only on items a librarian reviewed, so a low presence rate is low
yield rather than a broken entry, and for Internet Archive it moves with the
query scope (8% on a loose title search, 92% scoped to a scanning partner's
pre-1860 texts).

The probe never decides rights and never writes a candidate. It reports.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from http.client import IncompleteRead
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from sourcecut_api.db.load_repositories import (
    DEFAULT_LICENSE_PATH,
    DEFAULT_REPOSITORY_PATH,
    load_registry,
)

USER_AGENT = "SourceCut/1.0 (corpus acquisition probe)"
DEFAULT_SAMPLE = 20
#: Below this the entry is reported as thin, but not rejected: some repositories
#: populate a rights field only on items a librarian reviewed, and absence there
#: is a correct "unknown status", not a broken entry. See `ProbeResult.usable`.
BASELINE_PRESENCE = 0.8

#: How the declared path is compared with `eligible_values`. Both are exact
#: string matches; they differ in what the path resolves to.
MATCH_VALUE = "value"      # the path holds the determination and nothing else
MATCH_ANY_OF = "any_of"    # the path holds many labels, one of which may be it

Fetch = Callable[[str], bytes]


@dataclass(frozen=True, slots=True)
class ProbeResult:
    repository_id: str
    sample_size: int
    present: int
    matched: int
    observed_values: tuple[str, ...]

    @property
    def presence_rate(self) -> float:
        return self.present / self.sample_size if self.sample_size else 0.0

    @property
    def match_rate(self) -> float:
        return self.matched / self.sample_size if self.sample_size else 0.0

    @property
    def usable(self) -> bool:
        """Whether the sample gives any evidence the declared field is real.

        Rejection is reserved for a field that never appeared: there is then no
        evidence the path exists, and every candidate would read as ineligible
        for a reason that is about the registry rather than about the item.

        Anything above zero passes. A field present on only some items is how
        several repositories work — Internet Archive records
        `possible-copyright-status` on items a librarian reviewed and omits it
        elsewhere — and absence there is a correct "status unknown", which the
        acquisition path already treats as ineligible.
        """
        return self.sample_size > 0 and self.present > 0

    @property
    def thin(self) -> bool:
        """Present, but on few enough items to be worth reporting."""
        return self.usable and self.presence_rate < BASELINE_PRESENCE


def read_rights_field(item: Any, path: str) -> str | None:
    """Read a dotted path out of one item, or ``None`` when it is not there.

    Values are stringified rather than coerced: a repository reporting a boolean
    ``copyright`` and one reporting the string ``"Public Domain"`` are compared
    the same way, against the exact strings the registry lists.
    """
    current = item
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return None
        current = current[segment]
    if current is None:
        return None
    if isinstance(current, bool):
        return "true" if current else "false"
    if isinstance(current, list):
        # Some repositories repeat the field; a list is only readable when it
        # holds exactly one determination.
        if len(current) != 1:
            return None
        current = current[0]
    if isinstance(current, dict):
        return None
    return str(current)


def read_rights_labels(item: Any, path: str) -> tuple[str, ...]:
    """Read every scalar the dotted path resolves to, for ``any_of`` matching.

    Some repositories carry the determination as one of many labels rather than
    as a dedicated field: a Wikisource work declares it by belonging to
    ``Category:PD-old``, alongside a dozen unrelated maintenance categories. The
    match is still exact-string; what changes is that it is set membership.
    """
    current = item
    for segment in path.split("."):
        if isinstance(current, list):
            collected: list[str] = []
            for element in current:
                collected.extend(read_rights_labels(element, segment))
            return tuple(collected)
        if not isinstance(current, dict) or segment not in current:
            return ()
        current = current[segment]
    if isinstance(current, list):
        return tuple(str(value) for value in current if _is_scalar(value))
    return (str(current),) if _is_scalar(current) else ()


def _is_scalar(value: Any) -> bool:
    return isinstance(value, str | int | float) and not isinstance(value, bool)


def evaluate(
    repository_id: str,
    items: Sequence[Any],
    *,
    rights_field: str,
    eligible_values: Sequence[str],
    rights_match: str = MATCH_VALUE,
) -> ProbeResult:
    eligible = set(eligible_values)
    observed: list[str] = []
    present = 0
    matched = 0
    for item in items:
        if rights_match == MATCH_ANY_OF:
            labels = read_rights_labels(item, rights_field)
            if not labels:
                continue
            present += 1
            # Only the matching labels are recorded: the path deliberately holds
            # unrelated values here, so listing them all would bury the signal.
            # Drift still shows, as presence high with matches at zero.
            observed.extend(label for label in labels if label in eligible)
            if eligible & set(labels):
                matched += 1
            continue
        value = read_rights_field(item, rights_field)
        if value is None:
            continue
        present += 1
        observed.append(value)
        if value in eligible:
            matched += 1
    return ProbeResult(
        repository_id=repository_id,
        sample_size=len(items),
        present=present,
        matched=matched,
        observed_values=tuple(sorted(set(observed))),
    )


# -- adapters ---------------------------------------------------------------
# One per repository shape. Each returns a list of raw item dicts exactly as the
# repository sent them; nothing is normalized, because what is under test is the
# repository's own vocabulary.


def gutendex_items(base_url: str, query: str, limit: int, fetch: Fetch) -> list[Any]:
    url = f"{base_url.rstrip('/')}/books/?{urlencode({'search': query})}"
    payload = json.loads(fetch(url))
    return list(payload.get("results", []))[:limit]


def internet_archive_items(base_url: str, query: str, limit: int, fetch: Fetch) -> list[Any]:
    parameters = urlencode(
        {
            "q": query,
            "fl[]": "identifier",
            "rows": str(limit),
            "output": "json",
        }
    )
    search = json.loads(fetch(f"{base_url.rstrip('/')}/advancedsearch.php?{parameters}"))
    identifiers = [
        str(doc["identifier"])
        for doc in search.get("response", {}).get("docs", [])
        if doc.get("identifier")
    ]
    # Rights live on the item, not in the search result, so the probe reads the
    # same endpoint acquisition would.
    return [
        json.loads(fetch(f"{base_url.rstrip('/')}/metadata/{quote(identifier)}"))
        for identifier in identifiers[:limit]
    ]


# Library of Congress has no adapter on purpose. Probing it on 2026-09-03 found
# no determination field on loc.gov text items: the search result carries
# `access_advisory` ("Open to research.", an access statement, not a rights one)
# and the item endpoint carries `item.rights`, a per-collection HTML paragraph.
# Prose cannot be matched with exact values, and matching it on phrases is the
# judgement call ADR-024 keeps out of acquisition. LoC media harvesting is
# unaffected: `pipelines/media/loc.py` classifies rights text for assets that are
# displayed with that text beside them, which is a different bargain.
def wikisource_items(base_url: str, query: str, limit: int, fetch: Fetch) -> list[Any]:
    """Root works only, with their categories.

    Wikisource records the licence on the work, not on its chapters, and search
    returns chapters. Probing what search returns unfiltered reports 0% presence
    on a repository whose root works declare a licence every time, so the filter
    is part of reading this repository correctly rather than a convenience.
    """
    parameters = urlencode(
        {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": "0",
            "gsrlimit": str(min(limit * 4, 200)),
            "prop": "categories",
            "cllimit": "500",
        }
    )
    payload = json.loads(fetch(f"{base_url.rstrip('/')}/w/api.php?{parameters}"))
    pages = payload.get("query", {}).get("pages", {}).values()
    roots = [page for page in pages if "/" not in str(page.get("title", "/"))]
    return roots[:limit]


ADAPTERS: dict[str, Callable[[str, str, int, Fetch], list[Any]]] = {
    "gutendex": gutendex_items,
    "internet_archive": internet_archive_items,
    "wikisource": wikisource_items,
}


def http_fetch(
    url: str, *, timeout_seconds: float = 30, attempts: int = 3, pause_seconds: float = 2.0
) -> bytes:
    """Fetch one JSON document, retrying the transient failures these APIs give.

    Archive APIs drop reads and return 503 often enough that a single attempt
    reports a network hiccup as a repository verdict. Retries cover only that;
    a 4xx is the repository answering and is raised immediately.
    """
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - https
                return response.read()
        except HTTPError as error:
            if error.code < 500:
                raise
            last = error
        except (URLError, TimeoutError, IncompleteRead, ConnectionError) as error:
            last = error
        if attempt + 1 < attempts:
            time.sleep(pause_seconds * (attempt + 1))
    raise RuntimeError(f"{url} failed after {attempts} attempts: {last}") from last


def probe(
    entry: dict[str, Any],
    *,
    query: str,
    limit: int = DEFAULT_SAMPLE,
    fetch: Fetch | None = None,
) -> ProbeResult:
    adapter = ADAPTERS.get(str(entry["adapter"]))
    if adapter is None:
        raise ValueError(f"No adapter named {entry['adapter']!r}")
    items = adapter(str(entry["base_url"]), query, limit, fetch or http_fetch)
    return evaluate(
        str(entry["repository_id"]),
        items,
        rights_field=str(entry["rights_field"]),
        eligible_values=list(entry["eligible_values"]),
        rights_match=str(entry.get("rights_match", MATCH_VALUE)),
    )


def render(result: ProbeResult, *, rights_field: str) -> str:
    lines = [
        f"{result.repository_id}: sampled {result.sample_size} item(s)",
        f"  {rights_field} present on {result.present} ({result.presence_rate:.0%})",
        f"  eligible on {result.matched} ({result.match_rate:.0%})",
    ]
    if result.observed_values:
        lines.append("  observed values:")
        lines.extend(f"    {value!r}" for value in result.observed_values)
    else:
        lines.append("  observed values: none — the declared field was never present")
    if not result.usable:
        lines.append(
            "  REJECTED: the declared field never appeared, so this sample is no evidence "
            "that it exists. Check the field name against a real item."
        )
    elif result.thin:
        lines.append(
            f"  THIN: present on under {BASELINE_PRESENCE:.0%} of items. Acquisition will treat "
            "the rest as status unknown and refuse them, which is correct but low yield."
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sample a registered repository and report what its rights field says"
    )
    parser.add_argument("repository_id")
    parser.add_argument(
        "--query",
        default="journal",
        help="Search term used only to obtain a sample of items",
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_SAMPLE)
    parser.add_argument("--licenses", type=Path, default=DEFAULT_LICENSE_PATH)
    parser.add_argument("--repositories", type=Path, default=DEFAULT_REPOSITORY_PATH)
    parser.add_argument(
        "--record",
        action="store_true",
        help="Write the result back onto the source_repositories row",
    )
    args = parser.parse_args()

    registry = load_registry(args.licenses, args.repositories)
    entry = next(
        (
            item
            for item in registry.repositories
            if item["repository_id"] == args.repository_id
        ),
        None,
    )
    if entry is None:
        raise SystemExit(f"{args.repository_id} is not in {args.repositories}")

    result = probe(entry, query=args.query, limit=args.limit)
    print(render(result, rights_field=str(entry["rights_field"])))
    if args.record:
        _record(entry, result)
    raise SystemExit(0 if result.usable else 1)


def _record(entry: dict[str, Any], result: ProbeResult) -> None:
    from sourcecut_api.db.client import get_clickhouse_client
    from sourcecut_api.db.load_repositories import REPOSITORY_COLUMNS, repository_rows

    now = datetime.now(UTC)
    row = repository_rows([entry], now)[0]
    row[REPOSITORY_COLUMNS.index("probed_at")] = now
    row[REPOSITORY_COLUMNS.index("probe_sample_size")] = result.sample_size
    row[REPOSITORY_COLUMNS.index("probe_match_rate")] = result.match_rate
    client = get_clickhouse_client()
    try:
        client.insert(
            "source_repositories",
            [row],
            column_names=REPOSITORY_COLUMNS,
            settings={"async_insert": 1, "wait_for_async_insert": 1},
        )
    finally:
        client.close()
    print(f"Recorded the probe on {result.repository_id}.")
