from __future__ import annotations

import hashlib
from typing import Any

import pytest
from conftest import FakeClickHouseClient
from fastapi.testclient import TestClient

from pipelines.classics import parse_odyssey_tei, parse_odyssey_treebank
from pipelines.classics.treebank import TreebankAlignmentError
from sourcecut_api.main import create_app
from sourcecut_api.repositories import ClickHouseLinguisticRepository

REVISION = "790c84289edbdbe289dd7b752bfea29f0af4299d"
TREEBANK_REVISION = "bf4334f0af5e13d16b04c1cccd6237e683ac6f5f"


def _greek_tei() -> str:
    books = "".join(
        f'<div n="{book}" subtype="book"><l n="1">ἄνδρα πολύτροπον</l></div>'
        for book in range(1, 25)
    )
    return (
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        '<div n="urn:cts:greekLit:tlg0012.tlg002.perseus-grc2" xml:lang="grc">'
        f"{books}</div></body></text></TEI>"
    )


def _treebank() -> str:
    return (
        '<treebank cts="urn:cts:greekLit:tlg0012.tlg002.perseus-grc1.tb">'
        '<sentence id="1" subdoc="1.1"><word id="1" form="ἄνδρα" lemma="ἀνήρ" '
        'postag="n-s---ma-" relation="OBJ" cite="urn:cts:greekLit:tlg0012.tlg002:1.1"/>'
        '<word id="2" form="πολύτροπον" lemma="πολύτροπος" postag="a-s---ma-" '
        'relation="ATR" cite="urn:cts:greekLit:tlg0012.tlg002:1.1"/></sentence></treebank>'
    )


def _parsed_linguistics():
    text = parse_odyssey_tei(
        _greek_tei(),
        version_id="odyssey-perseus-grc2",
        upstream_path="odyssey.xml",
        upstream_revision=REVISION,
    )
    treebank = _treebank()
    return parse_odyssey_treebank(
        treebank,
        text_units=text.units,
        upstream_revision=TREEBANK_REVISION,
        upstream_path="odyssey-treebank.xml",
        repository_url="https://github.com/PerseusDL/treebank_data",
        expected_sha256=hashlib.sha256(treebank.encode()).hexdigest(),
    )


def test_treebank_alignment_preserves_exact_spans_and_unannotated_ambiguity() -> None:
    parsed = _parsed_linguistics()

    first = parsed.tokens[0]
    assert first.surface == "ἄνδρα"
    assert first.lemma == "ἀνήρ"
    assert first.morphology["case"] == "accusative"
    assert first.char_start == 0
    assert first.char_end == 5
    assert parsed.annotated_tokens == 2
    assert parsed.unannotated_tokens == 46
    assert parsed.tokens[2].lemma == ""
    assert parsed.tokens[2].review_status == "tokenized_unannotated"
    assert len(parsed.formulae) == 24
    assert parsed.formulae[0].review_status == "derived_unreviewed"


def test_treebank_rejects_source_hash_drift() -> None:
    text = parse_odyssey_tei(
        _greek_tei(),
        version_id="odyssey-perseus-grc2",
        upstream_path="odyssey.xml",
        upstream_revision=REVISION,
    )
    with pytest.raises(TreebankAlignmentError, match="hash"):
        parse_odyssey_treebank(
            _treebank(),
            text_units=text.units,
            upstream_revision=TREEBANK_REVISION,
            upstream_path="treebank.xml",
            repository_url="https://github.com/PerseusDL/treebank_data",
            expected_sha256="0" * 64,
        )


def test_linguistic_repository_is_idempotent() -> None:
    parsed = _parsed_linguistics()
    client = FakeClickHouseClient("corpus")
    repository = ClickHouseLinguisticRepository(client)  # type: ignore[arg-type]

    first = repository.load(parsed)
    second = repository.load(parsed)

    assert first.releases_inserted == 1
    assert first.tokens_inserted == 48
    assert first.formulae_inserted == 24
    assert second.tokens_inserted == 0
    assert client.tables["text_tokens"][0]["surface"] == "ἄνδρα"


class FakeLinguisticMcp:
    async def search_odyssey_text(self, request: Any, offset: int = 0) -> dict[str, Any]:
        del request, offset
        return {
            "rows": [
                {
                    "token_id": "token:" + "a" * 28,
                    "text_unit_id": "text-unit:odyssey-perseus-grc2:1:1-1",
                    "version_id": "odyssey-perseus-grc2",
                    "citation": "Od. 1.1",
                    "cts_urn": "urn:cts:greekLit:tlg0012.tlg002.perseus-grc2:1.1",
                    "book": 1,
                    "line_start": 1,
                    "line_end": 1,
                    "original_text": "ἄνδρα μοι ἔννεπε, μοῦσα, πολύτροπον",
                    "surface": "πολύτροπον",
                    "lemma": "πολύτροπος",
                    "part_of_speech": "adjective",
                    "morphology": {"case": "accusative"},
                    "char_start": 24,
                    "char_end": 35,
                    "annotation_source": "Perseus Ancient Greek Dependency Treebank",
                    "annotation_confidence": 0.95,
                    "review_status": "imported_unreviewed",
                    "annotation_version": "perseus-aldt-v2.1",
                }
            ]
        }

    async def get_odyssey_token(self, token_id: str) -> dict[str, Any]:
        return {
            "rows": [
                {
                    "token_id": token_id,
                    "surface": "πολύτροπον",
                    "lemma": "πολύτροπος",
                    "part_of_speech": "adjective",
                    "morphology": {},
                    "annotation_source": "Perseus",
                    "annotation_version": "v2.1",
                    "annotation_confidence": 0.95,
                    "review_status": "imported_unreviewed",
                    "occurrence_count": 2,
                }
            ]
        }

    async def get_odyssey_frequency(self, request: Any) -> list[dict[str, Any]]:
        del request
        return [{"key": "1", "count": 2}]

    async def get_odyssey_formulae(self, request: Any) -> list[dict[str, Any]]:
        del request
        return [
            {
                "formula_id": "formula:1",
                "display_formula": "πολύτροπον ἄνδρα",
                "normalized_formula": "πολυτροπον ανδρα",
                "ngram_size": 2,
                "occurrence_count": 2,
                "occurrences": [[1, 1, 1, "occ:1"]],
            }
        ]

    async def get_odyssey_cooccurrences(self, request: Any) -> list[dict[str, Any]]:
        del request
        return [{"book": 1, "left_line": 1, "right_line": 2}]


def test_search_analysis_and_saved_search_api() -> None:
    app = create_app()
    app.state.mcp_client_factory = FakeLinguisticMcp
    client = TestClient(app)
    body = {"query": "πολύτροπος", "mode": "lemma"}

    response = client.post("/api/v1/search/text", json=body)
    token_id = response.json()["hits"][0]["token"]["token_id"]
    token = client.get(f"/api/v1/tokens/{token_id}")
    frequency = client.post("/api/v1/search/frequency", json={"query": "πολύτροπος"})
    formulae = client.post("/api/v1/search/formulae", json={"query": "πολύτροπον"})
    cooccurrence = client.post(
        "/api/v1/search/cooccurrences",
        json={"left_lemma": "ἀνήρ", "right_lemma": "πολύτροπος"},
    )
    saved = client.post("/api/v1/saved-searches", json={"name": "Polytropos", "search": body})

    assert response.status_code == 200
    assert response.json()["hits"][0]["matches"] == [
        {"char_start": 24, "char_end": 35, "token_id": token_id}
    ]
    assert "derived annotations" in response.json()["warnings"][0]
    assert token.json()["occurrence_count"] == 2
    assert frequency.json()["buckets"] == [{"key": "1", "count": 2}]
    assert formulae.json()[0]["status"] == "exact_derived_pattern"
    assert cooccurrence.json()[0]["book"] == 1
    assert saved.status_code == 201
    assert len(client.get("/api/v1/saved-searches").json()) == 1
    deleted = client.delete(f"/api/v1/saved-searches/{saved.json()['saved_search_id']}")
    assert deleted.status_code == 204
