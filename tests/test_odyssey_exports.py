from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from sourcecut_api.main import create_app
from sourcecut_api.models.export import BoardExportRequest, ExportFormat
from sourcecut_api.models.odyssey_board import (
    BoardCreate,
    BoardItem,
    BoardItemKind,
    BoardReleasePins,
    OdysseyBoardSection,
)
from sourcecut_api.services.export import ExportTokenError, OdysseyExportService
from sourcecut_api.services.odyssey_board import MemoryBoardStore, OdysseyBoardService


def board_service() -> tuple[OdysseyBoardService, str, str]:
    service = OdysseyBoardService(MemoryBoardStore())
    board = service.create(
        BoardCreate(
            title="μῆνιν and the Cyclopeia",
            question="How is the encounter evidenced?",
            summary="A compact test board.",
            release_pins=BoardReleasePins(
                release_manifest_id="odyssey-release-test",
                corpus_revision="a" * 40,
                annotation_release_ids=("annotation-1",),
                active_versions=("odyssey-perseus-grc2",),
            ),
            warnings=("Geography remains conjectural.",),
            sections=(
                OdysseyBoardSection(
                    section_id="evidence",
                    title="Evidence",
                    generated_text="Generated account.",
                    user_notes="Scholar note.",
                    items=(
                        BoardItem(
                            item_id="passage-1",
                            kind=BoardItemKind.PASSAGE,
                            reference_id="urn:cts:greekLit:tlg0012.tlg002:9.105-115",
                            label="Cyclopes introduced",
                            citation="Od. 9.105–115",
                        ),
                        BoardItem(
                            item_id="map-1",
                            kind=BoardItemKind.MAP_VIEW,
                            reference_id="berard",
                            label="Bérard proposal",
                            citation="Bérard 1927",
                            metadata={
                                "coordinates": [15.1, 38.2],
                                "hypothesis_id": "berard",
                                "confidence": "low",
                            },
                        ),
                        BoardItem(
                            item_id="asset-restricted",
                            kind=BoardItemKind.ASSET,
                            reference_id="met-481994",
                            label="Restricted comparative image",
                            rights_status="RESTRICTED",
                            metadata={"image_url": "https://restricted.invalid/image.jpg"},
                        ),
                    ),
                ),
            ),
        )
    )
    return service, board.board_id, board.revision_id


@pytest.mark.parametrize(
    ("format_", "prefix"),
    [
        (ExportFormat.JSON, b"{"),
        (ExportFormat.MARKDOWN, b"# "),
        (ExportFormat.HTML, b"<!doctype html>"),
        (ExportFormat.PDF, b"%PDF"),
        (ExportFormat.CITATIONS_TEXT, "Bérard 1927".encode()),
        (ExportFormat.CITATIONS_MARKDOWN, b"# Citations"),
        (ExportFormat.CSL_JSON, b"["),
        (ExportFormat.BIBTEX, b"@book"),
        (ExportFormat.GEOJSON, b"{"),
        (ExportFormat.MAP_PNG, b"\x89PNG"),
    ],
)
def test_export_formats_are_derived_from_frozen_revision(
    format_: ExportFormat, prefix: bytes
) -> None:
    boards, board_id, revision_id = board_service()
    service = OdysseyExportService(boards, secret=b"test-secret")
    job = service.create_export(
        board_id,
        BoardExportRequest(revision_id=revision_id, format=format_),
    )
    token = job.download_url.split("token=", 1)[1]
    artifact = service.download(job.job_id, token)

    assert artifact.content.startswith(prefix)
    assert len(job.artifact_sha256) == 64
    assert len(job.manifest_sha256) == 64


def test_public_json_and_share_remove_restricted_image_fields() -> None:
    boards, board_id, revision_id = board_service()
    service = OdysseyExportService(boards, secret=b"test-secret")
    job = service.create_export(
        board_id,
        BoardExportRequest(revision_id=revision_id, format=ExportFormat.JSON),
    )
    token = job.download_url.split("token=", 1)[1]
    payload = json.loads(service.download(job.job_id, token).content)
    asset = payload["board"]["sections"][0]["items"][2]

    assert "image_url" not in asset["metadata"]
    assert asset["metadata"]["display"] == "metadata_only"
    assert payload["provenance_manifest"]["omitted_item_ids"] == ["asset-restricted"]
    link = service.share(board_id, revision_id, 30)
    assert service.shared_board(link.share_token).omitted_item_count == 1


def test_download_signature_is_enforced() -> None:
    boards, board_id, revision_id = board_service()
    service = OdysseyExportService(boards, secret=b"test-secret")
    job = service.create_export(
        board_id,
        BoardExportRequest(revision_id=revision_id, format=ExportFormat.JSON),
    )
    with pytest.raises(ExportTokenError):
        service.download(job.job_id, "tampered.0.signature")


def test_export_api_downloads_and_shares_frozen_snapshot() -> None:
    store = MemoryBoardStore()
    boards = OdysseyBoardService(store)
    created = boards.create(
        BoardCreate(
            title="Test board",
            release_pins=BoardReleasePins(
                release_manifest_id="release",
                corpus_revision="a" * 40,
            ),
        )
    )
    with TestClient(create_app(board_store=store)) as client:
        export_response = client.post(
            f"/api/v1/boards/{created.board_id}/exports",
            json={"revision_id": created.revision_id, "format": "json"},
        )
        assert export_response.status_code == 202
        download = client.get(export_response.json()["download_url"])
        assert download.status_code == 200
        assert download.headers["content-type"] == "application/json"
        share = client.post(
            f"/api/v1/boards/{created.board_id}/shares",
            json={"revision_id": created.revision_id, "expires_in_days": 7},
        )
        assert share.status_code == 201
        shared = client.get(share.json()["share_url"])
        assert shared.status_code == 200
        assert shared.json()["board"]["revision_id"] == created.revision_id
