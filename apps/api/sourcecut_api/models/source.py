from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class SourceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    provider: str
    title: str
    source_url: str
    edition_notes: str = ""
    rights_status: str
    raw_metadata: str = "{}"
    content_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
