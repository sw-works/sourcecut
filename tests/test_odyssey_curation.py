from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient

from sourcecut_api.main import create_app
from sourcecut_api.models.curation import (
    CorpusReleaseCreate,
    CurationDecision,
    CurationProposalCreate,
    CurationTarget,
    DerivedRebuildRequest,
    ImportRunRequest,
    ReleaseComparison,
    ReleaseManifestInput,
)
from sourcecut_api.services.curation import (
    CurationConflictError,
    CurationValidationError,
    MemoryCurationStore,
    OdysseyCurationService,
)
from sourcecut_api.services.odyssey_board import MemoryBoardStore


def proposal(target: CurationTarget = CurationTarget.ENTITY) -> CurationProposalCreate:
    changes: dict[str, str] = {"canonical_label": "Polyphemus"}
    if target == CurationTarget.LICENSE:
        changes = {
            "license_id": "cc-by-sa-4.0",
            "display_decision": "full_text_no_bulk_export",
            "source_url": "https://example.test/license",
        }
    return CurationProposalCreate(
        target_type=target,
        target_id="target-1",
        base_revision_id="release-a",
        proposed_changes=changes,
        rationale="Correct the reviewed derived record.",
        citations=("Od. 9.187–542",),
        proposer_id="curator-a",
    )


def trust(service: OdysseyCurationService, record_id: str) -> None:
    reviewed = service.decide(
        record_id,
        CurationDecision(
            expected_revision=1,
            status="reviewed",
            reviewer_id="reviewer-a",
            review_note="Checked against the cited source.",
        ),
    )
    service.decide(
        record_id,
        CurationDecision(
            expected_revision=reviewed.revision,
            status="trusted",
            reviewer_id="reviewer-b",
            review_note="Approved for the trusted layer.",
        ),
    )


def test_curation_preserves_revisions_and_rejects_source_mutation() -> None:
    service = OdysseyCurationService(MemoryCurationStore())
    created = service.propose(proposal())
    trust(service, created.record_id)

    history = service.history(created.record_id)
    assert [record.status.value for record in history] == ["draft", "reviewed", "trusted"]
    assert history[1].reviewer_id == "reviewer-a"
    assert len(service.audit()) == 3
    with pytest.raises(CurationConflictError):
        service.decide(
            created.record_id,
            CurationDecision(
                expected_revision=1,
                status="rejected",
                reviewer_id="reviewer-c",
                review_note="This decision uses a stale revision.",
            ),
        )
    with pytest.raises(CurationValidationError, match="immutable"):
        service.propose(proposal().model_copy(update={"proposed_changes": {"raw_tei": "changed"}}))


def test_imports_are_idempotent_and_release_compare_is_deterministic() -> None:
    service = OdysseyCurationService(MemoryCurationStore())
    request = ImportRunRequest(
        import_kind="corpus",
        upstream_revision="revision-a",
        manifest_sha256=hashlib.sha256(b"manifest").hexdigest(),
        actor_id="operator",
    )
    first = service.register_import(request)
    second = service.register_import(request)
    comparison = service.compare(
        ReleaseManifestInput(records={"a": "1" * 64, "b": "2" * 64}),
        ReleaseManifestInput(records={"b": "3" * 64, "c": "4" * 64}),
    )

    assert first == second
    assert comparison.added == ("c",)
    assert comparison.changed == ("b",)
    assert comparison.removed == ("a",)


def test_release_requires_trusted_records_and_license_then_supports_rollback() -> None:
    service = OdysseyCurationService(MemoryCurationStore())
    entity = service.propose(proposal())
    license_record = service.propose(proposal(CurationTarget.LICENSE))
    run = service.register_import(
        ImportRunRequest(
            import_kind="corpus",
            upstream_revision="revision-a",
            manifest_sha256="a" * 64,
            actor_id="operator",
        )
    )
    release = service.create_release(
        CorpusReleaseCreate(
            label="Odyssey release A",
            upstream_revision="revision-a",
            source_version_ids=("odyssey-perseus-grc2",),
            curation_record_ids=(entity.record_id, license_record.record_id),
            license_record_ids=(license_record.record_id,),
            import_run_ids=(run.import_run_id,),
            comparison=ReleaseComparison(
                added=("book-1",), changed=(), removed=(), unchanged_count=0
            ),
            actor_id="operator",
        )
    )
    with pytest.raises(CurationValidationError, match="untrusted"):
        service.promote_release(release.release_id, actor_id="admin", note="Too early.")
    trust(service, entity.record_id)
    trust(service, license_record.record_id)
    promoted = service.promote_release(
        release.release_id, actor_id="admin", note="All launch gates passed."
    )

    assert promoted.status == "active"
    assert (
        service.rollback(
            promoted.release_id, actor_id="admin", reason="Restore the known-good release."
        ).release_id
        == promoted.release_id
    )
    assert service.coverage().license_records_trusted == 1


def test_derived_rebuild_records_zero_source_mutations() -> None:
    service = OdysseyCurationService(MemoryCurationStore())
    rebuild = service.rebuild(
        DerivedRebuildRequest(
            layer="entities",
            source_version_ids=("odyssey-perseus-grc2",),
            actor_id="operator",
        )
    )
    assert rebuild.source_mutations == 0
    assert service.audit()[0].detail["source_mutations"] == 0


def test_admin_routes_require_authentication_and_expose_coverage() -> None:
    store = MemoryCurationStore()
    with TestClient(
        create_app(
            board_store=MemoryBoardStore(),
            curation_store=store,
            admin_key="correct-key",
        )
    ) as client:
        denied = client.get("/api/v1/admin/odyssey/coverage")
        assert denied.status_code == 401
        headers = {"X-SourceCut-Admin-Key": "correct-key"}
        created = client.post(
            "/api/v1/admin/odyssey/proposals",
            headers=headers,
            json=proposal().model_dump(mode="json"),
        )
        assert created.status_code == 201
        coverage = client.get("/api/v1/admin/odyssey/coverage", headers=headers)
        assert coverage.status_code == 200
        assert coverage.json()["by_target"]["entity"] == 1
