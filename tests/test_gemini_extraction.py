from __future__ import annotations

import hashlib
from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from pipelines.extraction.gemini import (
    PROMPT_VERSION,
    SCHEMA_VERSION,
    ExtractionConfig,
    GeminiObservationExtractor,
    build_idempotency_key,
)
from sourcecut_api.models import ObservationBatch, Passage


class FakeModels:
    def __init__(self, response: SimpleNamespace) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return self.response


def make_passage() -> Passage:
    text = "The snow fell and several men were unable to proceed."
    return Passage(
        passage_id="test:lewis:1805-09-21:1:passage:0",
        entry_id="test:lewis:1805-09-21:1",
        source_id="test",
        author_id="lewis",
        author_display_name="Meriwether Lewis",
        entry_date=date(1805, 9, 21),
        passage_index=0,
        char_start=0,
        char_end=len(text),
        passage_text=text,
        passage_sha256=hashlib.sha256(text.encode()).hexdigest(),
    )


def candidate_payload() -> dict[str, object]:
    return {
        "category": "weather",
        "canonical_term": "snow",
        "normalized_description": "Snow impeded travel.",
        "explicit": True,
        "source_quote": "The snow fell",
        "source_start": 0,
        "source_end": 13,
        "confidence": 0.98,
    }


def test_extracts_typed_candidates_and_records_versions() -> None:
    models = FakeModels(
        SimpleNamespace(parsed={"observations": [candidate_payload()]}, text=None)
    )
    passage = make_passage()
    config = ExtractionConfig(model="gemini-test")
    result = GeminiObservationExtractor(SimpleNamespace(models=models), config).extract(passage)

    assert len(result.candidates) == 1
    assert result.candidates[0].category == "weather"
    assert result.model == "gemini-test"
    assert result.schema_version == SCHEMA_VERSION
    assert result.prompt_version == PROMPT_VERSION
    assert result.passage_id == passage.passage_id
    assert result.passage_sha256 == passage.passage_sha256
    assert result.idempotency_key == build_idempotency_key(
        passage.passage_sha256,
        "gemini-test",
        SCHEMA_VERSION,
        PROMPT_VERSION,
    )


def test_uses_pydantic_response_schema_and_evidence_only_prompt() -> None:
    models = FakeModels(SimpleNamespace(parsed={"observations": []}, text=None))
    passage = make_passage()

    GeminiObservationExtractor(SimpleNamespace(models=models)).extract(passage)

    call = models.calls[0]
    assert call["contents"].count(passage.passage_text) == 1
    assert call["config"].response_schema is None
    assert call["config"].response_json_schema == ObservationBatch.model_json_schema()
    assert call["config"].response_mime_type == "application/json"
    assert call["config"].temperature == 0
    instruction = call["config"].system_instruction
    assert "only the supplied passage" in instruction
    assert "Do not add outside knowledge" in instruction
    assert "Preserve uncertainty" in instruction
    assert "exact, contiguous quote" in instruction


def test_json_text_fallback_is_validated() -> None:
    response_text = ObservationBatch.model_validate(
        {"observations": [candidate_payload()]}
    ).model_dump_json()
    models = FakeModels(SimpleNamespace(parsed=None, text=response_text))

    result = GeminiObservationExtractor(SimpleNamespace(models=models)).extract(make_passage())

    assert result.candidates[0].canonical_term == "snow"


def test_uniquely_aligns_model_normalized_whitespace_to_stored_passage() -> None:
    passage = make_passage().model_copy(
        update={"passage_text": "The  snow\nfell and several men were unable to proceed."}
    )
    payload = candidate_payload() | {
        "source_quote": "The snow fell",
        "source_start": 0,
        "source_end": 13,
    }
    models = FakeModels(SimpleNamespace(parsed={"observations": [payload]}, text=None))

    result = GeminiObservationExtractor(SimpleNamespace(models=models)).extract(passage)

    candidate = result.candidates[0]
    assert candidate.source_quote == "The  snow\nfell"
    assert passage.passage_text[candidate.source_start : candidate.source_end] == (
        candidate.source_quote
    )


def test_invalid_structured_candidate_is_rejected() -> None:
    invalid = candidate_payload() | {"category": "historically_plausible_object"}
    models = FakeModels(SimpleNamespace(parsed={"observations": [invalid]}, text=None))

    with pytest.raises(ValidationError):
        GeminiObservationExtractor(SimpleNamespace(models=models)).extract(make_passage())


def test_idempotency_key_changes_with_each_input() -> None:
    base = ("a" * 64, "model", "schema", "prompt")
    original = build_idempotency_key(*base)

    assert original == build_idempotency_key(*base)
    for index in range(len(base)):
        changed = list(base)
        changed[index] += "-changed"
        assert build_idempotency_key(*changed) != original
