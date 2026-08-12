from __future__ import annotations

import uuid
from datetime import UTC, datetime
from threading import RLock
from typing import Protocol

from sourcecut_api.models.odyssey_board import (
    BoardCreate,
    BoardPatch,
    BoardRevision,
    OdysseyBoard,
    OdysseyBoardSection,
    SectionRegeneration,
)

DEFAULT_SECTION_TITLES = (
    "Narrative Context",
    "Setting",
    "Characters",
    "Actions and Blocking",
    "Objects and Material Culture",
    "Language and Translation",
    "Geography",
    "Visual Reception",
    "Conflicts and Unknowns",
    "Source List",
)


class BoardNotFoundError(LookupError):
    pass


class BoardConflictError(RuntimeError):
    pass


class BoardRevisionNotFoundError(LookupError):
    pass


class BoardStore(Protocol):
    def save_board(self, board: OdysseyBoard, revision: BoardRevision) -> None: ...

    def get_board(self, board_id: str) -> OdysseyBoard | None: ...

    def save_revision(self, revision: BoardRevision) -> None: ...

    def list_revisions(self, board_id: str) -> tuple[BoardRevision, ...]: ...

    def get_revision(self, board_id: str, revision_id: str) -> BoardRevision | None: ...


class MemoryBoardStore:
    def __init__(self) -> None:
        self._boards: dict[str, OdysseyBoard] = {}
        self._revisions: dict[str, list[BoardRevision]] = {}
        self._lock = RLock()

    def save_board(self, board: OdysseyBoard, revision: BoardRevision) -> None:
        with self._lock:
            self._boards[board.board_id] = board
            self._revisions.setdefault(board.board_id, []).append(revision)

    def get_board(self, board_id: str) -> OdysseyBoard | None:
        with self._lock:
            return self._boards.get(board_id)

    def save_revision(self, revision: BoardRevision) -> None:
        with self._lock:
            self._revisions.setdefault(revision.board_id, []).append(revision)

    def list_revisions(self, board_id: str) -> tuple[BoardRevision, ...]:
        with self._lock:
            return tuple(self._revisions.get(board_id, ()))

    def get_revision(self, board_id: str, revision_id: str) -> BoardRevision | None:
        with self._lock:
            return next(
                (
                    revision
                    for revision in self._revisions.get(board_id, ())
                    if revision.revision_id == revision_id
                ),
                None,
            )


class OdysseyBoardService:
    def __init__(self, store: BoardStore) -> None:
        self._store = store

    def create(self, request: BoardCreate, *, actor: str = "public-user") -> OdysseyBoard:
        now = datetime.now(UTC)
        board_id = str(uuid.uuid4())
        revision_id = str(uuid.uuid4())
        sections = request.sections or tuple(
            OdysseyBoardSection(
                section_id=_slug(title),
                title=title,
            )
            for title in DEFAULT_SECTION_TITLES
        )
        board = OdysseyBoard(
            board_id=board_id,
            revision_id=revision_id,
            title=request.title,
            question=request.question,
            summary=request.summary,
            sections=sections,
            release_pins=request.release_pins,
            warnings=request.warnings,
            conflicts=request.conflicts,
            unsupported_questions=request.unsupported_questions,
            agent_trace=request.agent_trace,
            source_session_id=request.source_session_id,
            created_at=now,
            updated_at=now,
        )
        revision = _revision(board, "", "current", ("created",), actor)
        self._store.save_board(board, revision)
        return board

    def get(self, board_id: str) -> OdysseyBoard:
        board = self._store.get_board(board_id)
        if board is None:
            raise BoardNotFoundError(board_id)
        return board

    def patch(self, board_id: str, request: BoardPatch) -> OdysseyBoard:
        current = self.get(board_id)
        self._assert_current(current, request.expected_revision_id)
        change_names = request.model_fields_set - {"expected_revision_id", "actor"}
        changes = {
            name: getattr(request, name)
            for name in change_names
            if getattr(request, name) is not None
        }
        revision_id = str(uuid.uuid4())
        updated = current.model_copy(
            update={**changes, "revision_id": revision_id, "updated_at": datetime.now(UTC)}
        )
        revision = _revision(
            updated,
            current.revision_id,
            "current",
            tuple(sorted(changes)),
            request.actor,
        )
        self._store.save_board(updated, revision)
        return updated

    def regenerate_section(
        self,
        board_id: str,
        section_id: str,
        request: SectionRegeneration,
    ) -> BoardRevision:
        current = self.get(board_id)
        self._assert_current(current, request.expected_revision_id)
        if not any(section.section_id == section_id for section in current.sections):
            raise BoardNotFoundError(section_id)
        candidate_id = str(uuid.uuid4())
        sections = tuple(
            section.model_copy(
                update={
                    "generated_text": request.generated_text,
                    "warnings": request.warnings,
                }
            )
            if section.section_id == section_id
            else section
            for section in current.sections
        )
        candidate = current.model_copy(
            update={
                "revision_id": candidate_id,
                "sections": sections,
                "agent_trace": current.agent_trace + request.trace,
                "updated_at": datetime.now(UTC),
            }
        )
        revision = _revision(
            candidate,
            current.revision_id,
            "candidate",
            (f"sections.{section_id}.generated_text",),
            request.actor,
        )
        self._store.save_revision(revision)
        return revision

    def accept_candidate(
        self, board_id: str, revision_id: str, *, expected_revision_id: str, actor: str
    ) -> OdysseyBoard:
        current = self.get(board_id)
        self._assert_current(current, expected_revision_id)
        candidate = self._store.get_revision(board_id, revision_id)
        if candidate is None or candidate.revision_kind != "candidate":
            raise BoardRevisionNotFoundError(revision_id)
        accepted_id = str(uuid.uuid4())
        accepted = candidate.document.model_copy(
            update={"revision_id": accepted_id, "updated_at": datetime.now(UTC)}
        )
        revision = _revision(
            accepted,
            current.revision_id,
            "current",
            candidate.changed_fields,
            actor,
        )
        self._store.save_board(accepted, revision)
        return accepted

    def duplicate(self, board_id: str, *, actor: str = "public-user") -> OdysseyBoard:
        source = self.get(board_id)
        now = datetime.now(UTC)
        duplicate = source.model_copy(
            update={
                "board_id": str(uuid.uuid4()),
                "revision_id": str(uuid.uuid4()),
                "title": f"{source.title} — Copy",
                "source_session_id": "",
                "created_at": now,
                "updated_at": now,
            }
        )
        revision = _revision(duplicate, "", "duplicate", ("duplicated_from",), actor)
        self._store.save_board(duplicate, revision)
        return duplicate

    def snapshot(self, board_id: str, *, expected_revision_id: str, actor: str) -> BoardRevision:
        current = self.get(board_id)
        self._assert_current(current, expected_revision_id)
        snapshot = current.model_copy(update={"revision_id": str(uuid.uuid4())})
        revision = _revision(snapshot, current.revision_id, "snapshot", ("snapshot",), actor)
        self._store.save_revision(revision)
        return revision

    def revisions(self, board_id: str) -> tuple[BoardRevision, ...]:
        self.get(board_id)
        return self._store.list_revisions(board_id)

    @staticmethod
    def _assert_current(current: OdysseyBoard, expected_revision_id: str) -> None:
        if current.revision_id != expected_revision_id:
            raise BoardConflictError(
                f"revision {expected_revision_id} is stale; "
                f"current revision is {current.revision_id}"
            )


def _revision(
    board: OdysseyBoard,
    parent_revision_id: str,
    kind: str,
    changed_fields: tuple[str, ...],
    actor: str,
) -> BoardRevision:
    return BoardRevision(
        revision_id=board.revision_id,
        board_id=board.board_id,
        parent_revision_id=parent_revision_id,
        revision_kind=kind,
        changed_fields=changed_fields,
        actor=actor,
        release_pins=board.release_pins,
        document=board,
        created_at=board.updated_at,
    )


def _slug(value: str) -> str:
    return "-".join(
        "".join(character.lower() if character.isalnum() else " " for character in value).split()
    )
