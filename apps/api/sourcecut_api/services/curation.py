from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from threading import RLock

from sourcecut_api.models.curation import (
    CorpusRelease,
    CorpusReleaseCreate,
    CoverageDashboard,
    CurationAuditEvent,
    CurationDecision,
    CurationProposalCreate,
    CurationRecord,
    CurationTarget,
    DerivedRebuild,
    DerivedRebuildRequest,
    ImportRun,
    ImportRunRequest,
    ReleaseComparison,
    ReleaseManifestInput,
    ReviewStatus,
)

IMMUTABLE_SOURCE_FIELDS = {
    "raw_text",
    "raw_tei",
    "source_text",
    "raw_payload",
    "provider_payload",
    "raw_sha256",
    "content_sha256",
    "source_version_id",
    "version_id",
}
ALLOWED_TRANSITIONS = {
    ReviewStatus.DRAFT: {ReviewStatus.REVIEWED, ReviewStatus.REJECTED},
    ReviewStatus.REVIEWED: {ReviewStatus.TRUSTED, ReviewStatus.REJECTED},
    ReviewStatus.TRUSTED: {ReviewStatus.SUPERSEDED},
    ReviewStatus.REJECTED: set(),
    ReviewStatus.SUPERSEDED: set(),
}


class CurationNotFoundError(LookupError):
    pass


class CurationConflictError(RuntimeError):
    pass


class CurationValidationError(ValueError):
    pass


class MemoryCurationStore:
    def __init__(self) -> None:
        self.records: dict[str, list[CurationRecord]] = {}
        self.audit_events: list[CurationAuditEvent] = []
        self.import_runs: dict[str, ImportRun] = {}
        self.releases: dict[str, CorpusRelease] = {}
        self.active_release_id = ""
        self.rebuilds: list[DerivedRebuild] = []
        self.lock = RLock()

    def save_record(self, record: CurationRecord) -> None:
        self.records.setdefault(record.record_id, []).append(record)

    def record_history(self, record_id: str) -> tuple[CurationRecord, ...]:
        return tuple(self.records.get(record_id, ()))

    def latest_records(self) -> tuple[CurationRecord, ...]:
        return tuple(revisions[-1] for revisions in self.records.values())

    def save_audit(self, event: CurationAuditEvent) -> None:
        self.audit_events.append(event)

    def list_audit(self) -> tuple[CurationAuditEvent, ...]:
        return tuple(reversed(self.audit_events))

    def get_import(self, key: str) -> ImportRun | None:
        return self.import_runs.get(key)

    def save_import(self, run: ImportRun) -> None:
        self.import_runs[run.idempotency_key] = run

    def import_exists(self, run_id: str) -> bool:
        return any(run.import_run_id == run_id for run in self.import_runs.values())

    def import_count(self) -> int:
        return len(self.import_runs)

    def save_release(self, release: CorpusRelease) -> None:
        self.releases[release.release_id] = release

    def get_release(self, release_id: str) -> CorpusRelease | None:
        return self.releases.get(release_id)

    def get_active_release_id(self) -> str:
        return self.active_release_id

    def set_active_release(self, release_id: str, actor_id: str, reason: str) -> None:
        del actor_id, reason
        self.active_release_id = release_id

    def save_rebuild(self, rebuild: DerivedRebuild) -> None:
        self.rebuilds.append(rebuild)


class OdysseyCurationService:
    def __init__(self, store: MemoryCurationStore) -> None:
        self._store = store

    def propose(self, request: CurationProposalCreate) -> CurationRecord:
        forbidden = IMMUTABLE_SOURCE_FIELDS & set(request.proposed_changes)
        if forbidden:
            raise CurationValidationError(
                f"raw/source fields are immutable: {', '.join(sorted(forbidden))}"
            )
        now = datetime.now(UTC)
        record = CurationRecord(
            record_id=str(uuid.uuid4()),
            revision=1,
            target_type=request.target_type,
            target_id=request.target_id,
            base_revision_id=request.base_revision_id,
            proposed_changes=request.proposed_changes,
            rationale=request.rationale,
            citations=request.citations,
            status=ReviewStatus.DRAFT,
            proposer_id=request.proposer_id,
            created_at=now,
            updated_at=now,
        )
        with self._store.lock:
            self._store.save_record(record)
            self._audit("proposal_created", request.proposer_id, record, "", "1", {})
        return record

    def decide(self, record_id: str, request: CurationDecision) -> CurationRecord:
        with self._store.lock:
            current = self.get(record_id)
            if current.revision != request.expected_revision:
                raise CurationConflictError("curation revision is stale")
            target_status = ReviewStatus(request.status)
            if target_status not in ALLOWED_TRANSITIONS[current.status]:
                raise CurationValidationError(
                    f"cannot move {current.status.value} to {target_status.value}"
                )
            if target_status == ReviewStatus.TRUSTED:
                self._validate_trust(current)
            updated = current.model_copy(
                update={
                    "revision": current.revision + 1,
                    "status": target_status,
                    "reviewer_id": request.reviewer_id,
                    "review_note": request.review_note,
                    "updated_at": datetime.now(UTC),
                }
            )
            self._store.save_record(updated)
            self._audit(
                "review_decision",
                request.reviewer_id,
                updated,
                str(current.revision),
                str(updated.revision),
                {"from": current.status.value, "to": target_status.value},
            )
            return updated

    def get(self, record_id: str) -> CurationRecord:
        revisions = self._store.record_history(record_id)
        if not revisions:
            raise CurationNotFoundError(record_id)
        return revisions[-1]

    def list_records(
        self, *, status: ReviewStatus | None = None, target: CurationTarget | None = None
    ) -> tuple[CurationRecord, ...]:
        records = list(self._store.latest_records())
        if status is not None:
            records = [record for record in records if record.status == status]
        if target is not None:
            records = [record for record in records if record.target_type == target]
        return tuple(sorted(records, key=lambda record: record.updated_at, reverse=True))

    def history(self, record_id: str) -> tuple[CurationRecord, ...]:
        self.get(record_id)
        return self._store.record_history(record_id)

    def audit(self) -> tuple[CurationAuditEvent, ...]:
        return self._store.list_audit()

    def register_import(self, request: ImportRunRequest) -> ImportRun:
        key = hashlib.sha256(
            f"{request.import_kind}:{request.upstream_revision}:{request.manifest_sha256}".encode()
        ).hexdigest()
        with self._store.lock:
            existing = self._store.get_import(key)
            if existing is not None:
                return existing
            run = ImportRun(
                import_run_id=str(uuid.uuid4()),
                idempotency_key=key,
                import_kind=request.import_kind,
                upstream_revision=request.upstream_revision,
                manifest_sha256=request.manifest_sha256,
                status="registered",
                created_at=datetime.now(UTC),
            )
            self._store.save_import(run)
            self._audit_simple(
                "import_registered", request.actor_id, request.import_kind, run.import_run_id
            )
            return run

    @staticmethod
    def compare(
        current: ReleaseManifestInput, candidate: ReleaseManifestInput
    ) -> ReleaseComparison:
        current_keys = set(current.records)
        candidate_keys = set(candidate.records)
        shared = current_keys & candidate_keys
        return ReleaseComparison(
            added=tuple(sorted(candidate_keys - current_keys)),
            changed=tuple(
                sorted(key for key in shared if current.records[key] != candidate.records[key])
            ),
            removed=tuple(sorted(current_keys - candidate_keys)),
            unchanged_count=sum(current.records[key] == candidate.records[key] for key in shared),
        )

    def create_release(self, request: CorpusReleaseCreate) -> CorpusRelease:
        for run_id in request.import_run_ids:
            if not self._store.import_exists(run_id):
                raise CurationValidationError(f"unknown import run: {run_id}")
        for record_id in request.curation_record_ids:
            self.get(record_id)
        release = CorpusRelease(
            release_id=str(uuid.uuid4()),
            label=request.label,
            upstream_revision=request.upstream_revision,
            source_version_ids=request.source_version_ids,
            curation_record_ids=request.curation_record_ids,
            license_record_ids=request.license_record_ids,
            import_run_ids=request.import_run_ids,
            comparison=request.comparison,
            status="candidate",
            created_by=request.actor_id,
            created_at=datetime.now(UTC),
        )
        with self._store.lock:
            self._store.save_release(release)
            self._audit_simple(
                "release_candidate_created", request.actor_id, "release", release.release_id
            )
        return release

    def promote_release(self, release_id: str, *, actor_id: str, note: str) -> CorpusRelease:
        with self._store.lock:
            release = self._store.get_release(release_id)
            if release is None:
                raise CurationNotFoundError(release_id)
            records = [self.get(record_id) for record_id in release.curation_record_ids]
            untrusted = [
                record.record_id for record in records if record.status != ReviewStatus.TRUSTED
            ]
            if untrusted:
                raise CurationValidationError(
                    f"release contains untrusted curation records: {', '.join(untrusted)}"
                )
            licenses = [self.get(record_id) for record_id in release.license_record_ids]
            if not licenses or any(
                record.target_type != CurationTarget.LICENSE for record in licenses
            ):
                raise CurationValidationError("release requires trusted license validation records")
            previous_id = self._store.get_active_release_id()
            if previous_id:
                previous = self._store.get_release(previous_id)
                if previous is not None:
                    self._store.save_release(previous.model_copy(update={"status": "superseded"}))
            promoted = release.model_copy(
                update={
                    "status": "active",
                    "promoted_by": actor_id,
                    "promoted_at": datetime.now(UTC),
                }
            )
            self._store.save_release(promoted)
            self._store.set_active_release(release_id, actor_id, note)
            self._audit_simple(
                "release_promoted",
                actor_id,
                "release",
                release_id,
                {"note": note, "previous_release_id": previous_id},
            )
            return promoted

    def rollback(self, release_id: str, *, actor_id: str, reason: str) -> CorpusRelease:
        with self._store.lock:
            target = self._store.get_release(release_id)
            if target is None or target.promoted_at is None:
                raise CurationValidationError("rollback target was never promoted")
            current_id = self._store.get_active_release_id()
            if current_id and current_id != release_id:
                current = self._store.get_release(current_id)
                if current is not None:
                    self._store.save_release(current.model_copy(update={"status": "superseded"}))
            active = target.model_copy(update={"status": "active"})
            self._store.save_release(active)
            self._store.set_active_release(release_id, actor_id, reason)
            self._audit_simple(
                "release_rolled_back",
                actor_id,
                "release",
                release_id,
                {"reason": reason, "replaced_release_id": current_id},
            )
            return active

    def rebuild(self, request: DerivedRebuildRequest) -> DerivedRebuild:
        rebuild = DerivedRebuild(
            rebuild_id=str(uuid.uuid4()),
            layer=request.layer,
            source_version_ids=request.source_version_ids,
            created_at=datetime.now(UTC),
        )
        with self._store.lock:
            self._store.save_rebuild(rebuild)
            self._audit_simple(
                "derived_rebuild_queued",
                request.actor_id,
                request.layer,
                rebuild.rebuild_id,
                {"source_mutations": 0},
            )
        return rebuild

    def coverage(self) -> CoverageDashboard:
        records = self.list_records()
        trusted = sum(record.status == ReviewStatus.TRUSTED for record in records)
        return CoverageDashboard(
            by_target={
                target.value: sum(record.target_type == target for record in records)
                for target in CurationTarget
            },
            by_status={
                status.value: sum(record.status == status for record in records)
                for status in ReviewStatus
            },
            trusted_percent=round(trusted / len(records) * 100, 1) if records else 0,
            license_records_trusted=sum(
                record.target_type == CurationTarget.LICENSE
                and record.status == ReviewStatus.TRUSTED
                for record in records
            ),
            unresolved_records=sum(
                record.status in {ReviewStatus.DRAFT, ReviewStatus.REVIEWED} for record in records
            ),
            import_runs=self._store.import_count(),
            active_release_id=self._store.get_active_release_id(),
            generated_at=datetime.now(UTC),
        )

    @staticmethod
    def _validate_trust(record: CurationRecord) -> None:
        if not record.citations:
            raise CurationValidationError("trusted records require citations")
        if record.target_type == CurationTarget.LICENSE:
            required = {"license_id", "display_decision", "source_url"}
            missing = required - set(record.proposed_changes)
            if missing:
                raise CurationValidationError(
                    f"trusted license review is missing: {', '.join(sorted(missing))}"
                )

    def _audit(
        self,
        action: str,
        actor_id: str,
        record: CurationRecord,
        before: str,
        after: str,
        detail: dict[str, object],
    ) -> None:
        self._store.save_audit(
            CurationAuditEvent(
                audit_id=str(uuid.uuid4()),
                action=action,
                actor_id=actor_id,
                target_type=record.target_type.value,
                target_id=record.record_id,
                before_revision=before,
                after_revision=after,
                detail=detail,
                occurred_at=datetime.now(UTC),
            )
        )

    def _audit_simple(
        self,
        action: str,
        actor_id: str,
        target_type: str,
        target_id: str,
        detail: dict[str, object] | None = None,
    ) -> None:
        self._store.save_audit(
            CurationAuditEvent(
                audit_id=str(uuid.uuid4()),
                action=action,
                actor_id=actor_id,
                target_type=target_type,
                target_id=target_id,
                before_revision="",
                after_revision="",
                detail=detail or {},
                occurred_at=datetime.now(UTC),
            )
        )
