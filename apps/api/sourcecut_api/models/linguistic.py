from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sourcecut_api.models.corpus import Sha256


class SearchMode(StrEnum):
    EXACT = "exact"
    NORMALIZED = "normalized"
    FORM = "form"
    LEMMA = "lemma"
    ENGLISH = "english"


class LinguisticAnnotationRelease(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    annotation_release_id: str
    work_id: str = "odyssey"
    source_version_id: str
    annotation_source: str
    annotation_version: str
    source_document_urn: str
    repository_url: str
    upstream_path: str
    upstream_revision: str
    source_sha256: Sha256
    license_id: str
    raw_content: str
    review_status: str = "imported_unreviewed"


class TextToken(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    token_id: str
    text_unit_id: str
    version_id: str
    book: Annotated[int, Field(ge=1, le=24)]
    line: Annotated[int, Field(ge=1)]
    token_index: Annotated[int, Field(ge=0, le=65_535)]
    surface: str
    normalized_surface: str
    accentless_surface: str
    lemma: str = ""
    lemma_search: str = ""
    part_of_speech: str = "unknown"
    morphology: dict[str, str] = Field(default_factory=dict)
    char_start: Annotated[int, Field(ge=0)]
    char_end: Annotated[int, Field(ge=0)]
    annotation_source: str
    annotation_confidence: Annotated[float, Field(ge=0, le=1)]
    review_status: str
    annotation_version: str
    annotation_release_id: str = ""
    source_token_ref: str = ""
    token_sha256: Sha256

    @field_validator("char_end")
    @classmethod
    def validate_span_end(cls, value: int, info: object) -> int:
        data = getattr(info, "data", {})
        if value <= int(data.get("char_start", -1)):
            raise ValueError("char_end must be greater than char_start")
        return value


class FormulaOccurrence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    occurrence_id: str
    formula_id: str
    version_id: str
    book: Annotated[int, Field(ge=1, le=24)]
    line_start: Annotated[int, Field(ge=1)]
    line_end: Annotated[int, Field(ge=1)]
    ngram_size: Annotated[int, Field(ge=2, le=5)]
    normalized_formula: str
    display_formula: str
    token_ids: tuple[str, ...]
    occurrence_sha256: Sha256
    derived_method: str = "exact-token-ngram-v1"
    review_status: str = "derived_unreviewed"


class TextSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    corpus_id: Literal["odyssey"] = "odyssey"
    query: Annotated[str, Field(min_length=1, max_length=200)]
    mode: SearchMode = SearchMode.NORMALIZED
    version_ids: tuple[str, ...] = ()
    books: tuple[Annotated[int, Field(ge=1, le=24)], ...] = ()
    part_of_speech: tuple[str, ...] = ()
    speaker_ids: tuple[str, ...] = ()
    entity_ids: tuple[str, ...] = ()
    narrative_levels: tuple[str, ...] = ()
    page_size: Annotated[int, Field(ge=1, le=100)] = 25
    cursor: str | None = None
    accent_insensitive: bool = False


class TextMatchSpan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    char_start: int
    char_end: int
    token_id: str = ""


class TokenAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    token_id: str
    surface: str
    lemma: str
    part_of_speech: str
    morphology: dict[str, str]
    annotation_source: str
    annotation_version: str
    annotation_confidence: float
    review_status: str
    gloss: str | None = None
    gloss_source: str = "not_available"
    occurrence_count: int = 0
    derived_annotation: bool = True


class TextSearchHit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text_unit_id: str
    version_id: str
    citation: str
    cts_urn: str
    book: int
    line_start: int
    line_end: int
    text: str
    matches: tuple[TextMatchSpan, ...]
    token: TokenAnalysis | None = None


class TextSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query: str
    mode: SearchMode
    interpretation: str
    hits: tuple[TextSearchHit, ...]
    facets: dict[str, dict[str, int]]
    next_cursor: str | None = None
    warnings: tuple[str, ...] = ()


class FrequencyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: Annotated[str, Field(min_length=1, max_length=100)]
    mode: Literal["lemma", "form"] = "lemma"
    group_by: Literal["book", "speaker", "scene", "narrative_level"] = "book"
    version_id: str = "odyssey-perseus-grc2"


class FrequencyBucket(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    count: int


class FrequencyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query: str
    mode: str
    group_by: str
    buckets: tuple[FrequencyBucket, ...]
    annotation_notice: str


class FormulaSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: Annotated[str, Field(max_length=200)] = ""
    ngram_size: Annotated[int | None, Field(ge=2, le=5)] = None
    book: Annotated[int | None, Field(ge=1, le=24)] = None
    page_size: Annotated[int, Field(ge=1, le=100)] = 25


class FormulaResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    formula_id: str
    display_formula: str
    normalized_formula: str
    ngram_size: int
    occurrence_count: int
    occurrences: tuple[dict[str, object], ...]
    status: str = "exact_derived_pattern"


class CooccurrenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left_lemma: Annotated[str, Field(min_length=1, max_length=100)]
    right_lemma: Annotated[str, Field(min_length=1, max_length=100)]
    window_lines: Annotated[int, Field(ge=0, le=50)] = 5
    books: tuple[Annotated[int, Field(ge=1, le=24)], ...] = ()


class SavedSearchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=120)]
    search: TextSearchRequest


class SavedSearch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    saved_search_id: str
    owner_id: str
    name: str
    search: TextSearchRequest
    created_at: str
    storage_scope: str = "application_session"
