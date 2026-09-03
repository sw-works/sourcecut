"""Load the acquisition registry: which repositories may be acquired from.

The registry is committed reference data (ADR-017) rather than a form, so the
human approval ADR-024 requires *is* the pull request that adds the row. Two
files, because they answer different questions:

- ``licenses.json`` — what a rights status permits.
- ``source_repositories.json`` — where a repository lives, and which field of
  its own metadata carries a rights determination.

A repository maps its vocabulary onto a license; collapsing the two would let
"we may redistribute CC0" stand in for "this item is CC0", which is the exact
substitution ADR-024 exists to prevent.

Validation runs before any write. An entry that cannot say which field carries
rights, or that tries to match on a pattern instead of exact values, is refused
here rather than discovered during a fetch.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sourcecut_api.db.client import get_clickhouse_client
from sourcecut_api.db.migrations import bootstrap_database

DEFAULT_LICENSE_PATH = Path("data/reference/licenses.json")
DEFAULT_REPOSITORY_PATH = Path("data/reference/source_repositories.json")

LICENSE_COLUMNS = [
    "license_id",
    "spdx_or_rights_code",
    "display_name",
    "canonical_url",
    "attribution_template",
    "share_alike",
    "commercial_use_allowed",
    "derivatives_allowed",
    "bulk_export_allowed",
    "notes",
    "reviewed_by",
    "reviewed_at",
    "updated_at",
]
REPOSITORY_COLUMNS = [
    "repository_id",
    "display_name",
    "base_url",
    "adapter",
    "rights_field",
    "rights_match",
    "eligible_values",
    "default_license_id",
    "rate_limit_per_minute",
    "terms_note",
    "notes",
    "reviewed_by",
    "reviewed_at",
    "probed_at",
    "probe_sample_size",
    "probe_match_rate",
    "updated_at",
]

REQUIRED_LICENSE_FIELDS = ("license_id", "spdx_or_rights_code", "display_name", "reviewed_by")
REQUIRED_REPOSITORY_FIELDS = (
    "repository_id",
    "display_name",
    "base_url",
    "adapter",
    "rights_field",
    "eligible_values",
    "default_license_id",
    "reviewed_by",
)
# A rights value is compared with ==, so anything that reads like a pattern is a
# sign the author expected matching rules the acquisition path does not have.
PATTERN_CHARACTERS = frozenset("*?[]()|^$\\")
#: How `rights_field` is compared with `eligible_values`. Both are exact string
#: matches and differ only in what the path resolves to: "value" for a field
#: holding the determination alone, "any_of" for one holding many labels of
#: which one may be the determination (a Wikisource work's categories).
RIGHTS_MATCHES = frozenset({"value", "any_of"})


class RegistryError(ValueError):
    """A registry file that must not reach ClickHouse."""


@dataclass(frozen=True, slots=True)
class Registry:
    licenses: tuple[dict[str, Any], ...]
    repositories: tuple[dict[str, Any], ...]


def load_registry(
    license_path: Path = DEFAULT_LICENSE_PATH,
    repository_path: Path = DEFAULT_REPOSITORY_PATH,
    *,
    known_license_ids: Iterable[str] = (),
) -> Registry:
    licenses = _read(license_path)
    repositories = _read(repository_path)
    validate_licenses(licenses)
    validate_repositories(
        repositories,
        license_ids={str(item["license_id"]) for item in licenses} | set(known_license_ids),
    )
    return Registry(tuple(licenses), tuple(repositories))


def validate_licenses(licenses: Sequence[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for item in licenses:
        _require(item, REQUIRED_LICENSE_FIELDS, "license")
        license_id = str(item["license_id"])
        if license_id in seen:
            raise RegistryError(f"Duplicate license_id: {license_id}")
        seen.add(license_id)
        _require_review(item, f"license {license_id}")


def validate_repositories(
    repositories: Sequence[dict[str, Any]], *, license_ids: set[str]
) -> None:
    seen: set[str] = set()
    for item in repositories:
        _require(item, REQUIRED_REPOSITORY_FIELDS, "repository")
        repository_id = str(item["repository_id"])
        if repository_id in seen:
            raise RegistryError(f"Duplicate repository_id: {repository_id}")
        seen.add(repository_id)
        _require_review(item, f"repository {repository_id}")

        if not str(item["rights_field"]).strip():
            # No field means stage 3 has nothing deterministic to read, and the
            # only way left to decide rights would be judgement (ADR-024).
            raise RegistryError(
                f"{repository_id} has an empty rights_field: a repository with no declared "
                "rights field cannot be acquired from"
            )
        values = item["eligible_values"]
        if not isinstance(values, list) or not values:
            raise RegistryError(f"{repository_id} must list at least one eligible rights value")
        for value in values:
            if not isinstance(value, str) or not value.strip():
                raise RegistryError(f"{repository_id} has an empty eligible rights value")
            if PATTERN_CHARACTERS & set(value):
                raise RegistryError(
                    f"{repository_id} eligible value {value!r} looks like a pattern; "
                    "eligibility is an exact string match"
                )
        if len(set(values)) != len(values):
            raise RegistryError(f"{repository_id} repeats an eligible rights value")

        match = str(item.get("rights_match", "value"))
        if match not in RIGHTS_MATCHES:
            raise RegistryError(
                f"{repository_id} has rights_match {match!r}; expected one of "
                f"{', '.join(sorted(RIGHTS_MATCHES))}"
            )
        base_url = str(item["base_url"])
        if not base_url.startswith("https://"):
            raise RegistryError(f"{repository_id} base_url must be https")
        license_id = str(item["default_license_id"])
        if license_id not in license_ids:
            raise RegistryError(
                f"{repository_id} names default_license_id {license_id!r}, which is in neither "
                "licenses.json nor the licenses table"
            )


def _require(item: dict[str, Any], fields: Sequence[str], kind: str) -> None:
    missing = [field for field in fields if not item.get(field)]
    if missing:
        raise RegistryError(f"A {kind} entry is missing {', '.join(missing)}")


def _require_review(item: dict[str, Any], label: str) -> None:
    """Both gates in ADR-024 are recorded, not implied."""
    if not str(item.get("reviewed_by", "")).strip():
        raise RegistryError(f"{label} has no reviewed_by")
    _parse_timestamp(item, label)


def _parse_timestamp(item: dict[str, Any], label: str) -> datetime:
    raw = str(item.get("reviewed_at", "")).strip()
    if not raw:
        raise RegistryError(f"{label} has no reviewed_at")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise RegistryError(f"{label} has an unparsable reviewed_at: {raw}") from error
    return parsed.astimezone(UTC)


def _read(path: Path) -> list[dict[str, Any]]:
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise RegistryError(f"{path} must hold a list of objects")
    return records


def license_rows(licenses: Sequence[dict[str, Any]], now: datetime) -> list[list[Any]]:
    return [
        [
            item["license_id"],
            item["spdx_or_rights_code"],
            item["display_name"],
            item.get("canonical_url", ""),
            item.get("attribution_template", ""),
            bool(item.get("share_alike", False)),
            int(item.get("commercial_use_allowed", -1)),
            int(item.get("derivatives_allowed", -1)),
            int(item.get("bulk_export_allowed", -1)),
            item.get("notes", ""),
            item["reviewed_by"],
            _parse_timestamp(item, str(item["license_id"])),
            now,
        ]
        for item in licenses
    ]


def repository_rows(
    repositories: Sequence[dict[str, Any]], now: datetime
) -> list[list[Any]]:
    return [
        [
            item["repository_id"],
            item["display_name"],
            item["base_url"],
            item["adapter"],
            item["rights_field"],
            item.get("rights_match", "value"),
            list(item["eligible_values"]),
            item["default_license_id"],
            int(item.get("rate_limit_per_minute", 30)),
            item.get("terms_note", ""),
            item.get("notes", ""),
            item["reviewed_by"],
            _parse_timestamp(item, str(item["repository_id"])),
            # A probe is a separate run against the live repository, so loading
            # the registry never claims one happened.
            None,
            0,
            0.0,
            now,
        ]
        for item in repositories
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load the licenses and source repositories acquisition may use"
    )
    parser.add_argument("--licenses", type=Path, default=DEFAULT_LICENSE_PATH)
    parser.add_argument("--repositories", type=Path, default=DEFAULT_REPOSITORY_PATH)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate the registry files and write nothing",
    )
    args = parser.parse_args()

    if args.check:
        registry = load_registry(args.licenses, args.repositories)
        print(
            f"Registry is valid: {len(registry.licenses)} license(s), "
            f"{len(registry.repositories)} repository/repositories."
        )
        return

    client = get_clickhouse_client()
    try:
        bootstrap_database(client)
        stored = {
            str(row[0])
            for row in client.query("SELECT license_id FROM licenses FINAL").result_rows
        }
        registry = load_registry(args.licenses, args.repositories, known_license_ids=stored)
        now = datetime.now(UTC)
        settings = {"async_insert": 1, "wait_for_async_insert": 1}
        client.insert(
            "licenses",
            license_rows(registry.licenses, now),
            column_names=LICENSE_COLUMNS,
            settings=settings,
        )
        client.insert(
            "source_repositories",
            repository_rows(registry.repositories, now),
            column_names=REPOSITORY_COLUMNS,
            settings=settings,
        )
    finally:
        client.close()
    print(
        f"Loaded {len(registry.licenses)} license(s) and "
        f"{len(registry.repositories)} repository/repositories. "
        "Each repository still needs sourcecut-probe-repository before discovery."
    )
