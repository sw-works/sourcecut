from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from threading import RLock
from typing import TYPE_CHECKING

from sourcecut_api.models.odyssey_board import BoardReleasePins, BoardRevision, OdysseyBoard

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client

SYNC_INSERT_SETTINGS = {"async_insert": 1, "wait_for_async_insert": 1}


class ClickHouseBoardRepository:
    def __init__(self, client: Client) -> None:
        self._client = client
        self._lock = RLock()

    def save_board(self, board: OdysseyBoard, revision: BoardRevision) -> None:
        with self._lock:
            self._insert_revision(revision)
            self._client.insert(
                "research_boards",
                [
                    [
                        board.board_id,
                        board.corpus_id,
                        board.revision_id,
                        board.model_dump_json(),
                        board.release_pins.release_manifest_id,
                        board.created_at,
                        board.updated_at,
                    ]
                ],
                column_names=[
                    "board_id",
                    "corpus_id",
                    "current_revision_id",
                    "document_json",
                    "release_manifest_id",
                    "created_at",
                    "updated_at",
                ],
                settings=SYNC_INSERT_SETTINGS,
            )

    def get_board(self, board_id: str) -> OdysseyBoard | None:
        with self._lock:
            rows = self._client.query(
                """
SELECT document_json
FROM research_boards FINAL
WHERE board_id = {board_id:String}
LIMIT 1
""".strip(),
                parameters={"board_id": board_id},
            ).result_rows
        return OdysseyBoard.model_validate_json(str(rows[0][0])) if rows else None

    def save_revision(self, revision: BoardRevision) -> None:
        with self._lock:
            self._insert_revision(revision)

    def list_revisions(self, board_id: str) -> tuple[BoardRevision, ...]:
        with self._lock:
            rows = self._client.query(
                f"{_REVISION_SELECT}\nWHERE board_id = {{board_id:String}}\n"
                "ORDER BY created_at, revision_id",
                parameters={"board_id": board_id},
            ).result_rows
        return tuple(_revision_from_row(row) for row in rows)

    def get_revision(self, board_id: str, revision_id: str) -> BoardRevision | None:
        with self._lock:
            rows = self._client.query(
                f"{_REVISION_SELECT}\nWHERE board_id = {{board_id:String}} "
                "AND revision_id = {revision_id:String}\nLIMIT 1",
                parameters={"board_id": board_id, "revision_id": revision_id},
            ).result_rows
        return _revision_from_row(rows[0]) if rows else None

    def _insert_revision(self, revision: BoardRevision) -> None:
        self._client.insert(
            "board_revisions",
            [
                [
                    revision.revision_id,
                    revision.board_id,
                    revision.parent_revision_id,
                    revision.revision_kind,
                    revision.document.model_dump_json(),
                    revision.release_pins.release_manifest_id,
                    list(revision.changed_fields),
                    revision.actor,
                    revision.document.source_session_id,
                    "["
                    + ",".join(event.model_dump_json() for event in revision.document.agent_trace)
                    + "]",
                    revision.created_at,
                ]
            ],
            column_names=[
                "revision_id",
                "board_id",
                "parent_revision_id",
                "revision_kind",
                "document_json",
                "release_manifest_id",
                "changed_fields",
                "actor",
                "source_session_id",
                "trace_json",
                "created_at",
            ],
            settings=SYNC_INSERT_SETTINGS,
        )


class LazyClickHouseBoardRepository:
    def __init__(self, client_factory: Callable[[], Client]) -> None:
        self._client_factory = client_factory
        self._repository: ClickHouseBoardRepository | None = None
        self._lock = RLock()

    def save_board(self, board: OdysseyBoard, revision: BoardRevision) -> None:
        self._resolved().save_board(board, revision)

    def get_board(self, board_id: str) -> OdysseyBoard | None:
        return self._resolved().get_board(board_id)

    def save_revision(self, revision: BoardRevision) -> None:
        self._resolved().save_revision(revision)

    def list_revisions(self, board_id: str) -> tuple[BoardRevision, ...]:
        return self._resolved().list_revisions(board_id)

    def get_revision(self, board_id: str, revision_id: str) -> BoardRevision | None:
        return self._resolved().get_revision(board_id, revision_id)

    def _resolved(self) -> ClickHouseBoardRepository:
        with self._lock:
            if self._repository is None:
                self._repository = ClickHouseBoardRepository(self._client_factory())
            return self._repository


_REVISION_SELECT = """
SELECT revision_id, board_id, parent_revision_id, revision_kind, document_json,
       release_manifest_id, changed_fields, actor, created_at
FROM board_revisions
""".strip()


def _revision_from_row(row: tuple[object, ...]) -> BoardRevision:
    document = OdysseyBoard.model_validate_json(str(row[4]))
    return BoardRevision(
        revision_id=str(row[0]),
        board_id=str(row[1]),
        parent_revision_id=str(row[2]),
        revision_kind=str(row[3]),
        document=document,
        release_pins=BoardReleasePins.model_validate(document.release_pins),
        changed_fields=tuple(str(value) for value in row[6]),
        actor=str(row[7]),
        created_at=row[8] if isinstance(row[8], datetime) else datetime.now(UTC),
    )
