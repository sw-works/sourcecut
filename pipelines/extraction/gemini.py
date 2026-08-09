from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Protocol

from google import genai
from google.genai import types

from sourcecut_api.models import ExtractionResult, ObservationBatch, Passage

DEFAULT_MODEL = "gemini-2.5-flash"
SCHEMA_VERSION = "observation-candidate-v1"
PROMPT_VERSION = "primary-source-extraction-v1"

SYSTEM_INSTRUCTION = """You extract production-relevant facts from one historical passage.
Use only the supplied passage as evidence. Do not add outside knowledge or historically plausible
details. Preserve uncertainty and historical spelling in source_quote. Every observation must use
one exact, contiguous quote and zero-based start/end offsets relative to the supplied passage,
where end is exclusive. Set explicit true only when the passage states the observation directly.
Return no observations when the passage contains no production-relevant evidence.
Allowed categories: weather, terrain, transportation, food, shelter, equipment, person, animal,
place, health, event."""


class GenerateContentResponse(Protocol):
    parsed: object
    text: str | None


class ModelsClient(Protocol):
    def generate_content(
        self,
        *,
        model: str,
        contents: str,
        config: types.GenerateContentConfig,
    ) -> GenerateContentResponse: ...


class GeminiClient(Protocol):
    models: ModelsClient


@dataclass(frozen=True)
class ExtractionConfig:
    model: str = DEFAULT_MODEL
    schema_version: str = SCHEMA_VERSION
    prompt_version: str = PROMPT_VERSION


class GeminiObservationExtractor:
    def __init__(
        self,
        client: GeminiClient,
        config: ExtractionConfig | None = None,
    ) -> None:
        self._client = client
        self._config = config or ExtractionConfig()

    def extract(self, passage: Passage) -> ExtractionResult:
        response = self._client.models.generate_content(
            model=self._config.model,
            contents=_build_prompt(passage),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0,
                response_mime_type="application/json",
                response_schema=ObservationBatch,
            ),
        )
        batch = _parse_response(response)
        return ExtractionResult(
            passage_id=passage.passage_id,
            passage_sha256=passage.passage_sha256,
            model=self._config.model,
            schema_version=self._config.schema_version,
            prompt_version=self._config.prompt_version,
            idempotency_key=build_idempotency_key(
                passage.passage_sha256,
                self._config.model,
                self._config.schema_version,
                self._config.prompt_version,
            ),
            candidates=batch.observations,
        )


def create_extractor(
    *,
    api_key: str | None = None,
    model: str | None = None,
) -> GeminiObservationExtractor:
    client = genai.Client(api_key=api_key) if api_key else genai.Client()
    configured_model = model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    return GeminiObservationExtractor(client, ExtractionConfig(model=configured_model))


def build_idempotency_key(
    passage_sha256: str,
    model: str,
    schema_version: str,
    prompt_version: str,
) -> str:
    components = [passage_sha256, model, schema_version, prompt_version]
    serialized = json.dumps(components, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _build_prompt(passage: Passage) -> str:
    return (
        f"Passage ID: {passage.passage_id}\n"
        "All source offsets must be relative to the text between the passage markers.\n"
        "<SOURCE_PASSAGE>\n"
        f"{passage.passage_text}\n"
        "</SOURCE_PASSAGE>"
    )


def _parse_response(response: GenerateContentResponse) -> ObservationBatch:
    if isinstance(response.parsed, ObservationBatch):
        return response.parsed
    if response.parsed is not None:
        return ObservationBatch.model_validate(response.parsed)
    if response.text is None:
        raise ValueError("Gemini returned neither parsed output nor response text")
    return ObservationBatch.model_validate_json(response.text)
