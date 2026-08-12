from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class CorpusStatus(StrEnum):
    ACTIVE = "active"
    PREVIEW = "preview"
    DISABLED = "disabled"


class VersionType(StrEnum):
    EDITION = "edition"
    TRANSLATION = "translation"
    COMMENTARY = "commentary"
    WITNESS = "witness"


class DisplayDecision(StrEnum):
    FULL_TEXT_AND_EXPORT = "full_text_and_export"
    FULL_TEXT_NO_BULK_EXPORT = "full_text_no_bulk_export"
    SHORT_EXCERPT_AND_CITATION = "short_excerpt_and_citation"
    METADATA_AND_CITATION_ONLY = "metadata_and_citation_only"
    INTERNAL_RESEARCH_ONLY = "internal_research_only"
    BLOCKED = "blocked"


class LicenseRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    license_id: str
    spdx_or_rights_code: str
    display_name: str
    canonical_url: str
    attribution_template: str
    share_alike: bool = False
    commercial_use_allowed: bool | None = None
    derivatives_allowed: bool | None = None
    bulk_export_allowed: bool | None = None
    notes: str = ""


class CorpusRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    corpus_id: str
    title: str
    description: str
    default_work_id: str
    adapter_version: str
    display_policy: DisplayDecision
    status: CorpusStatus


class WorkRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    work_id: str
    corpus_id: str
    cts_work_urn: str
    author_display_name: str
    title: str
    original_language: str
    book_count: Annotated[int, Field(ge=1, le=65_535)]
    metadata: dict[str, object] = Field(default_factory=dict)


class SourceVersionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version_id: str
    work_id: str
    cts_version_urn: str
    version_type: VersionType
    language: str
    label: str
    editor_names: tuple[str, ...] = ()
    translator_names: tuple[str, ...] = ()
    bibliographic_description: str
    publication_year: Annotated[int, Field(ge=0, le=65_535)] = 0
    source_url: str
    upstream_revision: str
    license_id: str
    display_decision: DisplayDecision
    source_sha256: Sha256 | None = None
    raw_manifest: dict[str, object] = Field(default_factory=dict)


class CorpusDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    corpus: CorpusRecord
    works: tuple[WorkRecord, ...]
    versions: tuple[SourceVersionRecord, ...]
    licenses: tuple[LicenseRecord, ...]
    release_manifest_id: str
    known_limitations: tuple[str, ...] = ()
