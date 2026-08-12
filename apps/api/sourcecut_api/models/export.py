from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from sourcecut_api.models.odyssey_board import OdysseyBoard


class ExportFormat(StrEnum):
    JSON = "json"
    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"
    CITATIONS_TEXT = "citations_text"
    CITATIONS_MARKDOWN = "citations_markdown"
    CSL_JSON = "csl_json"
    BIBTEX = "bibtex"
    GEOJSON = "geojson"
    MAP_PNG = "map_png"


class BoardExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision_id: str
    format: ExportFormat
    include: tuple[
        Literal["claims", "passages", "timeline", "map", "assets", "provenance"], ...
    ] = ("claims", "passages", "timeline", "map", "assets", "provenance")
    display_policy: Literal["private", "public_reusable"] = "public_reusable"


class ProvenanceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_id: str
    board_id: str
    revision_id: str
    release_manifest_id: str
    corpus_revision: str
    annotation_release_ids: tuple[str, ...]
    active_versions: tuple[str, ...]
    active_hypotheses: tuple[str, ...]
    source_session_id: str
    source_references: tuple[str, ...]
    omitted_item_ids: tuple[str, ...]
    generated_at: datetime


class ExportJob(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str
    board_id: str
    revision_id: str
    format: ExportFormat
    status: Literal["complete", "failed"]
    display_policy: Literal["private", "public_reusable"]
    rights_decision: str
    artifact_sha256: str
    manifest_sha256: str
    content_type: str
    filename: str
    download_url: str
    expires_at: datetime
    created_at: datetime


class ShareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision_id: str
    expires_in_days: Annotated[int, Field(ge=1, le=365)] = 30


class ShareLink(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    share_token: str
    board_id: str
    revision_id: str
    share_url: str
    omitted_item_count: int
    expires_at: datetime
    created_at: datetime


class SharedBoard(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    board: OdysseyBoard
    provenance_manifest: ProvenanceManifest
    omitted_item_count: int
    rights_notice: str
    expires_at: datetime
