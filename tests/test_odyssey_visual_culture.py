from __future__ import annotations

from pathlib import Path

from conftest import FakeClickHouseClient
from fastapi.testclient import TestClient

from pipelines.media.met import load_met_odyssey_release
from sourcecut_api.main import create_app
from sourcecut_api.repositories import ClickHouseVisualCultureRepository

ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "data/reference/odyssey_visual_culture.json"
CACHE = ROOT / "data/cache/met"


def test_met_release_preserves_raw_payloads_and_separates_image_rights() -> None:
    release = load_met_odyssey_release(MANIFEST, CACHE)
    assert len(release.assets) == 5
    papyrus = next(a for a in release.assets if a.asset_id == "met:248134")
    restricted = next(a for a in release.assets if a.asset_id == "met:481994")
    assert '"objectID":248134' in papyrus.raw_metadata
    assert papyrus.thumbnail_approved and papyrus.thumbnail_path
    assert not restricted.thumbnail_approved and restricted.media_url == ""
    rejected = next(a for a in release.assessments if a.asset_id == "met:481994")
    assert rejected.relationship_class == "UNRELATED_OR_UNSUPPORTED"
    assert rejected.verification_status == "rejected"


def test_visual_culture_repository_is_idempotent() -> None:
    release = load_met_odyssey_release(MANIFEST, CACHE)
    client = FakeClickHouseClient("corpus")
    repository = ClickHouseVisualCultureRepository(client)  # type: ignore[arg-type]
    first = repository.load(release)
    second = repository.load(release)
    assert first.metadata_inserted == 5 and first.assessments_inserted == 5
    assert second.metadata_inserted == second.links_inserted == second.assessments_inserted == 0


class FakeVisualMcp:
    async def search_odyssey_assets(self, query_text, relationships, public_only, facets):
        del query_text, relationships, public_only, facets
        return [_row()]

    async def get_odyssey_visual_asset(self, asset_id):
        return [{**_row(), "asset_id": asset_id}]


def _row():
    return {
        "asset_id": "met:251485",
        "title": "Terracotta oinochoe",
        "relationship_class": "ANCIENT_REPRESENTATION",
        "production_use": "Ancient reception",
        "limitations": "Not evidence of occurrence",
        "evidence_ids": ["event:bow-contest"],
        "verification_status": "accepted_with_warning",
        "rights_status": "public_domain",
        "image_rights_status": "public_domain",
    }


def test_visual_asset_api_exposes_relationship_limitations() -> None:
    app = create_app()
    app.state.mcp_client_factory = FakeVisualMcp
    client = TestClient(app)
    search = client.post("/api/v1/search/assets", json={})
    assessment = client.get("/api/v1/assets/met:251485/relationships")
    assert search.status_code == assessment.status_code == 200
    assert assessment.json()["relationship_class"] == "ANCIENT_REPRESENTATION"
    assert assessment.json()["limitations"] == "Not evidence of occurrence"
