from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ClassicalEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    entity_id: str
    entity_type: str
    canonical_name: str
    greek_name: str = ""
    aliases: tuple[str, ...]
    description: str
    authority_uris: tuple[str, ...] = ()
    curation_citations: tuple[str, ...]
    status: str = "trusted"


class ClassicalEntityMention(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    mention_id: str
    entity_id: str
    text_unit_id: str
    version_id: str
    book: int
    line_start: int
    line_end: int
    surface: str
    char_start: int
    char_end: int
    mention_role: str = "named"
    confidence: float = Field(ge=0, le=1)
    review_status: str = "deterministic_alias_match"


class Theme(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    theme_id: str
    title: str
    description: str
    aliases: tuple[str, ...] = ()
    bibliography: tuple[str, ...]
    curator: str
    status: str = "trusted"
    version: str


class ThemePassage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    theme_passage_id: str
    theme_id: str
    text_unit_id: str
    rationale: str
    evidence_class: str = "CURATED_THEMATIC_LINK"
    review_status: str = "trusted"


class EntityThemeRelease(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    release_id: str
    entities: tuple[ClassicalEntity, ...]
    mentions: tuple[ClassicalEntityMention, ...]
    themes: tuple[Theme, ...]
    theme_passages: tuple[ThemePassage, ...]
