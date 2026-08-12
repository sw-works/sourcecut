from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from sourcecut_api.models.visual_culture import VisualCultureRelease

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client


@dataclass(frozen=True, slots=True)
class VisualCultureLoadResult:
    metadata_inserted: int
    links_inserted: int
    assessments_inserted: int


class VisualCultureDriftError(RuntimeError):
    pass


class ClickHouseVisualCultureRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def load(self, release: VisualCultureRelease) -> VisualCultureLoadResult:
        now = datetime.now(UTC)
        groups = [
            (
                "odyssey_asset_metadata",
                "asset_id",
                list(release.metadata),
                [
                    "asset_id",
                    "institution",
                    "object_id",
                    "culture",
                    "period",
                    "object_date",
                    "object_begin_date",
                    "object_end_date",
                    "medium",
                    "image_rights_status",
                    "image_attribution",
                    "cached_image_path",
                    "public_display",
                ],
            ),
            (
                "asset_corpus_links",
                "asset_link_id",
                list(release.links),
                [
                    "asset_link_id",
                    "asset_id",
                    "corpus_id",
                    "target_kind",
                    "target_id",
                    "relationship_class",
                    "review_status",
                ],
            ),
            (
                "asset_relationship_assessments",
                "assessment_id",
                list(release.assessments),
                [
                    "assessment_id",
                    "asset_id",
                    "relationship_class",
                    "production_use",
                    "limitations",
                    "evidence_ids",
                    "confidence",
                    "verification_status",
                    "review_status",
                ],
            ),
        ]
        counts = []
        for table, key, records, fields in groups:
            missing = self._missing(table, key, records)
            self._insert(table, missing, fields, release.release_id, now)
            counts.append(len(missing))
        return VisualCultureLoadResult(*counts)

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
                raise VisualCultureDriftError(f"{table}.{key} has a different hash")
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
