from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Protocol

from google import genai
from google.genai import types

from sourcecut_api.models import ExtractionResult, ObservationBatch, ObservationCandidate, Passage
from sourcecut_api.telemetry import add_counter, observe_histogram, telemetry_span

DEFAULT_MODEL = "gemini-2.5-flash"
SCHEMA_VERSION = "observation-candidate-v1"
PROMPT_VERSION = "primary-source-extraction-v2"

SYSTEM_INSTRUCTION = """You extract production-relevant facts from one historical passage.
Use only the supplied passage as evidence. Do not add outside knowledge or historically plausible
details. Preserve uncertainty and historical spelling in source_quote. Every observation must use
one exact, contiguous quote and zero-based start/end offsets relative to the supplied passage,
where end is exclusive. Copy the quote's whitespace exactly, including repeated spaces and line
breaks. Set explicit true only when the passage states the observation directly.
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
    # Zero for the deterministic single-shot path. Self-consistency raises it
    # so repeated runs are independent samples rather than one answer repeated.
    temperature: float = 0.0


class GeminiObservationExtractor:
    def __init__(
        self,
        client: GeminiClient,
        config: ExtractionConfig | None = None,
    ) -> None:
        self._client = client
        self._config = config or ExtractionConfig()

    def extract(self, passage: Passage) -> ExtractionResult:
        attributes = {
            "gen_ai.system": "gemini",
            "gen_ai.request.model": self._config.model,
            "sourcecut.passage_id": passage.passage_id,
            "sourcecut.schema.version": self._config.schema_version,
            "sourcecut.prompt.version": self._config.prompt_version,
        }
        started = time.perf_counter()
        try:
            with telemetry_span("sourcecut.extraction.run", attributes):
                with telemetry_span("gemini.generate_content", attributes) as gemini_span:
                    response = self._client.models.generate_content(
                        model=self._config.model,
                        contents=_build_prompt(passage),
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_INSTRUCTION,
                            temperature=self._config.temperature,
                            response_mime_type="application/json",
                            response_json_schema=ObservationBatch.model_json_schema(),
                        ),
                    )
                    usage = getattr(response, "usage_metadata", None)
                    if usage is not None:
                        for field, attribute in (
                            ("prompt_token_count", "gen_ai.usage.input_tokens"),
                            ("candidates_token_count", "gen_ai.usage.output_tokens"),
                            ("thoughts_token_count", "sourcecut.gen_ai.thinking_tokens"),
                        ):
                            value = getattr(usage, field, None)
                            if value is not None:
                                gemini_span.set_attribute(attribute, int(value))
                batch = _parse_response(response)
                candidates = tuple(
                    _align_candidate_span(passage, candidate)
                    for candidate in batch.observations
                )
                result = ExtractionResult(
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
                    candidates=candidates,
                )
            add_counter("sourcecut.extraction.runs", 1, {"status": "success"})
            add_counter("sourcecut.observations.created", len(result.candidates))
            return result
        except Exception:
            add_counter("sourcecut.extraction.runs", 1, {"status": "failure"})
            raise
        finally:
            observe_histogram(
                "sourcecut.extraction.duration",
                (time.perf_counter() - started) * 1000,
            )


def create_extractor(
    *,
    api_key: str | None = None,
    model: str | None = None,
    temperature: float = 0.0,
) -> GeminiObservationExtractor:
    client = genai.Client(api_key=api_key) if api_key else genai.Client()
    configured_model = model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    return GeminiObservationExtractor(
        client, ExtractionConfig(model=configured_model, temperature=temperature)
    )


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
    with telemetry_span("sourcecut.pydantic.validate", {"sourcecut.model": "ObservationBatch"}):
        if isinstance(response.parsed, ObservationBatch):
            return response.parsed
        if response.parsed is not None:
            return ObservationBatch.model_validate(response.parsed)
        if response.text is None:
            raise ValueError("Gemini returned neither parsed output nor response text")
        return ObservationBatch.model_validate_json(response.text)


def _align_candidate_span(
    passage: Passage,
    candidate: ObservationCandidate,
) -> ObservationCandidate:
    typed = candidate
    text = passage.passage_text
    if text[typed.source_start : typed.source_end] == typed.source_quote:
        return typed
    exact = tuple(re.finditer(re.escape(typed.source_quote), text))
    if len(exact) == 1:
        match = exact[0]
        return typed.model_copy(
            update={"source_start": match.start(), "source_end": match.end()}
        )
    words = typed.source_quote.split()
    if not words:
        return typed
    flexible = tuple(re.finditer(r"\s+".join(re.escape(word) for word in words), text))
    if len(flexible) != 1:
        return typed
    match = flexible[0]
    return typed.model_copy(
        update={
            "source_quote": text[match.start() : match.end()],
            "source_start": match.start(),
            "source_end": match.end(),
        }
    )
