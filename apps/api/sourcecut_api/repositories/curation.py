from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from threading import RLock
from typing import TYPE_CHECKING

from sourcecut_api.models.curation import (
    CorpusRelease,
    CurationAuditEvent,
    CurationRecord,
    DerivedRebuild,
    ImportRun,
)

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client

SYNC_INSERT = {"async_insert": 1, "wait_for_async_insert": 1}


class ClickHouseCurationStore:
    def __init__(self, client: Client) -> None:
        self._client = client
        self.lock = RLock()

    def save_record(self, record: CurationRecord) -> None:
        self._client.insert(
            "curation_records",
            [
                [
                    record.record_id,
                    record.revision,
                    record.target_type,
                    record.target_id,
                    record.base_revision_id,
                    json.dumps(record.proposed_changes, separators=(",", ":"), sort_keys=True),
                    record.rationale,
                    list(record.citations),
                    record.status,
                    record.proposer_id,
                    record.reviewer_id,
                    record.review_note,
                    record.created_at,
                    record.updated_at,
                ]
            ],
            column_names=[
                "record_id",
                "revision",
                "target_type",
                "target_id",
                "base_revision_id",
                "proposed_changes_json",
                "rationale",
                "citations",
                "status",
                "proposer_id",
                "reviewer_id",
                "review_note",
                "created_at",
                "updated_at",
            ],
            settings=SYNC_INSERT,
        )

    def record_history(self, record_id: str) -> tuple[CurationRecord, ...]:
        rows = self._client.query(
            f"{_RECORD_SELECT}\nWHERE record_id = {{record_id:String}} ORDER BY revision",
            parameters={"record_id": record_id},
        ).result_rows
        return tuple(_record(row) for row in rows)

    def latest_records(self) -> tuple[CurationRecord, ...]:
        rows = self._client.query(
            f"{_RECORD_SELECT}\nORDER BY record_id, revision DESC LIMIT 1 BY record_id"
        ).result_rows
        return tuple(_record(row) for row in rows)

    def save_audit(self, event: CurationAuditEvent) -> None:
        self._client.insert(
            "curation_audit_log",
            [
                [
                    event.audit_id,
                    event.action,
                    event.actor_id,
                    event.target_type,
                    event.target_id,
                    event.before_revision,
                    event.after_revision,
                    json.dumps(event.detail, separators=(",", ":"), sort_keys=True),
                    event.occurred_at,
                ]
            ],
            column_names=[
                "audit_id",
                "action",
                "actor_id",
                "target_type",
                "target_id",
                "before_revision",
                "after_revision",
                "detail_json",
                "occurred_at",
            ],
            settings=SYNC_INSERT,
        )

    def list_audit(self) -> tuple[CurationAuditEvent, ...]:
        rows = self._client.query(
            """
SELECT audit_id, action, actor_id, target_type, target_id, before_revision,
       after_revision, detail_json, occurred_at
FROM curation_audit_log
ORDER BY occurred_at DESC, audit_id DESC
LIMIT 1000
""".strip()
        ).result_rows
        return tuple(
            CurationAuditEvent(
                audit_id=str(row[0]),
                action=str(row[1]),
                actor_id=str(row[2]),
                target_type=str(row[3]),
                target_id=str(row[4]),
                before_revision=str(row[5]),
                after_revision=str(row[6]),
                detail=json.loads(str(row[7])),
                occurred_at=row[8],
            )
            for row in rows
        )

    def get_import(self, key: str) -> ImportRun | None:
        rows = self._client.query(
            f"{_IMPORT_SELECT}\nWHERE idempotency_key = {{key:String}} LIMIT 1",
            parameters={"key": key},
        ).result_rows
        return _import(row=rows[0]) if rows else None

    def save_import(self, run: ImportRun) -> None:
        self._client.insert(
            "curation_import_runs",
            [
                [
                    run.import_run_id,
                    run.idempotency_key,
                    run.import_kind,
                    run.upstream_revision,
                    run.manifest_sha256,
                    run.status,
                    run.created_at,
                ]
            ],
            column_names=[
                "import_run_id",
                "idempotency_key",
                "import_kind",
                "upstream_revision",
                "manifest_sha256",
                "status",
                "created_at",
            ],
            settings=SYNC_INSERT,
        )

    def import_exists(self, run_id: str) -> bool:
        rows = self._client.query(
            "SELECT count() FROM curation_import_runs WHERE import_run_id = {run_id:String}",
            parameters={"run_id": run_id},
        ).result_rows
        return bool(rows and int(rows[0][0]))

    def import_count(self) -> int:
        rows = self._client.query(
            "SELECT uniqExact(idempotency_key) FROM curation_import_runs"
        ).result_rows
        return int(rows[0][0]) if rows else 0

    def save_release(self, release: CorpusRelease) -> None:
        self._client.insert(
            "corpus_releases",
            [
                [
                    release.release_id,
                    release.model_dump_json(),
                    release.status,
                    release.upstream_revision,
                    release.created_at,
                    release.promoted_at,
                    release.promoted_at or release.created_at,
                ]
            ],
            column_names=[
                "release_id",
                "release_json",
                "status",
                "upstream_revision",
                "created_at",
                "promoted_at",
                "updated_at",
            ],
            settings=SYNC_INSERT,
        )

    def get_release(self, release_id: str) -> CorpusRelease | None:
        rows = self._client.query(
            """
SELECT release_json FROM corpus_releases FINAL
WHERE release_id = {release_id:String}
LIMIT 1
""".strip(),
            parameters={"release_id": release_id},
        ).result_rows
        return CorpusRelease.model_validate_json(str(rows[0][0])) if rows else None

    def get_active_release_id(self) -> str:
        rows = self._client.query(
            """
SELECT release_id FROM release_promotions
ORDER BY occurred_at DESC, promotion_id DESC
LIMIT 1
""".strip()
        ).result_rows
        return str(rows[0][0]) if rows else ""

    def set_active_release(self, release_id: str, actor_id: str, reason: str) -> None:
        self._client.insert(
            "release_promotions",
            [[str(uuid.uuid4()), release_id, "activate", actor_id, reason, _now()]],
            column_names=[
                "promotion_id",
                "release_id",
                "action",
                "actor_id",
                "reason",
                "occurred_at",
            ],
            settings=SYNC_INSERT,
        )

    def save_rebuild(self, rebuild: DerivedRebuild) -> None:
        self._client.insert(
            "derived_rebuild_jobs",
            [
                [
                    rebuild.rebuild_id,
                    rebuild.layer,
                    list(rebuild.source_version_ids),
                    rebuild.source_mutations,
                    rebuild.status,
                    rebuild.created_at,
                ]
            ],
            column_names=[
                "rebuild_id",
                "layer",
                "source_version_ids",
                "source_mutations",
                "status",
                "created_at",
            ],
            settings=SYNC_INSERT,
        )


class LazyClickHouseCurationStore:
    def __init__(self, factory: Callable[[], Client]) -> None:
        self._factory = factory
        self._resolved_store: ClickHouseCurationStore | None = None
        self.lock = RLock()

    def __getattr__(self, name: str) -> object:
        with self.lock:
            if self._resolved_store is None:
                self._resolved_store = ClickHouseCurationStore(self._factory())
            return getattr(self._resolved_store, name)


_RECORD_SELECT = """
SELECT record_id, revision, target_type, target_id, base_revision_id,
       proposed_changes_json, rationale, citations, status, proposer_id,
       reviewer_id, review_note, created_at, updated_at
FROM curation_records
""".strip()
_IMPORT_SELECT = """
SELECT import_run_id, idempotency_key, import_kind, upstream_revision,
       manifest_sha256, status, created_at
FROM curation_import_runs FINAL
""".strip()


def _record(row: tuple[object, ...]) -> CurationRecord:
    return CurationRecord(
        record_id=str(row[0]),
        revision=int(row[1]),
        target_type=str(row[2]),
        target_id=str(row[3]),
        base_revision_id=str(row[4]),
        proposed_changes=json.loads(str(row[5])),
        rationale=str(row[6]),
        citations=tuple(str(value) for value in row[7]),
        status=str(row[8]),
        proposer_id=str(row[9]),
        reviewer_id=str(row[10]),
        review_note=str(row[11]),
        created_at=row[12],
        updated_at=row[13],
    )


def _import(row: tuple[object, ...]) -> ImportRun:
    return ImportRun(
        import_run_id=str(row[0]),
        idempotency_key=str(row[1]),
        import_kind=str(row[2]),
        upstream_revision=str(row[3]),
        manifest_sha256=str(row[4]),
        status=str(row[5]),
        created_at=row[6],
    )


def _now() -> datetime:
    return datetime.now(UTC)
