from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

AuthorId = Literal["lewis", "clark"]


class JournalEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    entry_id: str
    source_id: str
    author_id: AuthorId
    author_display_name: str
    entry_date: date
    ordinal_for_day: Annotated[int, Field(ge=1, le=65535)]
    heading: str
    raw_text: str
    source_url: str
    source_locator: str
    raw_text_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    parser_version: str
