from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from sourcecut_api.models.classical_text import TextUnit
from sourcecut_api.models.entities import (
    ClassicalEntity,
    ClassicalEntityMention,
    EntityThemeRelease,
    Theme,
    ThemePassage,
)


class EntityThemeReleaseError(ValueError):
    pass


def load_entity_theme_release(path: Path, text_units: tuple[TextUnit, ...]) -> EntityThemeRelease:
    payload = json.loads(path.read_text(encoding="utf-8"))
    citation = str(payload["curation_source"])
    entities = tuple(
        ClassicalEntity(
            entity_id=item[0],
            entity_type=item[1],
            canonical_name=item[2],
            greek_name=item[3],
            aliases=tuple(item[4]),
            description=item[5],
            curation_citations=(citation,),
        )
        for item in payload["entities"]
    )
    unit_index = {(u.version_id, u.book, u.line_start): u for u in text_units}
    mentions = tuple(_mentions(entities, text_units))
    themes = []
    links = []
    for item in payload["themes"]:
        theme = Theme(
            theme_id=item[0],
            title=item[1],
            description=item[2],
            aliases=tuple(item[3]),
            bibliography=(citation,),
            curator="SourceCut editorial",
            version=payload["release_id"],
        )
        unit = unit_index.get(("odyssey-perseus-grc2", int(item[4]), int(item[5])))
        if unit is None:
            raise EntityThemeReleaseError(f"Theme {theme.theme_id} references a missing Greek line")
        themes.append(theme)
        links.append(
            ThemePassage(
                theme_passage_id=f"theme-passage:{theme.theme_id}:{unit.book}:{unit.line_start}",
                theme_id=theme.theme_id,
                text_unit_id=unit.text_unit_id,
                rationale=f"Curated anchor passage for {theme.title}.",
            )
        )
    release = EntityThemeRelease(
        release_id=payload["release_id"],
        entities=entities,
        mentions=mentions,
        themes=tuple(themes),
        theme_passages=tuple(links),
    )
    if not mentions:
        raise EntityThemeReleaseError("Entity release contains no exact alias matches")
    return release


def _mentions(entities: tuple[ClassicalEntity, ...], units: tuple[TextUnit, ...]):
    for unit in units:
        occupied: list[tuple[int, int]] = []
        aliases = sorted(
            (
                (alias, entity)
                for entity in entities
                if entity.entity_type in {"person", "god", "group", "creature", "place"}
                for alias in entity.aliases
            ),
            key=lambda item: len(item[0]),
            reverse=True,
        )
        for alias, entity in aliases:
            for match in re.finditer(re.escape(alias), unit.original_text, flags=re.IGNORECASE):
                if any(match.start() < end and match.end() > start for start, end in occupied):
                    continue
                occupied.append((match.start(), match.end()))
                digest = hashlib.sha256(
                    f"{entity.entity_id}:{unit.text_unit_id}:{match.start()}:{match.end()}".encode()
                ).hexdigest()[:24]
                yield ClassicalEntityMention(
                    mention_id=f"classical-mention:{digest}",
                    entity_id=entity.entity_id,
                    text_unit_id=unit.text_unit_id,
                    version_id=unit.version_id,
                    book=unit.book,
                    line_start=unit.line_start,
                    line_end=unit.line_end,
                    surface=match.group(),
                    char_start=match.start(),
                    char_end=match.end(),
                    confidence=1.0,
                )
