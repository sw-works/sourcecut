from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class RightsStatus(StrEnum):
    PUBLIC_DOMAIN = "public_domain"
    CC0 = "cc0"
    REUSABLE_WITH_CONDITIONS = "reusable_with_conditions"
    RIGHTS_UNCLEAR = "rights_unclear"
    RESTRICTED = "restricted"


class HistoricalRelationship(StrEnum):
    PRIMARY = "PRIMARY"
    NEAR_CONTEMPORARY = "NEAR_CONTEMPORARY"
    PERIOD_COMPARATIVE = "PERIOD_COMPARATIVE"
    LATER_REPRESENTATION = "LATER_REPRESENTATION"
    MODERN_REFERENCE = "MODERN_REFERENCE"
    REPLICA = "REPLICA"
    UNKNOWN = "UNKNOWN"


class MediaAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    asset_id: str
    provider: str
    provider_id: str
    title: str
    description: str = ""
    creators: tuple[str, ...] = ()
    asset_type: str
    creation_date_text: str = ""
    creation_year: Annotated[int, Field(ge=0, le=65535)] = 0
    subjects: tuple[str, ...] = ()
    places: tuple[str, ...] = ()
    source_url: str
    media_url: str = ""
    thumbnail_path: str = ""
    rights_status: RightsStatus
    rights_text: str = ""
    historical_relationship: HistoricalRelationship
    raw_metadata: str
    metadata_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]

    @property
    def thumbnail_approved(self) -> bool:
        return self.rights_status in {
            RightsStatus.PUBLIC_DOMAIN,
            RightsStatus.CC0,
            RightsStatus.REUSABLE_WITH_CONDITIONS,
        }
