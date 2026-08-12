from __future__ import annotations

from fastapi.testclient import TestClient

from sourcecut_api.main import create_app
from sourcecut_api.models.odyssey_board import (
    BoardCreate,
    BoardItem,
    BoardItemKind,
    BoardPatch,
    BoardReleasePins,
    BoardTraceEvent,
    OdysseyBoardSection,
    SectionRegeneration,
)
from sourcecut_api.services.odyssey_board import (
    BoardConflictError,
    MemoryBoardStore,
    OdysseyBoardService,
)


def request() -> BoardCreate:
    return BoardCreate(
        title="Odysseus and Polyphemus — Book 9",
        question="How does Odysseus frame the encounter?",
        release_pins=BoardReleasePins(
            release_manifest_id="odyssey-release-test",
            corpus_revision="790c8428",
            annotation_release_ids=("odyssey-treebank-test",),
            active_versions=("odyssey-perseus-grc2", "odyssey-perseus-eng3"),
        ),
        sections=(
            OdysseyBoardSection(
                section_id="narrative-context",
                title="Narrative Context",
                generated_text="Generated synthesis remains reviewable.",
                user_notes="My independent note.",
                items=(
                    BoardItem(
                        item_id="item-1",
                        kind=BoardItemKind.PASSAGE,
                        reference_id="urn:cts:greekLit:tlg0012.tlg002:9.105-115",
                        label="The Cyclopes introduced",
                        citation="Od. 9.105–115",
                    ),
                ),
            ),
        ),
    )


def test_board_revisions_preserve_notes_and_require_optimistic_token() -> None:
    service = OdysseyBoardService(MemoryBoardStore())
    created = service.create(request())
    changed = service.patch(
        created.board_id,
        BoardPatch(
            expected_revision_id=created.revision_id,
            title="Cyclopeia evidence file",
            sections=(created.sections[0].model_copy(update={"user_notes": "Revised by user."}),),
        ),
    )

    assert changed.sections[0].generated_text == created.sections[0].generated_text
    assert changed.sections[0].user_notes == "Revised by user."
    assert service.revisions(created.board_id)[0].document == created
    try:
        service.patch(
            created.board_id,
            BoardPatch(expected_revision_id=created.revision_id, title="Stale edit"),
        )
    except BoardConflictError:
        pass
    else:
        raise AssertionError("stale edits must fail")


def test_regeneration_is_candidate_until_explicit_acceptance() -> None:
    service = OdysseyBoardService(MemoryBoardStore())
    created = service.create(request())
    candidate = service.regenerate_section(
        created.board_id,
        "narrative-context",
        SectionRegeneration(
            expected_revision_id=created.revision_id,
            generated_text="A new generated interpretation.",
            trace=(
                BoardTraceEvent(
                    event_id="trace-1",
                    event_type="mcp",
                    stage="evidence",
                    message="Resolved passage reference",
                    occurred_at=created.created_at,
                    tool_name="get_text_range",
                ),
            ),
        ),
    )

    assert candidate.revision_kind == "candidate"
    assert service.get(created.board_id) == created
    accepted = service.accept_candidate(
        created.board_id,
        candidate.revision_id,
        expected_revision_id=created.revision_id,
        actor="scholar",
    )
    assert accepted.sections[0].generated_text == "A new generated interpretation."
    assert accepted.agent_trace[-1].tool_name == "get_text_range"


def test_snapshot_and_duplicate_are_immutable_reconstructable_documents() -> None:
    service = OdysseyBoardService(MemoryBoardStore())
    created = service.create(request())
    snapshot = service.snapshot(
        created.board_id, expected_revision_id=created.revision_id, actor="scholar"
    )
    duplicate = service.duplicate(created.board_id)

    assert snapshot.document.sections[0].items[0].reference_id.endswith("9.105-115")
    assert snapshot.revision_kind == "snapshot"
    assert duplicate.board_id != created.board_id
    assert duplicate.release_pins == created.release_pins
    assert duplicate.source_session_id == ""


def test_board_api_returns_conflict_for_stale_revision() -> None:
    with TestClient(create_app(board_store=MemoryBoardStore())) as client:
        response = client.post("/api/v1/boards", json=request().model_dump(mode="json"))
        assert response.status_code == 201
        board = response.json()
        patch = client.patch(
            f"/api/v1/boards/{board['board_id']}",
            json={"expected_revision_id": board["revision_id"], "summary": "Saved."},
        )
        assert patch.status_code == 200
        conflict = client.patch(
            f"/api/v1/boards/{board['board_id']}",
            json={"expected_revision_id": board["revision_id"], "summary": "Lost edit."},
        )
        assert conflict.status_code == 409
