from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sourcecut_api.integrations.google_video import (
    SHOT_BRIEF_PROMPT_VERSION,
    ShotBriefProducer,
    VideoCritic,
    VideoGenerator,
    create_google_video_clients,
)
from sourcecut_api.models import (
    BoardSection,
    ConsistencyLabel,
    ConsistencyReport,
    ConsistencyResult,
    CorrectionApproval,
    GenerationApproval,
    PrevisJob,
    PrevisJobEnvelope,
    PrevisJobStatus,
    ResearchBoard,
    RightsStatus,
    ShotBrief,
    ShotBriefContent,
    ShotBriefEnvelope,
    ShotBriefRequest,
)
from sourcecut_api.storage import PrevisStore, create_previs_store
from sourcecut_api.telemetry import add_counter, observe_histogram, telemetry_span

REQUIRED_EXCLUSIONS = (
    "wagons",
    "modern vehicles",
    "paved roads",
    "modern buildings",
)
GUARDED_TERMS = (
    "automobile",
    "building",
    "paved road",
    "rifle",
    "uniform",
    "wagon",
)
DISCLOSURE = "AI-generated previsualization — not historical evidence"


class PrevisError(RuntimeError):
    pass


class PrevisNotFoundError(PrevisError):
    pass


class PrevisBlockedError(PrevisError):
    pass


class PrevisConflictError(PrevisError):
    pass


@dataclass(frozen=True, slots=True)
class PrevisSettings:
    enabled: bool = False
    video_model: str = "replace-with-enabled-veo-model"
    review_model: str = "gemini-2.5-flash"
    storage_uri: str = "data/previs"
    max_duration_seconds: int = 8
    max_generations_per_brief: int = 2
    max_estimated_cost_usd: float = 10
    estimated_cost_per_second_usd: float | None = None

    @classmethod
    def from_env(cls) -> PrevisSettings:
        raw_rate = os.getenv(
            "SOURCECUT_VIDEO_ESTIMATED_COST_PER_SECOND_USD",
            "replace-with-current-rate",
        )
        rate = None if "replace-" in raw_rate else float(raw_rate)
        settings = cls(
            enabled=_env_bool("SOURCECUT_VIDEO_ENABLED", False),
            video_model=os.getenv(
                "SOURCECUT_VIDEO_MODEL", "replace-with-enabled-veo-model"
            ),
            review_model=os.getenv(
                "SOURCECUT_VIDEO_REVIEW_MODEL", "gemini-2.5-flash"
            ),
            storage_uri=os.getenv("SOURCECUT_VIDEO_STORAGE_URI", "data/previs"),
            max_duration_seconds=int(
                os.getenv("SOURCECUT_VIDEO_MAX_DURATION_SECONDS", "8")
            ),
            max_generations_per_brief=int(
                os.getenv("SOURCECUT_VIDEO_MAX_GENERATIONS_PER_BRIEF", "2")
            ),
            max_estimated_cost_usd=float(
                os.getenv("SOURCECUT_VIDEO_MAX_ESTIMATED_COST_USD", "10")
            ),
            estimated_cost_per_second_usd=rate,
        )
        if not 1 <= settings.max_duration_seconds <= 8:
            raise ValueError("SOURCECUT_VIDEO_MAX_DURATION_SECONDS must be between 1 and 8")
        if not 1 <= settings.max_generations_per_brief <= 2:
            raise ValueError(
                "SOURCECUT_VIDEO_MAX_GENERATIONS_PER_BRIEF must be between 1 and 2"
            )
        if settings.max_estimated_cost_usd <= 0:
            raise ValueError("SOURCECUT_VIDEO_MAX_ESTIMATED_COST_USD must be positive")
        if rate is not None and rate <= 0:
            raise ValueError(
                "SOURCECUT_VIDEO_ESTIMATED_COST_PER_SECOND_USD must be positive"
            )
        return settings

    @property
    def generation_blockers(self) -> tuple[str, ...]:
        blockers: list[str] = []
        if not self.enabled:
            blockers.append("Paid video generation is disabled.")
        if not self.video_model or "replace-" in self.video_model:
            blockers.append("Configure an enabled Veo model.")
        if self.estimated_cost_per_second_usd is None:
            blockers.append("Configure the current estimated cost per second.")
        return tuple(blockers)

    def estimated_cost(self, duration_seconds: int) -> float | None:
        if self.estimated_cost_per_second_usd is None:
            return None
        return round(duration_seconds * self.estimated_cost_per_second_usd, 2)


class PrevisService:
    def __init__(
        self,
        settings: PrevisSettings,
        store: PrevisStore,
        producer: ShotBriefProducer,
        generator: VideoGenerator,
        critic: VideoCritic,
        *,
        archive_root: Path = Path("data/archive-cache/loc"),
    ) -> None:
        self._settings = settings
        self._store = store
        self._producer = producer
        self._generator = generator
        self._critic = critic
        self._archive_root = archive_root.resolve()

    async def create_brief(
        self,
        session_id: str,
        board: ResearchBoard,
        request: ShotBriefRequest,
    ) -> ShotBriefEnvelope:
        if request.duration_seconds > self._settings.max_duration_seconds:
            raise PrevisBlockedError(
                f"Duration exceeds the {self._settings.max_duration_seconds}-second limit."
            )
        section = _find_section(board, request.board_section_title)
        references = self._resolve_references(section, request.reference_asset_ids)
        context = _producer_context(session_id, board, section, request, references)
        with telemetry_span(
            "sourcecut.previs.brief.create",
            {
                "sourcecut.research.session_id": session_id,
                "sourcecut.previs.strictness": request.strictness,
                "sourcecut.previs.shot_type": request.shot_type,
            },
        ):
            content = await self._producer.produce(context)
            content = _add_required_exclusions(content)
            _validate_content(content, section, request.strictness.value)
            brief = ShotBrief(
                shot_brief_id=str(uuid.uuid4()),
                research_session_id=session_id,
                board_section_id=_section_id(section),
                board_fingerprint=_fingerprint(board.model_dump(mode="json")),
                shot_type=request.shot_type,
                strictness=request.strictness,
                duration_seconds=request.duration_seconds,
                aspect_ratio=request.aspect_ratio,
                generate_audio=False,
                reference_asset_ids=tuple(asset.asset.asset_id for asset in references),
                producer_model=self._producer.model,
                prompt_version=SHOT_BRIEF_PROMPT_VERSION,
                created_at=_now(),
                content=content,
            )
            self._store.save_brief(brief)
            self._store.save_references(
                brief.shot_brief_id,
                tuple(_reference_payload(asset.asset.asset_id, asset.asset.thumbnail_path)
                      for asset in references),
            )
        add_counter(
            "sourcecut.previs.briefs",
            1,
            {"strictness": request.strictness.value, "status": "success"},
        )
        return self._brief_envelope(brief)

    async def generate(
        self, brief_id: str, approval: GenerationApproval
    ) -> PrevisJobEnvelope:
        brief = self._load_brief(brief_id)
        if not approval.approved:
            raise PrevisBlockedError("Explicit paid-generation approval is required.")
        if approval.brief_fingerprint != brief_fingerprint(brief):
            raise PrevisConflictError("The shot brief changed; review and approve it again.")
        self._assert_generation_ready(brief)
        return await self._start_job(brief, generation_count=1)

    async def get_job(self, job_id: str) -> PrevisJobEnvelope:
        job = self._load_job(job_id)
        if job.status is not PrevisJobStatus.GENERATING:
            return self._job_envelope(job)
        started = _now()
        with telemetry_span(
            "sourcecut.previs.provider.poll",
            {
                "sourcecut.previs.job_id": job.job_id,
                "gen_ai.request.model": job.model,
            },
        ):
            result = await self._generator.poll(job.provider_operation_name)
        observe_histogram(
            "sourcecut.previs.provider.poll.duration",
            (_now() - started).total_seconds() * 1000,
        )
        if not result.done:
            return self._job_envelope(job)
        if result.safe_error:
            status = PrevisJobStatus.BLOCKED if result.blocked else PrevisJobStatus.FAILED
            job = job.model_copy(
                update={
                    "status": status,
                    "safe_error": result.safe_error,
                    "updated_at": _now(),
                }
            )
            self._store.save_job(job)
            add_counter("sourcecut.previs.generations", 1, {"status": status.value})
            return self._job_envelope(job)
        if result.video_bytes:
            output_uri = self._store.save_video(job.job_id, result.video_bytes)
        elif result.output_uri:
            output_uri = self._store.materialize_provider_video(
                job.job_id, result.output_uri
            )
        else:
            raise PrevisConflictError("Completed video operation returned no output.")
        job = job.model_copy(
            update={
                "status": PrevisJobStatus.COMPLETE,
                "output_uri": output_uri,
                "updated_at": _now(),
            }
        )
        self._store.save_job(job)
        add_counter("sourcecut.previs.generations", 1, {"status": "complete"})
        return self._job_envelope(job)

    async def review(self, job_id: str) -> PrevisJobEnvelope:
        job = self._load_job(job_id)
        existing = self._store.load_report(job_id)
        if existing is not None:
            return self._job_envelope(job, existing)
        if job.status is not PrevisJobStatus.COMPLETE or not job.output_uri:
            raise PrevisConflictError("The generated clip must complete before review.")
        brief = self._load_brief(job.shot_brief_id)
        video, mime_type = self._store.read_video(job.job_id)
        reviewing = job.model_copy(
            update={"status": PrevisJobStatus.REVIEWING, "updated_at": _now()}
        )
        self._store.save_job(reviewing)
        try:
            with telemetry_span(
                "sourcecut.previs.review",
                {
                    "sourcecut.previs.job_id": job.job_id,
                    "gen_ai.request.model": self._critic.model,
                },
            ):
                report = await self._critic.review(
                    reviewing, brief, video, mime_type
                )
                report = report.model_copy(update={"reviewed_at": _now()})
                _validate_report(report, brief)
                self._store.save_report(report)
            completed = reviewing.model_copy(
                update={"status": PrevisJobStatus.COMPLETE, "updated_at": _now()}
            )
            self._store.save_job(completed)
        except Exception:
            completed = reviewing.model_copy(
                update={
                    "status": PrevisJobStatus.COMPLETE,
                    "updated_at": _now(),
                    "safe_error": "The clip was generated, but its consistency review failed.",
                }
            )
            self._store.save_job(completed)
            raise
        for label in ConsistencyLabel:
            add_counter(
                "sourcecut.previs.review.findings",
                sum(item.label is label for item in report.findings),
                {"label": label.value},
            )
        return self._job_envelope(completed, report)

    async def correct(
        self, job_id: str, approval: CorrectionApproval
    ) -> PrevisJobEnvelope:
        parent = self._load_job(job_id)
        if not approval.approved:
            raise PrevisBlockedError("Explicit corrected-generation approval is required.")
        if approval.job_fingerprint != job_fingerprint(parent):
            raise PrevisConflictError("The reviewed job changed; approve the correction again.")
        if parent.status is not PrevisJobStatus.COMPLETE:
            raise PrevisConflictError("Only a completed clip can be corrected.")
        report = self._store.load_report(parent.job_id)
        if report is None:
            raise PrevisConflictError("Review the generated clip before correction.")
        if report.overall_result is ConsistencyResult.CONSISTENT:
            raise PrevisConflictError("A consistent clip does not need correction.")
        if not report.correction_instructions:
            raise PrevisConflictError("The review contains no correction instructions.")
        generation_count = parent.generation_count + 1
        if generation_count > self._settings.max_generations_per_brief:
            raise PrevisBlockedError("The correction generation limit has been reached.")
        brief = self._load_brief(parent.shot_brief_id)
        self._assert_generation_ready(brief)
        add_counter("sourcecut.previs.corrections", 1)
        return await self._start_job(
            brief,
            generation_count=generation_count,
            parent_job_id=parent.job_id,
            correction_instructions=report.correction_instructions,
        )

    def read_video(self, job_id: str) -> tuple[bytes, str]:
        job = self._load_job(job_id)
        if job.status is not PrevisJobStatus.COMPLETE or not job.output_uri:
            raise PrevisConflictError("Generated video is not ready.")
        return self._store.read_video(job_id)

    async def _start_job(
        self,
        brief: ShotBrief,
        *,
        generation_count: int,
        parent_job_id: str | None = None,
        correction_instructions: tuple[str, ...] = (),
    ) -> PrevisJobEnvelope:
        job_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"sourcecut:{brief.shot_brief_id}:{generation_count}:{parent_job_id or 'root'}",
            )
        )
        try:
            return self._job_envelope(self._store.load_job(job_id))
        except FileNotFoundError:
            pass
        cost = self._settings.estimated_cost(brief.duration_seconds)
        if cost is None:
            raise PrevisBlockedError("Estimated generation cost is not configured.")
        request_fingerprint = _fingerprint(
            {
                "brief_fingerprint": brief_fingerprint(brief),
                "model": self._settings.video_model,
                "generation_count": generation_count,
                "parent_job_id": parent_job_id,
                "corrections": correction_instructions,
            }
        )
        now = _now()
        job = PrevisJob(
            job_id=job_id,
            shot_brief_id=brief.shot_brief_id,
            status=PrevisJobStatus.QUEUED,
            parent_job_id=parent_job_id,
            model=self._settings.video_model,
            request_fingerprint=request_fingerprint,
            estimated_cost_usd=cost,
            generation_count=generation_count,
            created_at=now,
            updated_at=now,
        )
        self._store.save_job(job)
        references = self._store.read_references(
            brief.shot_brief_id, brief.reference_asset_ids
        )
        try:
            with telemetry_span(
                "sourcecut.previs.provider.submit",
                {
                    "sourcecut.previs.job_id": job.job_id,
                    "sourcecut.previs.generation_count": generation_count,
                    "sourcecut.previs.estimated_cost_usd": cost,
                    "gen_ai.request.model": self._settings.video_model,
                },
            ):
                operation_name = await self._generator.submit(
                    job.job_id,
                    brief,
                    references,
                    output_gcs_uri=self._store.provider_output_prefix(job.job_id),
                    correction_instructions=correction_instructions,
                )
            job = job.model_copy(
                update={
                    "status": PrevisJobStatus.GENERATING,
                    "provider_operation_name": operation_name,
                    "updated_at": _now(),
                }
            )
        except Exception as error:
            job = job.model_copy(
                update={
                    "status": PrevisJobStatus.FAILED,
                    "safe_error": f"Provider submission failed ({type(error).__name__}).",
                    "updated_at": _now(),
                }
            )
        self._store.save_job(job)
        return self._job_envelope(job)

    def _resolve_references(
        self, section: BoardSection, asset_ids: tuple[str, ...]
    ) -> tuple[Any, ...]:
        available = {item.asset.asset_id: item for item in section.assets}
        references: list[Any] = []
        for asset_id in asset_ids:
            asset = available.get(asset_id)
            if asset is None:
                raise PrevisBlockedError(
                    "A selected reference is not part of the stored board section."
                )
            if asset.asset.rights_status is not RightsStatus.PUBLIC_DOMAIN:
                raise PrevisBlockedError(
                    "Previs references must be explicitly public domain."
                )
            _approved_reference_path(asset.asset.thumbnail_path, self._archive_root)
            references.append(asset)
        return tuple(references[:3])

    def _assert_generation_ready(self, brief: ShotBrief) -> None:
        blockers = self._settings.generation_blockers
        if blockers:
            raise PrevisBlockedError(" ".join(blockers))
        if brief.duration_seconds > self._settings.max_duration_seconds:
            raise PrevisBlockedError("Shot brief exceeds the configured duration limit.")
        cost = self._settings.estimated_cost(brief.duration_seconds)
        if cost is None or cost > self._settings.max_estimated_cost_usd:
            raise PrevisBlockedError("Estimated generation cost exceeds the configured limit.")

    def _brief_envelope(self, brief: ShotBrief) -> ShotBriefEnvelope:
        cost = self._settings.estimated_cost(brief.duration_seconds)
        blockers = list(self._settings.generation_blockers)
        if cost is not None and cost > self._settings.max_estimated_cost_usd:
            blockers.append("Estimated generation cost exceeds the configured limit.")
        return ShotBriefEnvelope(
            brief=brief,
            brief_fingerprint=brief_fingerprint(brief),
            estimated_cost_usd=cost,
            can_generate=not blockers,
            blockers=tuple(blockers),
        )

    def _job_envelope(
        self, job: PrevisJob, report: ConsistencyReport | None = None
    ) -> PrevisJobEnvelope:
        if report is None:
            report = self._store.load_report(job.job_id)
        video_url = (
            f"/api/previs/jobs/{job.job_id}/video"
            if job.status is PrevisJobStatus.COMPLETE and job.output_uri
            else ""
        )
        return PrevisJobEnvelope(
            job=job,
            job_fingerprint=job_fingerprint(job),
            report=report,
            video_url=video_url,
        )

    def _load_brief(self, brief_id: str) -> ShotBrief:
        try:
            return self._store.load_brief(brief_id)
        except (FileNotFoundError, ValueError) as error:
            raise PrevisNotFoundError("Shot brief was not found.") from error

    def _load_job(self, job_id: str) -> PrevisJob:
        try:
            return self._store.load_job(job_id)
        except (FileNotFoundError, ValueError) as error:
            raise PrevisNotFoundError("Previs job was not found.") from error


def create_previs_service() -> PrevisService:
    settings = PrevisSettings.from_env()
    producer, generator, critic = create_google_video_clients()
    return PrevisService(
        settings,
        create_previs_store(settings.storage_uri),
        producer,
        generator,
        critic,
        archive_root=Path(os.getenv("SOURCECUT_ARCHIVE_CACHE_ROOT", "data/archive-cache/loc")),
    )


def brief_fingerprint(brief: ShotBrief) -> str:
    return _fingerprint(brief.model_dump(mode="json"))


def job_fingerprint(job: PrevisJob) -> str:
    return _fingerprint(job.model_dump(mode="json"))


def _producer_context(
    session_id: str,
    board: ResearchBoard,
    section: BoardSection,
    request: ShotBriefRequest,
    references: tuple[Any, ...],
) -> dict[str, Any]:
    evidence = _section_evidence(section)
    return {
        "research_session_id": session_id,
        "board_title": board.title,
        "section_title": section.title,
        "controls": {
            "shot_type": request.shot_type.value,
            "strictness": request.strictness.value,
            "duration_seconds": request.duration_seconds,
            "aspect_ratio": request.aspect_ratio,
            "generate_audio": False,
        },
        "evidence": [item.model_dump(mode="json") for item in evidence],
        "reference_assets": [
            {
                "asset_id": item.asset.asset_id,
                "title": item.asset.title,
                "asset_type": item.asset.asset_type,
                "historical_relationship": item.historical_relationship.value,
                "production_use": item.production_use,
            }
            for item in references
        ],
        "required_exclusions": REQUIRED_EXCLUSIONS,
    }


def _validate_content(
    content: ShotBriefContent, section: BoardSection, strictness: str
) -> None:
    evidence = _section_evidence(section)
    observation_ids = {item.observation_id for item in evidence}
    passage_ids = {item.passage_id for item in evidence}
    for detail in content.supported_details:
        if not set(detail.observation_ids) <= observation_ids:
            raise PrevisBlockedError("Shot brief cited an unknown observation.")
        if not set(detail.passage_ids) <= passage_ids:
            raise PrevisBlockedError("Shot brief cited an unknown passage.")
    if strictness == "strict" and content.interpretive_additions:
        raise PrevisBlockedError("Strict shot briefs cannot add interpretive details.")
    evidence_text = " ".join(
        f"{item.canonical_term} {item.source_quote}" for item in evidence
    ).casefold()
    positive = content.positive_prompt.casefold()
    for term in GUARDED_TERMS:
        if term in positive and term not in evidence_text:
            raise PrevisBlockedError(f"Shot brief added unsupported detail: {term}.")


def _validate_report(report: ConsistencyReport, brief: ShotBrief) -> None:
    observation_ids = {
        value
        for detail in brief.content.supported_details
        for value in detail.observation_ids
    }
    passage_ids = {
        value for detail in brief.content.supported_details for value in detail.passage_ids
    }
    for finding in report.findings:
        if not set(finding.observation_ids) <= observation_ids:
            raise PrevisBlockedError("Consistency report cited an unknown observation.")
        if not set(finding.passage_ids) <= passage_ids:
            raise PrevisBlockedError("Consistency report cited an unknown passage.")
    has_unsupported = any(
        item.label is ConsistencyLabel.UNSUPPORTED for item in report.findings
    )
    if has_unsupported and not report.correction_instructions:
        raise PrevisBlockedError(
            "Unsupported consistency findings require correction instructions."
        )


def _add_required_exclusions(content: ShotBriefContent) -> ShotBriefContent:
    exclusions = tuple(dict.fromkeys((*content.excluded_details, *REQUIRED_EXCLUSIONS)))
    negative = content.negative_prompt
    missing = [item for item in REQUIRED_EXCLUSIONS if item.casefold() not in negative.casefold()]
    if missing:
        negative = ", ".join((negative, *missing))
    return content.model_copy(
        update={"excluded_details": exclusions, "negative_prompt": negative}
    )


def _section_evidence(section: BoardSection) -> tuple[Any, ...]:
    unique: dict[str, Any] = {}
    for asset in section.assets:
        for evidence in asset.evidence:
            unique.setdefault(evidence.observation_id, evidence)
    return tuple(unique.values())


def _find_section(board: ResearchBoard, title: str) -> BoardSection:
    for section in board.sections:
        if section.title == title:
            return section
    raise PrevisNotFoundError("Research Board section was not found.")


def _section_id(section: BoardSection) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", section.title.casefold()).strip("-")
    return f"{slug}-{hashlib.sha256(section.title.encode()).hexdigest()[:8]}"


def _approved_reference_path(value: str, root: Path) -> Path:
    path = Path(value).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise PrevisBlockedError("Selected reference does not have an approved cached image.")
    return path


def _reference_payload(asset_id: str, value: str) -> tuple[str, bytes, str]:
    path = Path(value).resolve()
    mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return asset_id, path.read_bytes(), mime_type


def _fingerprint(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def _now() -> datetime:
    return datetime.now(UTC)
