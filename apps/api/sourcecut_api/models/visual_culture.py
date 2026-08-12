from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from sourcecut_api.models.media import MediaAsset

RelationshipClass = Literal[
    "ANCIENT_REPRESENTATION",
    "ANCIENT_COMPARATIVE_OBJECT",
    "LATER_CLASSICAL_RECEPTION",
    "POST_CLASSICAL_RECEPTION",
    "MODERN_REFERENCE",
    "GEOGRAPHIC_REFERENCE",
    "MATERIAL_CULTURE_COMPARATIVE",
    "UNRELATED_OR_UNSUPPORTED",
]


class OdysseyAssetMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    asset_id: str
    institution: str
    object_id: str
    culture: str
    period: str
    object_date: str
    object_begin_date: int
    object_end_date: int
    medium: str
    image_rights_status: str
    image_attribution: str
    cached_image_path: str = ""
    public_display: bool


class AssetCorpusLink(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    asset_link_id: str
    asset_id: str
    corpus_id: str = "odyssey"
    target_kind: Literal["corpus", "entity", "event", "theme", "place", "passage", "claim"]
    target_id: str
    relationship_class: RelationshipClass
    review_status: str = "trusted"


class AssetRelationshipAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    assessment_id: str
    asset_id: str
    relationship_class: RelationshipClass
    production_use: str
    limitations: str
    evidence_ids: tuple[str, ...]
    confidence: str
    verification_status: Literal[
        "accepted",
        "accepted_with_warning",
        "metadata_only",
        "interpretive",
        "rejected",
        "needs_review",
    ]
    review_status: str = "trusted"

    @model_validator(mode="after")
    def unsupported_is_not_public(self) -> AssetRelationshipAssessment:
        if (
            self.relationship_class == "UNRELATED_OR_UNSUPPORTED"
            and self.verification_status != "rejected"
        ):
            raise ValueError("Unsupported relationships must be rejected")
        return self


class VisualCultureRelease(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    release_id: str
    assets: tuple[MediaAsset, ...]
    metadata: tuple[OdysseyAssetMetadata, ...]
    links: tuple[AssetCorpusLink, ...]
    assessments: tuple[AssetRelationshipAssessment, ...]
