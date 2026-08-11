from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from sourcecut_api.models.media import HistoricalRelationship, MediaAsset, RightsStatus


class BoardConfidence(StrEnum):
    HIGH = "HIGH"
    SINGLE_SOURCE = "SINGLE_SOURCE"
    INTERPRETIVE = "INTERPRETIVE"
    UNSUPPORTED = "UNSUPPORTED"
    RIGHTS_REJECTED = "RIGHTS_REJECTED"


class EvidenceCitation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str
    passage_id: str
    author_display_name: str
    entry_date: Annotated[int, Field(ge=18000101, le=18991231)]
    category: str
    canonical_term: str
    source_quote: str
    confidence: Annotated[float, Field(ge=0, le=1)]


class AgreementCell(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    author_id: str
    author_display_name: str
    entry_date: Annotated[int, Field(ge=18000101, le=18991231)]
    state: Literal["mentions", "entry_without_mention", "no_entry"]
    mention_count: int = 0
    observation_count: int = 0
    passage_ids: tuple[str, ...] = ()


class AssetRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    requirement_id: str
    title: str
    category: str
    production_need: str
    search_terms: tuple[str, ...]
    evidence: tuple[EvidenceCitation, ...]
    agreement: tuple[AgreementCell, ...] = ()
    corroboration_authors: int = 0
    corroboration_days: int = 0


class VisualInspection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    relevant: bool
    visible_findings: str
    mismatch_flags: tuple[str, ...] = ()


class BoardMediaAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: str
    provider: str
    title: str
    asset_type: str
    creation_date_text: str
    source_url: str
    thumbnail_path: str
    rights_status: RightsStatus
    rights_text: str

    @classmethod
    def from_media_asset(cls, asset: MediaAsset) -> BoardMediaAsset:
        return cls(
            asset_id=asset.asset_id,
            provider=asset.provider,
            title=asset.title,
            asset_type=asset.asset_type,
            creation_date_text=asset.creation_date_text,
            source_url=asset.source_url,
            thumbnail_path=asset.thumbnail_path,
            rights_status=asset.rights_status,
            rights_text=asset.rights_text,
        )


class VerifiedAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset: BoardMediaAsset
    requirement_id: str
    confidence: BoardConfidence
    production_use: str
    why_selected: str
    evidence: tuple[EvidenceCitation, ...]
    historical_relationship: HistoricalRelationship
    visual_inspection: VisualInspection | None = None


class BoardSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str
    assets: tuple[VerifiedAsset, ...]


class ResearchBoard(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt: str
    title: str
    summary: str
    evidence_matrix: tuple[AssetRequirement, ...]
    sections: tuple[BoardSection, ...]
    reviewed_assets: tuple[VerifiedAsset, ...]
    warnings: tuple[str, ...]
    sources_used: tuple[str, ...]
