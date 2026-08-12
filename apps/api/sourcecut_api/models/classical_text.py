from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from sourcecut_api.models.corpus import DisplayDecision, Sha256


class RawSourceDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: str
    version_id: str
    media_type: str = "application/tei+xml"
    raw_content: str
    raw_sha256: Sha256
    upstream_path: str
    upstream_revision: str


class TextUnit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text_unit_id: str
    work_id: str = "odyssey"
    version_id: str
    book: Annotated[int, Field(ge=1, le=24)]
    line_start: Annotated[int, Field(ge=1)]
    line_end: Annotated[int, Field(ge=1)]
    source_line_start: Annotated[int, Field(ge=1)]
    source_line_end: Annotated[int, Field(ge=1)]
    citation_correction: str = ""
    citation: str
    cts_urn: str
    unit_index: Annotated[int, Field(ge=0)]
    original_text: str
    normalized_text: str
    source_document_id: str
    source_char_start: Annotated[int, Field(ge=0)] = 0
    source_char_end: Annotated[int, Field(ge=0)] = 0
    text_sha256: Sha256
    parser_version: str


class ClassicalPassage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    passage_id: str
    version_id: str
    book: Annotated[int, Field(ge=1, le=24)]
    line_start: Annotated[int, Field(ge=1)]
    line_end: Annotated[int, Field(ge=1)]
    unit_ids: tuple[str, ...]
    passage_text: str
    passage_sha256: Sha256
    segmentation_version: str


class ResolvedCitation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    resolved: bool = True
    work_id: str = "odyssey"
    version_id: str
    book: int
    line_start: int
    line_end: int
    citation: str
    cts_urn: str
    canonical_url: str


class TextUnitView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text_unit_id: str
    citation: str
    cts_urn: str
    book: int
    line_start: int
    line_end: int
    text: str


class TextRangeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    work_id: str = "odyssey"
    version_id: str
    version_label: str
    language: str
    book: int
    line_start: int
    line_end: int
    cts_urn: str
    display_decision: DisplayDecision
    bibliographic_description: str
    attribution: str
    source_url: str
    license_name: str
    license_url: str
    units: tuple[TextUnitView, ...]
    previous_line: int | None = None
    next_line: int | None = None


class ParallelPassage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: TextRangeResponse
    targets: tuple[TextRangeResponse, ...]
    alignment_status: str = "line_range"
    warning: str = (
        "Parallel ranges are navigational alignments. Translation wording is not independent "
        "primary-source corroboration."
    )
