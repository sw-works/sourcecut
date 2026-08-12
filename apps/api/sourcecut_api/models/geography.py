from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


class AncientPlace(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    place_id: str
    canonical_name: str
    aliases: tuple[str, ...] = ()
    pleiades_uri: str
    representative_lon: float
    representative_lat: float
    coordinate_certainty: str
    authority_source: str = "Pleiades"
    source_release: str
    license_id: str = "CC-BY-3.0"


class GeographySource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source_id: str
    citation: str
    url: str


class PoeticPlace(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    poetic_place_id: str
    canonical_name: str
    place_class: Literal["identified", "region", "traditional", "hypothesized", "mythic_unlocated"]
    description: str
    default_map_behavior: str
    review_status: str = "trusted"


class PlaceIdentification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    identification_id: str
    poetic_place_id: str
    ancient_place_id: str | None = None
    hypothesis_id: str
    identification_class: str
    longitude: float | None = None
    latitude: float | None = None
    confidence: str
    status: str
    rationale: str
    scholarly_source_ids: tuple[str, ...] = ()
    review_status: str = "trusted"

    @model_validator(mode="after")
    def trusted_has_source_or_unlocated(self) -> PlaceIdentification:
        if (
            self.review_status == "trusted"
            and not self.scholarly_source_ids
            and self.status != "text_only_unlocated"
        ):
            raise ValueError("Trusted place identification requires a source")
        if (self.longitude is None) != (self.latitude is None):
            raise ValueError("Longitude and latitude must be supplied together")
        return self


class RouteHypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    hypothesis_id: str
    title: str
    author_or_tradition: str
    description: str
    scholarly_source_ids: tuple[str, ...]
    license_id: str
    display_order: int
    is_default: bool = False
    review_status: str = "trusted"


class RouteNode(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    route_node_id: str
    hypothesis_id: str
    event_id: str
    poetic_place_id: str
    identification_id: str | None = None
    sequence_index: Decimal
    node_kind: str
    longitude: float | None = None
    latitude: float | None = None
    display_region: str
    citation_ids: tuple[str, ...]
    review_status: str = "trusted"


class RouteEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    route_edge_id: str
    hypothesis_id: str
    from_node_id: str
    to_node_id: str
    edge_kind: Literal["traveled", "proposed", "branch", "return", "unknown_transition"]
    sequence_index: Decimal
    certainty: str
    citation_ids: tuple[str, ...]
    review_status: str = "trusted"


class GeographyRelease(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    release_id: str
    authority_release: str
    sources: tuple[GeographySource, ...]
    ancient_places: tuple[AncientPlace, ...]
    poetic_places: tuple[PoeticPlace, ...]
    identifications: tuple[PlaceIdentification, ...]
    hypotheses: tuple[RouteHypothesis, ...]
    nodes: tuple[RouteNode, ...]
    edges: tuple[RouteEdge, ...]
