from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from sourcecut_api.models.entities import EntityThemeRelease

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client


@dataclass(frozen=True, slots=True)
class EntityThemeLoadResult:
    entities_inserted: int
    mentions_inserted: int
    themes_inserted: int
    theme_passages_inserted: int


class EntityThemeDriftError(RuntimeError):
    pass


class ClickHouseEntityThemeRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def load(self, release: EntityThemeRelease) -> EntityThemeLoadResult:
        now = datetime.now(UTC)
        groups = [
            (
                "classical_entities",
                "entity_id",
                list(release.entities),
                [
                    "entity_id",
                    "entity_type",
                    "canonical_name",
                    "greek_name",
                    "aliases",
                    "description",
                    "authority_uris",
                    "curation_citations",
                    "status",
                ],
            ),
            (
                "classical_entity_mentions",
                "mention_id",
                list(release.mentions),
                [
                    "mention_id",
                    "entity_id",
                    "text_unit_id",
                    "version_id",
                    "book",
                    "line_start",
                    "line_end",
                    "surface",
                    "char_start",
                    "char_end",
                    "mention_role",
                    "confidence",
                    "review_status",
                ],
            ),
            (
                "themes",
                "theme_id",
                list(release.themes),
                [
                    "theme_id",
                    "title",
                    "description",
                    "aliases",
                    "bibliography",
                    "curator",
                    "status",
                    "version",
                ],
            ),
            (
                "theme_passages",
                "theme_passage_id",
                list(release.theme_passages),
                [
                    "theme_passage_id",
                    "theme_id",
                    "text_unit_id",
                    "rationale",
                    "evidence_class",
                    "review_status",
                ],
            ),
        ]
        counts = []
        for table, key, records, fields in groups:
            missing = self._missing(table, key, records)
            self._insert(table, missing, fields, release.release_id, now)
            counts.append(len(missing))
        return EntityThemeLoadResult(*counts)

    def _missing(self, table: str, field: str, records: list[BaseModel]) -> list[BaseModel]:
        ids = [str(getattr(x, field)) for x in records]
        if not ids:
            return []
        rows = self._client.query(
            f"SELECT {field}, record_sha256 FROM {table} WHERE {field} IN {{ids:Array(String)}}",
            parameters={"ids": ids},
        ).result_rows
        existing = {
            str(r[0]): r[1].decode("ascii") if isinstance(r[1], bytes) else r[1] for r in rows
        }
        missing = []
        for item in records:
            key = str(getattr(item, field))
            digest = _hash(item)
            if key not in existing:
                missing.append(item)
            elif existing[key] != digest:
                raise EntityThemeDriftError(f"{table}.{key} has a different hash")
        return missing

    def _insert(
        self,
        table: str,
        records: list[BaseModel],
        fields: Sequence[str],
        release_id: str,
        now: datetime,
    ) -> None:
        if not records:
            return
        rows = []
        for item in records:
            data = item.model_dump()
            rows.append(
                [
                    *[list(data[f]) if isinstance(data[f], tuple) else data[f] for f in fields],
                    release_id,
                    _hash(item),
                    now,
                ]
            )
        self._client.insert(
            table, rows, column_names=[*fields, "release_id", "record_sha256", "updated_at"]
        )


def _hash(item: BaseModel) -> str:
    return hashlib.sha256(item.model_dump_json().encode()).hexdigest()
