from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client

SESSION_INSERT_SETTINGS = {"async_insert": 1, "wait_for_async_insert": 1}
EVENT_INSERT_SETTINGS = {"async_insert": 1, "wait_for_async_insert": 0}


@dataclass(frozen=True, slots=True)
class StoredResearchSession:
    session_id: str
    status: str
    prompt: str
    board_json: str
    error: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class StoredResearchEvent:
    event_id: str
    session_id: str
    event_type: str
    stage: str
    status: str
    message: str
    payload: dict[str, Any]
    duration_ms: int
    occurred_at: datetime


class ResearchEventRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def save_session(
        self,
        *,
        session_id: str,
        status: str,
        prompt: str,
        board_json: str = "",
        error: str = "",
        created_at: datetime,
    ) -> StoredResearchSession:
        updated_at = datetime.now(UTC)
        self._client.insert(
            "research_sessions",
            [[session_id, status, prompt, board_json, error, created_at, updated_at]],
            column_names=[
                "session_id",
                "status",
                "prompt",
                "board_json",
                "error",
                "created_at",
                "updated_at",
            ],
            settings=SESSION_INSERT_SETTINGS,
        )
        return StoredResearchSession(
            session_id=session_id,
            status=status,
            prompt=prompt,
            board_json=board_json,
            error=error,
            created_at=created_at,
            updated_at=updated_at,
        )

    def get_session(self, session_id: str) -> StoredResearchSession | None:
        rows = self._client.query(
            """
SELECT session_id, status, prompt, board_json, error, created_at, updated_at
FROM research_sessions FINAL
WHERE session_id = {session_id:String}
LIMIT 1
""".strip(),
            parameters={"session_id": session_id},
        ).result_rows
        if not rows:
            return None
        row = rows[0]
        return StoredResearchSession(
            session_id=str(row[0]),
            status=str(row[1]),
            prompt=str(row[2]),
            board_json=str(row[3]),
            error=str(row[4]),
            created_at=row[5],
            updated_at=row[6],
        )

    def record(
        self,
        *,
        session_id: str,
        event_type: str,
        stage: str,
        status: str,
        message: str,
        payload: dict[str, Any] | None = None,
        duration_ms: int = 0,
    ) -> StoredResearchEvent:
        event = StoredResearchEvent(
            event_id=str(uuid.uuid4()),
            session_id=session_id,
            event_type=event_type,
            stage=stage,
            status=status,
            message=message,
            payload=payload or {},
            duration_ms=max(0, min(duration_ms, 2**32 - 1)),
            occurred_at=datetime.now(UTC),
        )
        self._client.insert(
            "research_events",
            [[
                event.event_id,
                event.session_id,
                event.event_type,
                event.stage,
                event.status,
                event.message,
                json.dumps(event.payload, separators=(",", ":"), sort_keys=True),
                event.duration_ms,
                event.occurred_at,
            ]],
            column_names=[
                "event_id",
                "session_id",
                "event_type",
                "stage",
                "status",
                "message",
                "payload_json",
                "duration_ms",
                "occurred_at",
            ],
            settings=EVENT_INSERT_SETTINGS,
        )
        return event

    def list_events(
        self,
        session_id: str,
        *,
        after: tuple[datetime, str] | None = None,
        limit: int = 200,
    ) -> tuple[StoredResearchEvent, ...]:
        cursor = after or (datetime(1970, 1, 1, tzinfo=UTC), "")
        rows = self._client.query(
            """
SELECT event_id, session_id, event_type, stage, status, message,
       payload_json, duration_ms, occurred_at
FROM research_events
WHERE session_id = {session_id:String}
  AND (occurred_at, event_id) > ({occurred_at:DateTime64(3, 'UTC')}, {event_id:String})
ORDER BY occurred_at, event_id
LIMIT {limit:UInt16}
""".strip(),
            parameters={
                "session_id": session_id,
                "occurred_at": cursor[0],
                "event_id": cursor[1],
                "limit": limit,
            },
        ).result_rows
        return tuple(
            StoredResearchEvent(
                event_id=str(row[0]),
                session_id=str(row[1]),
                event_type=str(row[2]),
                stage=str(row[3]),
                status=str(row[4]),
                message=str(row[5]),
                payload=json.loads(str(row[6])),
                duration_ms=int(row[7]),
                occurred_at=row[8],
            )
            for row in rows
        )
