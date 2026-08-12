from __future__ import annotations

import json
from pathlib import Path

from conftest import FakeClickHouseClient
from fastapi.testclient import TestClient

from sourcecut_api.corpora import CorpusRegistry
from sourcecut_api.corpora.odyssey import (
    ODYSSEY_VERSIONS,
    PERSEUS_REVISION,
    OdysseyCorpusAdapter,
)
from sourcecut_api.main import create_app
from sourcecut_api.repositories import ClickHouseCatalogRepository


def test_odyssey_adapter_registers_work_versions_and_rights() -> None:
    detail = OdysseyCorpusAdapter().detail()

    assert detail.corpus.corpus_id == "odyssey"
    assert detail.corpus.default_work_id == "odyssey"
    assert detail.works[0].book_count == 24
    assert detail.works[0].cts_work_urn == "urn:cts:greekLit:tlg0012.tlg002"
    assert {version.language for version in detail.versions} == {"grc", "eng"}
    assert {version.version_type.value for version in detail.versions} == {
        "edition",
        "translation",
    }
    assert all(version.upstream_revision == PERSEUS_REVISION for version in detail.versions)
    assert all(
        version.display_decision.value == "full_text_no_bulk_export"
        for version in detail.versions
    )
    assert detail.licenses[0].share_alike is True
    assert "TEI header" in detail.known_limitations[0]


def test_manifest_is_pinned_and_matches_registered_versions() -> None:
    path = Path(__file__).parents[1] / "data" / "manifests" / "odyssey" / "perseus.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))

    assert manifest["upstream_revision"] == PERSEUS_REVISION
    assert len(PERSEUS_REVISION) == 40
    assert {item["version_id"] for item in manifest["versions"]} == {
        version.version_id for version in ODYSSEY_VERSIONS
    }
    assert all(item["upstream_path"].endswith(".xml") for item in manifest["versions"])


def test_catalog_repository_writes_typed_provenance_records() -> None:
    client = FakeClickHouseClient("corpus")
    detail = OdysseyCorpusAdapter().detail()

    result = ClickHouseCatalogRepository(client).load_catalog(detail)  # type: ignore[arg-type]

    assert result.corpora_written == 1
    assert result.works_written == 1
    assert result.versions_written == 3
    assert result.licenses_written == 2
    assert client.tables["corpora"][0]["status"] == "preview"
    assert client.tables["works"][0]["book_count"] == 24
    assert client.tables["source_versions"][0]["source_sha256"] is None
    assert json.loads(client.tables["source_versions"][0]["raw_manifest"])[
        "upstream_repository"
    ].endswith("canonical-greekLit")
    assert client.tables["licenses"][0]["commercial_use_allowed"] == 1


def test_corpus_api_exposes_metadata_and_rejects_unknown_ids() -> None:
    app = create_app(corpus_registry=CorpusRegistry((OdysseyCorpusAdapter(),)))
    client = TestClient(app)

    listing = client.get("/api/v1/corpora")
    detail = client.get("/api/v1/corpora/odyssey")
    versions = client.get("/api/v1/works/odyssey/versions")

    assert listing.status_code == 200
    assert listing.json()[0]["corpus_id"] == "odyssey"
    assert detail.status_code == 200
    assert detail.json()["works"][0]["book_count"] == 24
    assert len(versions.json()) == 3
    assert client.get("/api/v1/corpora/missing").status_code == 404
    assert client.get("/api/v1/works/missing/versions").status_code == 404
