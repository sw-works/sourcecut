from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from sourcecut_api.integrations.google_video import (
    GeminiShotBriefProducer,
    VideoPoll,
)
from sourcecut_api.models import (
    BoardConfidence,
    BoardMediaAsset,
    BoardSection,
    ConsistencyFinding,
    ConsistencyLabel,
    ConsistencyReport,
    ConsistencyResult,
    CorrectionApproval,
    EvidenceCitation,
    GenerationApproval,
    HistoricalRelationship,
    ResearchBoard,
    RightsStatus,
    ShotBriefContent,
    ShotBriefRequest,
    SupportedDetail,
    VerifiedAsset,
)
from sourcecut_api.services.previs import (
    PrevisBlockedError,
    PrevisService,
    PrevisSettings,
    brief_fingerprint,
    job_fingerprint,
)
from sourcecut_api.storage.previs import FilePrevisStore, GcsPrevisStore


class FakeProducer:
    model = "gemini-test-producer"

    def __init__(self, *, interpretive: bool = False, unknown_id: bool = False) -> None:
        self.interpretive = interpretive
        self.unknown_id = unknown_id
        self.contexts: list[dict[str, Any]] = []

    async def produce(self, context: dict[str, Any]) -> ShotBriefContent:
        self.contexts.append(context)
        evidence = context["evidence"][0]
        observation_id = "invented" if self.unknown_id else evidence["observation_id"]
        return ShotBriefContent(
            purpose="Evidence-constrained production previsualization.",
            setting="A steep, forested Bitterroot mountain trail in September 1805.",
            action="Expedition horses move carefully through early snow.",
            composition="Wide establishing view with the party small against the terrain.",
            camera_motion="Slow lateral tracking movement.",
            ambience="Cold, muted daylight.",
            supported_details=(
                SupportedDetail(
                    detail="Horses crossing steep terrain in snow.",
                    observation_ids=(observation_id,),
                    passage_ids=(evidence["passage_id"],),
                ),
            ),
            interpretive_additions=("dark brown horse coats",) if self.interpretive else (),
            excluded_details=("permanent structures",),
            positive_prompt=(
                "Wide production previsualization of horses crossing steep forested mountain "
                "terrain in early snow, muted daylight, slow lateral tracking shot."
            ),
            negative_prompt="wagons, modern clothing",
        )


class FakeGeminiModels:
    def __init__(self) -> None:
        self.config: Any = None

    def generate_content(self, *, model: str, contents: str, config: Any) -> Any:
        del model, contents
        self.config = config
        return type("Response", (), {"parsed": FakeProducerContent(), "text": None})()


class FakeProducerContent(dict):
    def __init__(self) -> None:
        detail = {
            "detail": "Horses cross snowy terrain.",
            "observation_ids": ["observation:snow-horses"],
            "passage_ids": ["passage:1805-09-16"],
        }
        super().__init__(
            purpose="Production previsualization.",
            setting="A snowy mountain trail.",
            action="Horses cross the trail.",
            composition="Wide landscape frame.",
            camera_motion="Slow lateral tracking.",
            ambience="Cold daylight.",
            supported_details=[detail],
            interpretive_additions=[],
            excluded_details=["wagons"],
            positive_prompt="Wide previsualization of horses on a snowy mountain trail.",
            negative_prompt="wagons, modern clothing",
        )


class FakeGenerator:
    def __init__(self, polls: list[VideoPoll] | None = None) -> None:
        self.submissions: list[dict[str, Any]] = []
        self.polls = polls or [VideoPoll(done=True, video_bytes=b"fake-mp4")]

    async def submit(
        self,
        job_id: str,
        brief: Any,
        reference_images: tuple[tuple[bytes, str], ...],
        *,
        output_gcs_uri: str | None,
        correction_instructions: tuple[str, ...] = (),
    ) -> str:
        self.submissions.append(
            {
                "job_id": job_id,
                "brief": brief,
                "reference_images": reference_images,
                "output_gcs_uri": output_gcs_uri,
                "corrections": correction_instructions,
            }
        )
        return f"operations/{job_id}"

    async def poll(self, operation_name: str) -> VideoPoll:
        del operation_name
        return self.polls.pop(0)


class WagonCritic:
    model = "gemini-test-critic"

    async def review(
        self, job: Any, brief: Any, video: bytes, mime_type: str
    ) -> ConsistencyReport:
        del brief, video, mime_type
        return ConsistencyReport(
            job_id=job.job_id,
            overall_result=ConsistencyResult.UNSUPPORTED,
            findings=(
                ConsistencyFinding(
                    label=ConsistencyLabel.UNSUPPORTED,
                    visible_detail="A wagon is visible behind the horses.",
                    approximate_time_range="00:04–00:05",
                    severity="critical",
                    rationale="No selected evidence supports wagon transportation.",
                ),
            ),
            correction_instructions=("Remove the wagon; retain horses on the trail.",),
            critic_model=self.model,
            prompt_version="critic-test-v1",
            reviewed_at=datetime.now(UTC),
        )


def make_board(
    cache_root: Path, *, rights: RightsStatus = RightsStatus.PUBLIC_DOMAIN
) -> ResearchBoard:
    thumbnail = cache_root / "thumbnails" / "map.jpg"
    thumbnail.parent.mkdir(parents=True, exist_ok=True)
    thumbnail.write_bytes(b"reference-image")
    evidence = EvidenceCitation(
        observation_id="observation:snow-horses",
        passage_id="passage:1805-09-16",
        author_display_name="William Clark",
        entry_date=18050916,
        category="transportation",
        canonical_term="horses in snow",
        source_quote="our horses passed with much difficulty through the snow",
        confidence=0.98,
    )
    asset = VerifiedAsset(
        asset=BoardMediaAsset(
            asset_id="loc:map",
            provider="Library of Congress",
            title="Lewis and Clark route map",
            asset_type="map",
            creation_date_text="1807",
            source_url="https://www.loc.gov/item/map/",
            thumbnail_path=str(thumbnail),
            rights_status=rights,
            rights_text="Public domain",
        ),
        requirement_id="bitterroot:transportation",
        confidence=BoardConfidence.HIGH,
        production_use="Horse travel on constrained mountain trails.",
        why_selected="Near-contemporary route reference.",
        evidence=(evidence,),
        historical_relationship=HistoricalRelationship.NEAR_CONTEMPORARY,
    )
    section = BoardSection(title="Expedition transportation", assets=(asset,))
    return ResearchBoard(
        prompt="Build the Bitterroot board",
        title="Crossing the Bitterroots — September 1805",
        summary="Test board",
        evidence_matrix=(),
        sections=(section,),
        reviewed_assets=(asset,),
        warnings=(),
        sources_used=("William Clark", "Library of Congress"),
    )


def settings(*, enabled: bool = True) -> PrevisSettings:
    return PrevisSettings(
        enabled=enabled,
        video_model="veo-test",
        storage_uri="unused",
        estimated_cost_per_second_usd=0.5,
    )


def request() -> ShotBriefRequest:
    return ShotBriefRequest(
        board_section_title="Expedition transportation",
        reference_asset_ids=("loc:map",),
    )


def test_gemini_brief_uses_provider_compatible_schema() -> None:
    models = FakeGeminiModels()
    client = type("FakeGeminiClient", (), {"models": models})()
    producer = GeminiShotBriefProducer(client, model="gemini-test")

    context = {
        "evidence": [
            {
                "observation_id": "observation:snow-horses",
                "passage_id": "passage:1805-09-16",
            }
        ]
    }
    content = asyncio.run(producer.produce(context))
    serialized_schema = str(models.config.response_schema)

    assert content.negative_prompt == "wagons, modern clothing"
    assert "additionalProperties" not in serialized_schema
    assert "observation:snow-horses" in serialized_schema
    assert "passage:1805-09-16" in serialized_schema


def service(
    tmp_path: Path,
    producer: FakeProducer | None = None,
    generator: FakeGenerator | None = None,
    *,
    enabled: bool = True,
) -> tuple[PrevisService, FakeGenerator]:
    cache = tmp_path / "archive"
    video = generator or FakeGenerator()
    return (
        PrevisService(
            settings(enabled=enabled),
            FilePrevisStore(tmp_path / "previs"),
            producer or FakeProducer(),
            video,
            WagonCritic(),
            archive_root=cache,
        ),
        video,
    )


def test_strict_brief_is_grounded_persisted_and_fingerprinted(tmp_path: Path) -> None:
    previs, _ = service(tmp_path)
    board = make_board(tmp_path / "archive")

    envelope = asyncio.run(previs.create_brief("session-1", board, request()))

    assert envelope.can_generate is True
    assert envelope.estimated_cost_usd == 4
    assert envelope.brief.content.interpretive_additions == ()
    assert "wagons" in envelope.brief.content.excluded_details
    assert envelope.brief_fingerprint == brief_fingerprint(envelope.brief)
    reloaded = FilePrevisStore(tmp_path / "previs").load_brief(
        envelope.brief.shot_brief_id
    )
    assert reloaded == envelope.brief


@pytest.mark.parametrize(
    "producer, message",
    [
        (FakeProducer(interpretive=True), "[Ss]trict"),
        (FakeProducer(unknown_id=True), "unknown observation"),
    ],
)
def test_brief_guardrails_reject_untrusted_model_output(
    tmp_path: Path, producer: FakeProducer, message: str
) -> None:
    previs, _ = service(tmp_path, producer=producer)
    board = make_board(tmp_path / "archive")

    with pytest.raises((ValueError, PrevisBlockedError), match=message):
        asyncio.run(previs.create_brief("session-1", board, request()))


def test_reference_must_come_from_public_domain_board_asset(tmp_path: Path) -> None:
    previs, _ = service(tmp_path)
    board = make_board(tmp_path / "archive", rights=RightsStatus.RIGHTS_UNCLEAR)

    with pytest.raises(PrevisBlockedError, match="public domain"):
        asyncio.run(previs.create_brief("session-1", board, request()))

    invented = request().model_copy(update={"reference_asset_ids": ("loc:invented",)})
    with pytest.raises(PrevisBlockedError, match="stored board"):
        asyncio.run(previs.create_brief("session-1", board, invented))


def test_disabled_video_never_calls_provider(tmp_path: Path) -> None:
    previs, generator = service(tmp_path, enabled=False)
    board = make_board(tmp_path / "archive")
    envelope = asyncio.run(previs.create_brief("session-1", board, request()))

    assert envelope.can_generate is False
    with pytest.raises(PrevisBlockedError, match="disabled"):
        asyncio.run(
            previs.generate(
                envelope.brief.shot_brief_id,
                GenerationApproval(
                    approved=True, brief_fingerprint=envelope.brief_fingerprint
                ),
            )
        )
    assert generator.submissions == []


def test_generation_is_idempotent_and_survives_service_recreation(tmp_path: Path) -> None:
    generator = FakeGenerator(
        [VideoPoll(done=False), VideoPoll(done=True, video_bytes=b"fake-mp4")]
    )
    previs, _ = service(tmp_path, generator=generator)
    board = make_board(tmp_path / "archive")
    brief = asyncio.run(previs.create_brief("session-1", board, request()))
    approval = GenerationApproval(
        approved=True, brief_fingerprint=brief.brief_fingerprint
    )

    first = asyncio.run(previs.generate(brief.brief.shot_brief_id, approval))
    duplicate = asyncio.run(previs.generate(brief.brief.shot_brief_id, approval))
    pending = asyncio.run(previs.get_job(first.job.job_id))
    complete = asyncio.run(previs.get_job(first.job.job_id))

    assert first.job.job_id == duplicate.job.job_id
    assert len(generator.submissions) == 1
    assert pending.job.status == "generating"
    assert complete.job.status == "complete"
    assert previs.read_video(first.job.job_id) == (b"fake-mp4", "video/mp4")

    recreated, _ = service(tmp_path)
    recovered = asyncio.run(recreated.get_job(first.job.job_id))
    assert recovered.job == complete.job


def test_critic_flags_wagon_and_correction_is_capped(tmp_path: Path) -> None:
    previs, _ = service(
        tmp_path,
        generator=FakeGenerator(
            [
                VideoPoll(done=True, video_bytes=b"first-mp4"),
                VideoPoll(done=True, video_bytes=b"corrected-mp4"),
            ]
        ),
    )
    board = make_board(tmp_path / "archive")
    brief = asyncio.run(previs.create_brief("session-1", board, request()))
    parent = asyncio.run(
        previs.generate(
            brief.brief.shot_brief_id,
            GenerationApproval(
                approved=True, brief_fingerprint=brief.brief_fingerprint
            ),
        )
    )
    parent = asyncio.run(previs.get_job(parent.job.job_id))
    reviewed = asyncio.run(previs.review(parent.job.job_id))

    assert reviewed.report is not None
    assert reviewed.report.overall_result is ConsistencyResult.UNSUPPORTED
    assert reviewed.report.findings[0].visible_detail.startswith("A wagon")

    child = asyncio.run(
        previs.correct(
            parent.job.job_id,
            CorrectionApproval(
                approved=True, job_fingerprint=job_fingerprint(reviewed.job)
            ),
        )
    )
    child = asyncio.run(previs.get_job(child.job.job_id))
    child = asyncio.run(previs.review(child.job.job_id))
    with pytest.raises(PrevisBlockedError, match="limit"):
        asyncio.run(
            previs.correct(
                child.job.job_id,
                CorrectionApproval(
                    approved=True, job_fingerprint=job_fingerprint(child.job)
                ),
            )
        )


class FakeBlob:
    def __init__(self, bucket: FakeBucket, name: str) -> None:
        self.bucket = bucket
        self.name = name
        self.content_type: str | None = None

    def upload_from_string(self, content: bytes | str, content_type: str) -> None:
        self.bucket.objects[self.name] = (
            content.encode() if isinstance(content, str) else content
        )
        self.content_type = content_type

    def download_as_text(self) -> str:
        return self.bucket.objects[self.name].decode()

    def download_as_bytes(self) -> bytes:
        return self.bucket.objects[self.name]

    def exists(self) -> bool:
        return self.name in self.bucket.objects


class FakeBucket:
    def __init__(self, name: str) -> None:
        self.name = name
        self.objects: dict[str, bytes] = {}

    def blob(self, name: str) -> FakeBlob:
        return FakeBlob(self, name)

    def copy_blob(self, source: FakeBlob, destination: FakeBucket, new_name: str) -> None:
        destination.objects[new_name] = source.bucket.objects[source.name]


class FakeStorageClient:
    def __init__(self) -> None:
        self.buckets: dict[str, FakeBucket] = {}

    def bucket(self, name: str) -> FakeBucket:
        return self.buckets.setdefault(name, FakeBucket(name))


def test_gcs_store_persists_briefs_references_jobs_and_video(tmp_path: Path) -> None:
    client = FakeStorageClient()
    store = GcsPrevisStore("gs://sourcecut/previs", client=client)
    previs = PrevisService(
        settings(),
        store,
        FakeProducer(),
        FakeGenerator(),
        WagonCritic(),
        archive_root=tmp_path / "archive",
    )
    board = make_board(tmp_path / "archive")
    brief = asyncio.run(previs.create_brief("session-1", board, request()))
    job = asyncio.run(
        previs.generate(
            brief.brief.shot_brief_id,
            GenerationApproval(
                approved=True, brief_fingerprint=brief.brief_fingerprint
            ),
        )
    )
    job = asyncio.run(previs.get_job(job.job.job_id))

    assert store.load_brief(brief.brief.shot_brief_id) == brief.brief
    assert store.load_job(job.job.job_id) == job.job
    assert store.read_references(
        brief.brief.shot_brief_id, brief.brief.reference_asset_ids
    ) == ((b"reference-image", "image/jpeg"),)
    assert store.read_video(job.job.job_id) == (b"fake-mp4", "video/mp4")
