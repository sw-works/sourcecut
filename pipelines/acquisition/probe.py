"""Test a registry entry's rights claim before anything is acquired from it.

A ``source_repositories`` row is a claim: *this field carries the rights
determination, and these exact values mean the item is clearable*. Adding the
row does not make the claim true. The probe samples real items, prints the raw
value of the declared field for each, and reports how often it matched.

The failure this catches is quiet and expensive: a field that is absent on most
items reads as "nothing is eligible" during discovery, and a field whose values
drifted reads as "everything is ineligible" — either way you find out after
staging hundreds of documents rather than before fetching one.

The probe never decides rights and never writes a candidate. It reports.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from sourcecut_api.db.load_repositories import (
    DEFAULT_LICENSE_PATH,
    DEFAULT_REPOSITORY_PATH,
    load_registry,
)

USER_AGENT = "SourceCut/1.0 (corpus acquisition probe)"
DEFAULT_SAMPLE = 20
#: Below this, the declared field is not reliably present and the entry is wrong.
BASELINE_PRESENCE = 0.8

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
        # A repository nothing matches is still usable — it may simply hold
        # little public-domain material. A repository whose declared field is
        # mostly absent is a broken entry.
        return self.sample_size > 0 and self.presence_rate >= BASELINE_PRESENCE


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


def evaluate(
    repository_id: str,
    items: Sequence[Any],
    *,
    rights_field: str,
    eligible_values: Sequence[str],
) -> ProbeResult:
    eligible = set(eligible_values)
    observed: list[str] = []
    present = 0
    matched = 0
    for item in items:
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
    url = f"{base_url.rstrip('/')}/books?{urlencode({'search': query})}"
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


def loc_items(base_url: str, query: str, limit: int, fetch: Fetch) -> list[Any]:
    parameters = urlencode({"q": query, "fo": "json", "c": str(limit)})
    payload = json.loads(fetch(f"{base_url.rstrip('/')}/search/?{parameters}"))
    # The registry declares "item.rights_advisory", so each result is wrapped to
    # match the shape a single item response has.
    return [{"item": result} for result in payload.get("results", [])][:limit]


ADAPTERS: dict[str, Callable[[str, str, int, Fetch], list[Any]]] = {
    "gutendex": gutendex_items,
    "internet_archive": internet_archive_items,
    "loc_json": loc_items,
}


def http_fetch(url: str, *, timeout_seconds: float = 30) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - https only
        return response.read()


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
            f"  REJECTED: the declared field must be present on at least "
            f"{BASELINE_PRESENCE:.0%} of items"
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
