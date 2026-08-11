from __future__ import annotations

import json
from pathlib import Path

from pipelines.media.core import ArchiveApiClient, HttpPayload
from pipelines.media.nps import harvest_nps, normalize_nps
from pipelines.media.smithsonian import harvest_smithsonian, normalize_smithsonian
from sourcecut_api.models import HistoricalRelationship, RightsStatus

FIXTURE_ROOT = Path("fixtures/media")


def _fixture(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def test_smithsonian_accepts_only_cc0_media() -> None:
    accepted, rejected = _fixture("smithsonian-search.json")["response"]["rows"]

    asset = normalize_smithsonian(accepted)

    assert asset is not None
    assert asset.asset_id == "si:edanmdm-nmah_463144"
    assert asset.rights_status is RightsStatus.PUBLIC_DOMAIN
    assert asset.creation_year == 1801
    assert asset.historical_relationship is HistoricalRelationship.PERIOD_COMPARATIVE
    assert normalize_smithsonian(rejected) is None


def test_nps_rejects_ambiguous_rights_and_labels_environmental_reference() -> None:
    accepted, rejected = _fixture("nps-assets.json")["data"]

    asset = normalize_nps(accepted)

    assert asset is not None
    assert asset.provider == "National Park Service"
    assert asset.historical_relationship is HistoricalRelationship.PERIOD_COMPARATIVE
    assert normalize_nps(rejected) is None


def test_smithsonian_harvest_is_cached_and_counts_rights_rejections(tmp_path: Path) -> None:
    payload = _fixture("smithsonian-search.json")
    calls: list[str] = []

    def transport(url: str) -> HttpPayload:
        calls.append(url)
        if "ids.si.edu" in url:
            return HttpPayload(b"jpeg", "image/jpeg")
        return HttpPayload(json.dumps(payload).encode(), "application/json")

    client = ArchiveApiClient("Smithsonian", {"ids.si.edu"}, transport=transport)
    first = harvest_smithsonian(client, tmp_path, "test-key", ("peace medal",), max_items=3)
    call_count = len(calls)
    second = harvest_smithsonian(client, tmp_path, "test-key", ("peace medal",), max_items=3)

    assert len(first.assets) == 1
    assert first.rejected_rights == 1
    assert first.raw_records_cached == 1
    assert first.thumbnails_cached == 1
    assert second.raw_records_cached == 0
    assert second.thumbnails_cached == 0
    assert len(calls) == call_count
    assert first.assets[0].asset_id == second.assets[0].asset_id


def test_nps_harvest_is_cached_and_counts_rights_rejections(tmp_path: Path) -> None:
    payload = _fixture("nps-assets.json")
    calls: list[str] = []

    def transport(url: str) -> HttpPayload:
        calls.append(url)
        if "/common/uploads/" in url:
            return HttpPayload(b"jpeg", "image/jpeg")
        return HttpPayload(json.dumps(payload).encode(), "application/json")

    client = ArchiveApiClient("NPS", {"www.nps.gov"}, transport=transport)
    first = harvest_nps(client, tmp_path, "test-key", max_items=3)
    call_count = len(calls)
    second = harvest_nps(client, tmp_path, "test-key", max_items=3)

    assert len(first.assets) == 1
    assert first.rejected_rights == 1
    assert first.raw_records_cached == 1
    assert first.thumbnails_cached == 1
    assert second.raw_records_cached == 0
    assert second.thumbnails_cached == 0
    assert len(calls) == call_count
