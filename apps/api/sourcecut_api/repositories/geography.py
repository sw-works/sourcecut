from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from sourcecut_api.models.geography import GeographyRelease

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client


class GeographyDriftError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class GeographyLoadResult:
    places_inserted: int
    identifications_inserted: int
    nodes_inserted: int
    edges_inserted: int


class ClickHouseGeographyRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def load(self, release: GeographyRelease) -> GeographyLoadResult:
        now = datetime.now(UTC)
        ancient = self._missing("ancient_places", "place_id", list(release.ancient_places))
        poetic = self._missing("poetic_places", "poetic_place_id", list(release.poetic_places))
        identifications = self._missing(
            "place_identifications", "identification_id", list(release.identifications)
        )
        hypotheses = self._missing("route_hypotheses", "hypothesis_id", list(release.hypotheses))
        nodes = self._missing("route_nodes", "route_node_id", list(release.nodes))
        edges = self._missing("route_edges", "route_edge_id", list(release.edges))
        sources = self._missing("geography_sources", "source_id", list(release.sources))
        self._insert(
            "ancient_places",
            ancient,
            [
                "place_id",
                "canonical_name",
                "aliases",
                "pleiades_uri",
                "representative_lon",
                "representative_lat",
                "coordinate_certainty",
                "authority_source",
                "source_release",
                "license_id",
            ],
            release.release_id,
            now,
        )
        self._insert(
            "poetic_places",
            poetic,
            [
                "poetic_place_id",
                "canonical_name",
                "place_class",
                "default_map_behavior",
                "description",
                "review_status",
            ],
            release.release_id,
            now,
        )
        self._insert(
            "place_identifications",
            identifications,
            [
                "identification_id",
                "poetic_place_id",
                "ancient_place_id",
                "hypothesis_id",
                "identification_class",
                "longitude",
                "latitude",
                "confidence",
                "status",
                "rationale",
                "scholarly_source_ids",
                "review_status",
            ],
            release.release_id,
            now,
        )
        self._insert(
            "route_hypotheses",
            hypotheses,
            [
                "hypothesis_id",
                "title",
                "author_or_tradition",
                "description",
                "scholarly_source_ids",
                "license_id",
                "display_order",
                "is_default",
                "review_status",
            ],
            release.release_id,
            now,
        )
        self._insert(
            "route_nodes",
            nodes,
            [
                "route_node_id",
                "hypothesis_id",
                "event_id",
                "poetic_place_id",
                "identification_id",
                "sequence_index",
                "node_kind",
                "longitude",
                "latitude",
                "display_region",
                "citation_ids",
                "review_status",
            ],
            release.release_id,
            now,
        )
        self._insert(
            "route_edges",
            edges,
            [
                "route_edge_id",
                "hypothesis_id",
                "from_node_id",
                "to_node_id",
                "edge_kind",
                "sequence_index",
                "certainty",
                "citation_ids",
                "review_status",
            ],
            release.release_id,
            now,
        )
        self._insert(
            "geography_sources",
            sources,
            ["source_id", "citation", "url"],
            release.release_id,
            now,
        )
        return GeographyLoadResult(
            len(ancient) + len(poetic), len(identifications), len(nodes), len(edges)
        )

    def _missing(self, table: str, id_field: str, records: list[BaseModel]) -> list[BaseModel]:
        ids = [str(getattr(item, id_field)) for item in records]
        if not ids:
            return []
        rows = self._client.query(
            f"SELECT {id_field}, record_sha256 FROM {table} "
            f"WHERE {id_field} IN {{ids:Array(String)}}",
            parameters={"ids": ids},
        ).result_rows
        existing = {str(row[0]): _hash_text(row[1]) for row in rows}
        missing = []
        for item in records:
            key = str(getattr(item, id_field))
            if key not in existing:
                missing.append(item)
            elif existing[key] != _record_hash(item):
                raise GeographyDriftError(f"{table}.{key} has a different hash")
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
        columns = [*fields, "release_id", "record_sha256", "updated_at"]
        rows = []
        for item in records:
            dumped = item.model_dump()
            values = [
                list(dumped[field]) if isinstance(dumped[field], tuple) else dumped[field]
                for field in fields
            ]
            rows.append([*values, release_id, _record_hash(item), now])
        self._client.insert(table, rows, column_names=columns)


def _record_hash(item: BaseModel) -> str:
    return hashlib.sha256(item.model_dump_json().encode()).hexdigest()


def _hash_text(value: str | bytes) -> str:
    return value.decode("ascii") if isinstance(value, bytes) else value
