from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pipelines.acquisition.probe import evaluate, probe, read_rights_field, render
from sourcecut_api.db.load_repositories import (
    DEFAULT_LICENSE_PATH,
    DEFAULT_REPOSITORY_PATH,
    RegistryError,
    load_registry,
    repository_rows,
    validate_repositories,
)

LICENSE_IDS = {"us-public-domain"}


def entry(**changes: Any) -> dict[str, Any]:
    record = {
        "repository_id": "gutenberg",
        "display_name": "Project Gutenberg",
        "base_url": "https://gutendex.com",
        "adapter": "gutendex",
        "rights_field": "copyright",
        "eligible_values": ["false"],
        "default_license_id": "us-public-domain",
        "reviewed_by": "reviewer@example.com",
        "reviewed_at": "2026-09-03T00:00:00Z",
    }
    record.update(changes)
    return record


def refuses(record: dict[str, Any]) -> str:
    with pytest.raises(RegistryError) as error:
        validate_repositories([record], license_ids=LICENSE_IDS)
    return str(error.value)


# -- the registry files themselves -------------------------------------------


def test_the_committed_registry_is_valid() -> None:
    registry = load_registry(DEFAULT_LICENSE_PATH, DEFAULT_REPOSITORY_PATH)

    assert {item["repository_id"] for item in registry.repositories} == {
        "gutenberg",
        "internet_archive",
    }
    # Every repository names a license that the same load supplies.
    license_ids = {item["license_id"] for item in registry.licenses}
    assert all(
        item["default_license_id"] in license_ids for item in registry.repositories
    )


def test_loading_the_registry_never_claims_a_probe_happened() -> None:
    from datetime import UTC, datetime

    from sourcecut_api.db.load_repositories import REPOSITORY_COLUMNS

    row = repository_rows([entry()], datetime.now(UTC))[0]

    assert row[REPOSITORY_COLUMNS.index("probed_at")] is None
    assert row[REPOSITORY_COLUMNS.index("probe_sample_size")] == 0


# -- what the registry refuses ------------------------------------------------


def test_a_repository_without_a_rights_field_is_refused() -> None:
    assert "rights_field" in refuses(entry(rights_field="  "))


def test_a_pattern_is_refused_because_eligibility_is_an_exact_match() -> None:
    message = refuses(entry(eligible_values=["Public Domain*"]))

    assert "exact string match" in message


def test_an_eligible_value_list_that_admits_nothing_is_refused() -> None:
    assert "eligible_values" in refuses(entry(eligible_values=[]))
    assert "at least one eligible" in refuses(entry(eligible_values={"any": True}))
    assert "empty eligible" in refuses(entry(eligible_values=["  "]))


def test_an_unknown_license_is_refused() -> None:
    message = refuses(entry(default_license_id="invented-license"))

    assert "invented-license" in message


def test_an_unreviewed_repository_is_refused() -> None:
    """ADR-024's human gate is a recorded row, not an implication."""
    assert "reviewed_by" in refuses(entry(reviewed_by=""))
    assert "reviewed_at" in refuses(entry(reviewed_at=""))


def test_a_plain_http_repository_is_refused() -> None:
    assert "https" in refuses(entry(base_url="http://gutendex.com"))


def test_a_duplicate_repository_id_is_refused() -> None:
    with pytest.raises(RegistryError) as error:
        validate_repositories([entry(), entry()], license_ids=LICENSE_IDS)

    assert "Duplicate repository_id" in str(error.value)


def test_a_registry_file_that_is_not_a_list_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "source_repositories.json"
    path.write_text(json.dumps({"repository_id": "gutenberg"}), encoding="utf-8")

    with pytest.raises(RegistryError):
        load_registry(DEFAULT_LICENSE_PATH, path)


# -- the probe ---------------------------------------------------------------


def test_rights_field_reads_a_dotted_path_and_stringifies_a_boolean() -> None:
    assert read_rights_field({"copyright": False}, "copyright") == "false"
    assert read_rights_field({"metadata": {"rights": "Public Domain"}}, "metadata.rights") == (
        "Public Domain"
    )


def test_an_absent_or_ambiguous_rights_field_reads_as_missing() -> None:
    assert read_rights_field({"metadata": {}}, "metadata.rights") is None
    assert read_rights_field({"rights": None}, "rights") is None
    # Two determinations on one item is not a determination.
    assert read_rights_field({"rights": ["a", "b"]}, "rights") is None
    assert read_rights_field({"rights": ["only"]}, "rights") == "only"


def test_a_probe_separates_absence_from_ineligibility() -> None:
    items = [
        {"copyright": False},
        {"copyright": True},
        {"title": "no rights field at all"},
        {"copyright": False},
    ]

    result = evaluate("gutenberg", items, rights_field="copyright", eligible_values=["false"])

    assert (result.sample_size, result.present, result.matched) == (4, 3, 2)
    assert result.observed_values == ("false", "true")


def test_a_field_that_never_appears_is_rejected() -> None:
    """No occurrence is no evidence the declared path exists at all."""
    items = [{"title": "x"}, {"title": "y"}]

    result = evaluate("gutenberg", items, rights_field="copyright", eligible_values=["false"])

    assert not result.usable
    assert "REJECTED" in render(result, rights_field="copyright")


def test_a_field_present_on_only_some_items_is_thin_but_accepted() -> None:
    """Internet Archive records a determination only on items a librarian reviewed.

    Absence there is a correct "status unknown", which acquisition already
    refuses; rejecting the entry for it would confuse low yield with a wrong
    field name.
    """
    items = [{"title": "x"}, {"title": "y"}, {"copyright": False}]

    result = evaluate("gutenberg", items, rights_field="copyright", eligible_values=["false"])

    assert result.usable and result.thin
    assert "THIN" in render(result, rights_field="copyright")


def test_a_repository_that_matches_nothing_is_still_usable() -> None:
    """Holding little public-domain material is not the same as a broken entry."""
    items = [{"copyright": True}, {"copyright": True}]

    result = evaluate("gutenberg", items, rights_field="copyright", eligible_values=["false"])

    assert result.usable
    assert result.match_rate == 0.0


def test_the_probe_reads_the_repository_through_its_adapter() -> None:
    requested: list[str] = []

    def fetch(url: str) -> bytes:
        requested.append(url)
        return json.dumps({"results": [{"copyright": False}, {"copyright": True}]}).encode()

    result = probe(entry(), query="journal", limit=5, fetch=fetch)

    assert requested == ["https://gutendex.com/books/?search=journal"]
    assert (result.present, result.matched) == (2, 1)


def test_the_archive_probe_reads_rights_from_the_item_not_the_search_result() -> None:
    def fetch(url: str) -> bytes:
        if "advancedsearch" in url:
            return json.dumps({"response": {"docs": [{"identifier": "item-1"}]}}).encode()
        return json.dumps(
            {"metadata": {"possible-copyright-status": "NOT_IN_COPYRIGHT"}}
        ).encode()

    result = probe(
        entry(
            repository_id="internet_archive",
            base_url="https://archive.org",
            adapter="internet_archive",
            rights_field="metadata.possible-copyright-status",
            eligible_values=["NOT_IN_COPYRIGHT"],
        ),
        query="journal",
        limit=1,
        fetch=fetch,
    )

    assert (result.sample_size, result.matched) == (1, 1)
