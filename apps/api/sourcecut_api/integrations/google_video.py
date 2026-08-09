from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

from google import genai
from google.genai import types
from pydantic import BaseModel, ConfigDict

from sourcecut_api.models import (
    ConsistencyFinding,
    ConsistencyReport,
    ConsistencyResult,
    PrevisJob,
    ShotBrief,
    ShotBriefContent,
)

SHOT_BRIEF_PROMPT_VERSION = "previs-shot-brief-v1"
CRITIC_PROMPT_VERSION = "previs-critic-v1"

SHOT_BRIEF_INSTRUCTION = """
You are SourceCut's evidence-constrained shot-brief producer. Return a production previsualization
brief using only the supplied board section. Every supported detail must cite supplied observation
and passage IDs. In strict mode, interpretive_additions must be empty. Put modern or unsupported
objects in excluded_details and in negative_prompt. Negative prompts must be comma-separated noun
phrases, never instructions. Do not claim that a map or document literally depicts terrain,
people, clothing, or events. Do not add outside historical knowledge.
""".strip()

CRITIC_INSTRUCTION = """
You are SourceCut's independent previsualization critic. Inspect only visible or audible details in
the supplied generated clip. Compare them with the approved shot brief. Label each finding as
supported, interpretive, or unsupported. Unsupported findings require correction instructions
that remove or replace only the observed problem. Do not introduce new historical details and do
not describe the clip as evidence or archival footage.
""".strip()


class ShotBriefProducer(Protocol):
    model: str

    async def produce(self, context: dict[str, Any]) -> ShotBriefContent: ...


class VideoCritic(Protocol):
    model: str

    async def review(
        self,
        job: PrevisJob,
        brief: ShotBrief,
        video: bytes,
        mime_type: str,
    ) -> ConsistencyReport: ...


class VideoGenerator(Protocol):
    async def submit(
        self,
        job_id: str,
        brief: ShotBrief,
        reference_images: tuple[tuple[bytes, str], ...],
        *,
        output_gcs_uri: str | None,
        correction_instructions: tuple[str, ...] = (),
    ) -> str: ...

    async def poll(self, operation_name: str) -> VideoPoll: ...


@dataclass(frozen=True, slots=True)
class VideoPoll:
    done: bool
    video_bytes: bytes | None = None
    output_uri: str = ""
    blocked: bool = False
    safe_error: str = ""


class CriticContent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    overall_result: ConsistencyResult
    findings: tuple[ConsistencyFinding, ...]
    correction_instructions: tuple[str, ...] = ()


def _gemini_response_schema(model: type[BaseModel]) -> dict[str, Any]:
    schema = model.model_json_schema()

    def remove_unsupported(value: Any) -> None:
        if isinstance(value, dict):
            value.pop("additionalProperties", None)
            for child in value.values():
                remove_unsupported(child)
        elif isinstance(value, list):
            for child in value:
                remove_unsupported(child)

    remove_unsupported(schema)
    return schema


def _citation_constrained_schema(
    model: type[BaseModel],
    *,
    observation_ids: tuple[str, ...],
    passage_ids: tuple[str, ...],
) -> dict[str, Any]:
    schema = _gemini_response_schema(model)

    def constrain(value: Any) -> None:
        if isinstance(value, dict):
            properties = value.get("properties", {})
            if observation_ids and "observation_ids" in properties:
                properties["observation_ids"]["items"]["enum"] = list(observation_ids)
            if passage_ids and "passage_ids" in properties:
                properties["passage_ids"]["items"]["enum"] = list(passage_ids)
            for child in value.values():
                constrain(child)
        elif isinstance(value, list):
            for child in value:
                constrain(child)

    constrain(schema)
    return schema


class GeminiShotBriefProducer:
    def __init__(self, client: Any, *, model: str) -> None:
        self._client = client
        self.model = model

    async def produce(self, context: dict[str, Any]) -> ShotBriefContent:
        evidence = context.get("evidence", [])
        schema = _citation_constrained_schema(
            ShotBriefContent,
            observation_ids=tuple(item["observation_id"] for item in evidence),
            passage_ids=tuple(item["passage_id"] for item in evidence),
        )

        def generate() -> Any:
            return self._client.models.generate_content(
                model=self.model,
                contents=json.dumps(context, separators=(",", ":"), ensure_ascii=False),
                config=types.GenerateContentConfig(
                    system_instruction=SHOT_BRIEF_INSTRUCTION,
                    temperature=0,
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )

        response = await asyncio.to_thread(generate)
        return _parsed(response, ShotBriefContent, "shot brief")


class GeminiVideoCritic:
    def __init__(self, client: Any, *, model: str) -> None:
        self._client = client
        self.model = model

    async def review(
        self,
        job: PrevisJob,
        brief: ShotBrief,
        video: bytes,
        mime_type: str,
    ) -> ConsistencyReport:
        prompt = json.dumps(
            {
                "approved_shot_brief": brief.model_dump(mode="json"),
                "required_disclosure": (
                    "AI-generated previsualization — not historical evidence"
                ),
            },
            separators=(",", ":"),
            ensure_ascii=False,
        )
        observation_ids = tuple(
            value
            for detail in brief.content.supported_details
            for value in detail.observation_ids
        )
        passage_ids = tuple(
            value
            for detail in brief.content.supported_details
            for value in detail.passage_ids
        )
        schema = _citation_constrained_schema(
            CriticContent,
            observation_ids=observation_ids,
            passage_ids=passage_ids,
        )

        def generate() -> Any:
            return self._client.models.generate_content(
                model=self.model,
                contents=[prompt, types.Part.from_bytes(data=video, mime_type=mime_type)],
                config=types.GenerateContentConfig(
                    system_instruction=CRITIC_INSTRUCTION,
                    temperature=0,
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )

        response = await asyncio.to_thread(generate)
        content = _parsed(response, CriticContent, "consistency report")
        return ConsistencyReport(
            job_id=job.job_id,
            overall_result=content.overall_result,
            findings=content.findings,
            correction_instructions=content.correction_instructions,
            critic_model=self.model,
            prompt_version=CRITIC_PROMPT_VERSION,
            reviewed_at=job.updated_at,
        )


class GoogleVeoGenerator:
    def __init__(self, client: Any, *, model: str) -> None:
        self._client = client
        self._model = model

    async def submit(
        self,
        job_id: str,
        brief: ShotBrief,
        reference_images: tuple[tuple[bytes, str], ...],
        *,
        output_gcs_uri: str | None,
        correction_instructions: tuple[str, ...] = (),
    ) -> str:
        prompt = brief.content.positive_prompt
        if correction_instructions:
            prompt = f"{prompt}\nCorrections: {'; '.join(correction_instructions)}"
        references = [
            types.VideoGenerationReferenceImage(
                image=types.Image(image_bytes=content, mime_type=mime_type),
                reference_type=types.VideoGenerationReferenceType.ASSET,
            )
            for content, mime_type in reference_images[:3]
        ]

        def generate() -> Any:
            operation = self._client.models.generate_videos(
                model=self._model,
                source=types.GenerateVideosSource(prompt=prompt),
                config=types.GenerateVideosConfig(
                    number_of_videos=1,
                    output_gcs_uri=output_gcs_uri,
                    duration_seconds=brief.duration_seconds,
                    aspect_ratio=brief.aspect_ratio,
                    negative_prompt=brief.content.negative_prompt,
                    enhance_prompt=False,
                    generate_audio=False,
                    reference_images=references or None,
                    labels={"sourcecut_job": job_id},
                ),
            )
            if not operation.name:
                raise RuntimeError("Veo returned no operation name")
            return operation.name

        return await asyncio.to_thread(generate)

    async def poll(self, operation_name: str) -> VideoPoll:
        def refresh() -> VideoPoll:
            operation = self._client.operations.get(
                types.GenerateVideosOperation(name=operation_name)
            )
            if not operation.done:
                return VideoPoll(done=False)
            if operation.error:
                return VideoPoll(done=True, safe_error=_safe_provider_error(operation.error))
            response = operation.result or operation.response
            if response is None:
                return VideoPoll(done=True, safe_error="Video generation returned no result")
            videos = response.generated_videos or []
            if not videos or videos[0].video is None:
                reasons = response.rai_media_filtered_reasons or []
                return VideoPoll(
                    done=True,
                    blocked=bool(response.rai_media_filtered_count),
                    safe_error=(
                        reasons[0][:300]
                        if reasons
                        else "Video generation returned no clip"
                    ),
                )
            video = videos[0].video
            if video.video_bytes:
                return VideoPoll(done=True, video_bytes=video.video_bytes)
            if video.uri and video.uri.startswith("gs://"):
                return VideoPoll(done=True, output_uri=video.uri)
            if video.uri:
                return VideoPoll(done=True, video_bytes=self._client.files.download(file=video))
            return VideoPoll(done=True, safe_error="Generated video had no downloadable output")

        return await asyncio.to_thread(refresh)


def create_google_video_clients() -> tuple[
    GeminiShotBriefProducer, GoogleVeoGenerator, GeminiVideoCritic
]:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "false").casefold() == "true"
    client = genai.Client() if use_vertex or not api_key else genai.Client(api_key=api_key)
    brief_model = os.getenv("SOURCECUT_VIDEO_BRIEF_MODEL", "gemini-2.5-flash")
    video_model = os.getenv("SOURCECUT_VIDEO_MODEL", "replace-with-enabled-veo-model")
    review_model = os.getenv("SOURCECUT_VIDEO_REVIEW_MODEL", "gemini-2.5-flash")
    return (
        GeminiShotBriefProducer(client, model=brief_model),
        GoogleVeoGenerator(client, model=video_model),
        GeminiVideoCritic(client, model=review_model),
    )


def _parsed(response: Any, model_type: type[BaseModel], label: str) -> Any:
    if isinstance(response.parsed, model_type):
        return response.parsed
    if response.parsed is not None:
        return model_type.model_validate(response.parsed)
    if response.text is None:
        raise ValueError(f"Gemini returned no {label}")
    return model_type.model_validate_json(response.text)


def _safe_provider_error(error: Any) -> str:
    if isinstance(error, dict):
        message = str(error.get("message") or error.get("status") or "Video generation failed")
    else:
        message = str(error)
    return message.replace("\n", " ")[:300]
