from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path

from sourcecut_api.models.geography import (
    AncientPlace,
    GeographyRelease,
    GeographySource,
    PlaceIdentification,
    PoeticPlace,
    RouteEdge,
    RouteHypothesis,
    RouteNode,
)


class GeographyReleaseError(ValueError):
    pass


def load_geography_release(path: Path) -> GeographyRelease:
    payload = json.loads(path.read_text(encoding="utf-8"))
    poetic_places = tuple(
        PoeticPlace(
            poetic_place_id=item[0],
            canonical_name=item[1],
            place_class=item[2],
            description=item[3],
            default_map_behavior=item[4],
        )
        for item in payload["poetic_places"]
    )
    nodes = []
    for index, (place, event, citation) in enumerate(payload["sequence"], 1):
        match = re.fullmatch(r"(\d+)\.(\d+)-(\d+)\.(\d+)", citation)
        if match is None or match.group(1) != match.group(3):
            raise GeographyReleaseError(f"Invalid route citation: {citation}")
        book, start, _, end = match.groups()
        nodes.append(
            RouteNode(
                route_node_id=f"route-node:textual:{index:02}",
                hypothesis_id="textual_sequence",
                event_id=event,
                poetic_place_id=place,
                sequence_index=Decimal(index),
                node_kind="textual",
                display_region="beyond"
                if place
                in {
                    "lotus-eaters",
                    "cyclopes-land",
                    "aeolia",
                    "laestrygonia",
                    "aeaea",
                    "underworld",
                    "sirens",
                    "thrinacia",
                    "ogygia",
                }
                else "mediterranean",
                citation_ids=(
                    f"urn:cts:greekLit:tlg0012.tlg002.perseus-grc2:{book}.{start}-{end}",
                ),
            )
        )
    edges = tuple(
        RouteEdge(
            route_edge_id=f"route-edge:textual:{index:02}",
            hypothesis_id="textual_sequence",
            from_node_id=nodes[index - 1].route_node_id,
            to_node_id=nodes[index].route_node_id,
            edge_kind="return" if nodes[index].poetic_place_id == "aeaea" else "unknown_transition",
            sequence_index=Decimal(index),
            certainty="textual_sequence",
            citation_ids=nodes[index].citation_ids,
        )
        for index in range(1, len(nodes))
    )
    release = GeographyRelease(
        release_id=payload["release_id"],
        authority_release=payload["authority_release"],
        sources=tuple(GeographySource.model_validate(item) for item in payload["sources"]),
        ancient_places=tuple(
            AncientPlace.model_validate(item) for item in payload["ancient_places"]
        ),
        poetic_places=poetic_places,
        identifications=tuple(
            PlaceIdentification.model_validate(item) for item in payload["identifications"]
        ),
        hypotheses=tuple(RouteHypothesis.model_validate(item) for item in payload["hypotheses"]),
        nodes=tuple(nodes),
        edges=edges,
    )
    validate_geography_release(release)
    return release


def validate_geography_release(release: GeographyRelease) -> None:
    places = {item.poetic_place_id for item in release.poetic_places}
    nodes = {item.route_node_id for item in release.nodes}
    hypotheses = {item.hypothesis_id for item in release.hypotheses}
    sources = {item.source_id for item in release.sources}
    if len(nodes) != len(release.nodes):
        raise GeographyReleaseError("Duplicate route node")
    if not {"textual_sequence", "berard", "bradford"} <= hypotheses:
        raise GeographyReleaseError("Textual and two named comparison hypotheses are required")
    for item in (*release.identifications, *release.hypotheses):
        if not set(item.scholarly_source_ids) <= sources:
            raise GeographyReleaseError("Geography record references an unknown source")
    if any(item.poetic_place_id not in places for item in release.nodes):
        raise GeographyReleaseError("Route node references an unknown poetic place")
    if any(
        item.from_node_id not in nodes or item.to_node_id not in nodes for item in release.edges
    ):
        raise GeographyReleaseError("Route edge references an unknown node")
    for place in release.poetic_places:
        if place.place_class == "mythic_unlocated":
            matching = [
                item
                for item in release.identifications
                if item.poetic_place_id == place.poetic_place_id
            ]
            if any(item.hypothesis_id == "secure_places" for item in matching):
                raise GeographyReleaseError("Mythic place cannot receive a secure coordinate")
    if len(release.nodes) < 15 or len(release.edges) != len(release.nodes) - 1:
        raise GeographyReleaseError("The complete voyage sequence is required")
