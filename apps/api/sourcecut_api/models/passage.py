from __future__ import annotations

from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from sourcecut_api.models.journal import AuthorId


class Passage(BaseModel):
    model_config = ConfigDict(frozen=True)

    passage_id: str
    entry_id: str
    source_id: str
    author_id: AuthorId
    author_display_name: str
    entry_date: date
    passage_index: Annotated[int, Field(ge=0, le=65535)]
    char_start: Annotated[int, Field(ge=0)]
    char_end: Annotated[int, Field(gt=0)]
    passage_text: str
    passage_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]

    @model_validator(mode="after")
    def validate_span_length(self) -> Passage:
        if self.char_end <= self.char_start:
            raise ValueError("char_end must be greater than char_start")
        if self.char_end - self.char_start != len(self.passage_text):
            raise ValueError("passage span length must match passage_text")
        return self
