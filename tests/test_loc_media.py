from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from pipelines.media.loc import (
    HttpPayload,
    LocApiClient,
    LocQuery,
    harvest_loc,
    normalize_loc_item,
)
from sourcecut_api.models import HistoricalRelationship, RightsStatus
from sourcecut_api.repositories import ClickHouseMediaRepository, MediaAssetDriftError


def _item_payload(
    *,
    provider_id: str = "2017814842",
    rights: str = "The contents are in the public domain and are free to use and reuse.",
    restricted: bool = False,
) -> dict[str, Any]:
    return {
        "item": {
            "id": f"http://www.loc.gov/item/{provider_id}/",
            "title": "Bitterroot Valley, Montana. Cattle guard at Ross's Hole",
            "description": ["A historical landscape reference."],
            "contributor": ["Vachon, John"],
            "date": "1942-01-01",
            "subject": ["Bitterroot Valley", "Safety film negatives"],
            "location": ["Montana", "Ravalli County"],
            "url": f"https://www.loc.gov/item/{provider_id}/",
            "rights_information": "No known restrictions.",
            "rights": [rights],
            "access_restricted": restricted,
            "original_format": ["photo, print, drawing"],
        },
        "resources": [
            {
                "image": "https://tile.loc.gov/storage-services/service/pnp/example_150px.jpg"
            }
        ],
    }


def test_normalize_loc_item_preserves_raw_metadata_and_item_rights() -> None:
    payload = _item_payload()

    asset = normalize_loc_item(payload, provider_id="2017814842")

    expected_raw = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    assert asset.asset_id == "loc:2017814842"
    assert asset.rights_status is RightsStatus.PUBLIC_DOMAIN
    assert asset.historical_relationship is HistoricalRelationship.LATER_REPRESENTATION
    assert asset.creation_year == 1942
    assert asset.raw_metadata == expected_raw
    assert asset.metadata_sha256 == hashlib.sha256(expected_raw.encode()).hexdigest()
    assert asset.media_url.startswith("https://tile.loc.gov/")


def test_restricted_item_never_approves_thumbnail() -> None:
    asset = normalize_loc_item(
        _item_payload(restricted=True),
        provider_id="2017814842",
    )

    assert asset.rights_status is RightsStatus.RESTRICTED
    assert asset.thumbnail_approved is False


def test_harvest_caches_raw_json_and_only_downloads_approved_thumbnail(tmp_path: Path) -> None:
    query = LocQuery(endpoint="maps", query="Bitterroot")
    search_payload = {
        "results": [{"id": "http://www.loc.gov/item/2017814842/"}],
        "pagination": {"of": 1},
    }
    item_payload = _item_payload()
    calls: list[str] = []

    def transport(url: str) -> HttpPayload:
        calls.append(url)
        if "tile.loc.gov" in url:
            return HttpPayload(b"jpeg-bytes", "image/jpeg")
        payload = search_payload if "/maps/" in url else item_payload
        return HttpPayload(json.dumps(payload).encode(), "application/json")

    first = harvest_loc(
        LocApiClient(transport=transport),
        tmp_path,
        queries=(query,),
        item_ids=(),
    )
    call_count = len(calls)
    second = harvest_loc(
        LocApiClient(transport=transport),
        tmp_path,
        queries=(query,),
        item_ids=(),
    )

    assert len(first.assets) == 1
    assert first.raw_records_cached == 2
    assert first.thumbnails_cached == 1
    assert Path(first.assets[0].thumbnail_path).read_bytes() == b"jpeg-bytes"
    assert second.raw_records_cached == 0
    assert second.thumbnails_cached == 0
    assert len(calls) == call_count
    assert len(tuple((tmp_path / "items").glob("*.json"))) == 1


class FakeClickHouseClient:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.settings: dict[str, Any] | None = None
        self.query_count = 0

    def query(self, query: str, parameters: dict[str, Any]) -> SimpleNamespace:
        self.query_count += 1
        assert "FROM media_assets" in query
        return SimpleNamespace(
            result_rows=[
                (row["asset_id"], row["metadata_sha256"])
                for row in self.rows
                if row["asset_id"] in parameters["ids"]
            ]
        )

    def insert(
        self,
        table: str,
        data: list[list[object]],
        *,
        column_names: list[str],
        settings: dict[str, Any] | None,
    ) -> None:
        assert table == "media_assets"
        self.settings = settings
        self.rows.extend(dict(zip(column_names, row, strict=True)) for row in data)


def test_media_repository_relies_on_engine_dedup_and_rejects_input_drift() -> None:
    asset = normalize_loc_item(_item_payload(), provider_id="2017814842")
    client = FakeClickHouseClient()
    repository = ClickHouseMediaRepository(client)  # type: ignore[arg-type]

    assert repository.load_assets([asset]) == 1
    assert repository.load_assets([asset]) == 1
    assert client.settings == {"async_insert": 1, "wait_for_async_insert": 1}
    assert len(client.rows) == 2
    assert client.query_count == 0

    changed = asset.model_copy(update={"metadata_sha256": "f" * 64})
    assert repository.load_assets([changed]) == 1
    with pytest.raises(MediaAssetDriftError, match="conflicting metadata"):
        repository.load_assets([asset, changed])
