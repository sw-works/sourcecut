from __future__ import annotations

from pathlib import Path

from conftest import FakeClickHouseClient
from fastapi.testclient import TestClient

from pipelines.classics import load_entity_theme_release, parse_odyssey_tei
from sourcecut_api.main import create_app
from sourcecut_api.repositories import ClickHouseEntityThemeRepository

ROOT = Path(__file__).parents[1]
RELEASE = ROOT / "data/reference/odyssey_entities_themes.json"


def _text():
    books = []
    for book in range(1, 25):
        lines = '<l n="1">Odysseus and Ulysses welcome Athena with hospitality.</l>'
        if book == 16:
            lines = '<l n="1">Telemachus returns to Odysseus.</l>'
        if book == 22:
            lines = '<l n="1">Odysseus takes the bow.</l>'
        if book == 1:
            lines += '<l n="26">Athena joins the divine council.</l>'
        if book == 4:
            lines += '<l n="220">Penelope remembers Odysseus.</l>'
        if book == 5:
            lines += '<l n="203">Calypso offers immortality.</l>'
        if book == 6:
            lines += '<l n="119">Athena guides Odysseus.</l>'
        if book == 9:
            lines += '<l n="19">Odysseus names himself.</l><l n="39">Odysseus wanders.</l>'
        if book == 14:
            lines += '<l n="192">Odysseus tells a story.</l>'
        if book == 23:
            lines += '<l n="205">Penelope recognizes Odysseus.</l>'
        books.append(f'<div n="{book}" subtype="book">{lines}</div>')
    return (
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        '<div n="urn:cts:greekLit:tlg0012.tlg002.perseus-grc2">'
        + "".join(books)
        + "</div></body></text></TEI>"
    )


def _release():
    parsed = parse_odyssey_tei(
        _text(),
        version_id="odyssey-perseus-grc2",
        upstream_path="test.xml",
        upstream_revision="abc",
    )
    return load_entity_theme_release(RELEASE, parsed.units)


def test_alias_mentions_are_exact_and_translation_aliases_share_identity() -> None:
    release = _release()
    odysseus = [m for m in release.mentions if m.entity_id == "odysseus"]
    assert {m.surface for m in odysseus} >= {"Odysseus", "Ulysses"}
    assert all(
        m.surface
        == next(
            u.original_text[m.char_start : m.char_end]
            for u in _release_units()
            if u.text_unit_id == m.text_unit_id
        )
        for m in odysseus
    )
    assert len(release.themes) == 12 and len(release.theme_passages) == 12


def _release_units():
    return parse_odyssey_tei(
        _text(),
        version_id="odyssey-perseus-grc2",
        upstream_path="test.xml",
        upstream_revision="abc",
    ).units


def test_entity_repository_is_idempotent() -> None:
    release = _release()
    client = FakeClickHouseClient("corpus")
    repo = ClickHouseEntityThemeRepository(client)  # type: ignore[arg-type]
    first = repo.load(release)
    second = repo.load(release)
    assert first.entities_inserted == 18 and first.themes_inserted == 12
    assert second.entities_inserted == second.mentions_inserted == second.themes_inserted == 0


class FakeEntityMcp:
    async def list_odyssey_entities(self):
        return [
            {
                "entity_id": "odysseus",
                "entity_type": "person",
                "canonical_name": "Odysseus",
                "greek_name": "Ὀδυσσεύς",
                "aliases": ["Odysseus", "Ulysses"],
                "description": "Hero",
                "authority_uris": [],
                "curation_citations": ["editorial"],
                "occurrence_count": 2,
            }
        ]

    async def get_odyssey_entity(self, entity_id):
        return [
            {
                "entity_id": entity_id,
                "entity_type": "person",
                "canonical_name": "Odysseus",
                "greek_name": "Ὀδυσσεύς",
                "aliases": ["Odysseus", "Ulysses"],
                "description": "Hero",
                "authority_uris": [],
                "curation_citations": ["editorial"],
                "mention_id": "m1",
                "surface": "Ulysses",
                "book": 1,
                "line_start": 1,
                "line_end": 1,
            }
        ]

    async def get_odyssey_relationships(self, entity_id=""):
        return [
            {
                "source_entity_id": entity_id,
                "target_entity_id": "athena",
                "relationship_kind": "exact_unit_cooccurrence",
                "interpretation_notice": "Retrieval aid only",
            }
        ]

    async def list_odyssey_themes(self):
        return [
            {
                "theme_id": "nostos",
                "title": "Nostos",
                "description": "Return",
                "aliases": [],
                "bibliography": ["editorial"],
                "curator": "SourceCut",
                "passage_count": 1,
            }
        ]

    async def get_odyssey_theme(self, theme_id):
        return [
            {
                "theme_id": theme_id,
                "title": "Nostos",
                "description": "Return",
                "aliases": [],
                "bibliography": ["editorial"],
                "curator": "SourceCut",
                "theme_passage_id": "tp1",
                "book": 1,
                "line_start": 1,
            }
        ]


def test_entity_theme_api_labels_derived_relationships() -> None:
    app = create_app()
    app.state.mcp_client_factory = FakeEntityMcp
    client = TestClient(app)
    profile = client.get("/api/v1/entities/odysseus")
    relations = client.get("/api/v1/relationships?entity_id=odysseus")
    theme = client.get("/api/v1/themes/nostos")
    assert profile.status_code == relations.status_code == theme.status_code == 200
    assert profile.json()["occurrences"][0]["surface"] == "Ulysses"
    assert relations.json()[0]["relationship_kind"] == "exact_unit_cooccurrence"
    assert "curated interpretation" in theme.json()["editorial_notice"]
