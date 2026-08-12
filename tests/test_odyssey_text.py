from __future__ import annotations

from typing import Any

import pytest
from conftest import FakeClickHouseClient
from fastapi.testclient import TestClient

from pipelines.classics import OdysseyTeiError, build_classical_passages, parse_odyssey_tei
from sourcecut_api.corpora import CorpusRegistry
from sourcecut_api.corpora.odyssey import OdysseyCorpusAdapter
from sourcecut_api.main import create_app
from sourcecut_api.repositories import ClickHouseClassicalTextRepository
from sourcecut_api.services.citations import CitationResolutionError, CitationResolver

REVISION = "790c84289edbdbe289dd7b752bfea29f0af4299d"


def _tei(*, prose: bool = False, books: int = 24) -> str:
    content = []
    for book in range(1, books + 1):
        if prose:
            body = (
                f'<div type="textpart" n="1" subtype="card"><p>'
                f'<milestone n="1" unit="line"/>Book {book} opening. '
                f'<name>Odysseus</name> travels. '
                f'<milestone n="4" unit="line"/>Book {book} continues.'
                f"</p></div>"
            )
        else:
            body = f'<l n="1">Book {book} line one</l><l n="2">Book {book} line two</l>'
        content.append(f'<div n="{book}" type="textpart" subtype="book">{body}</div>')
    kind = "translation" if prose else "edition"
    version = "perseus-eng4" if prose else "perseus-grc2"
    language = "eng" if prose else "grc"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        f'<div type="{kind}" n="urn:cts:greekLit:tlg0012.tlg002.{version}" '
        f'xml:lang="{language}">'
        + "".join(content)
        + "</div></body></text></TEI>"
    )


def _parse(raw: str, version_id: str):
    return parse_odyssey_tei(
        raw,
        version_id=version_id,
        upstream_path=f"data/{version_id}.xml",
        upstream_revision=REVISION,
    )


def test_parser_preserves_all_verse_books_and_stable_citations() -> None:
    parsed = _parse(_tei(), "odyssey-perseus-grc2")

    assert len(parsed.units) == 48
    assert {unit.book for unit in parsed.units} == set(range(1, 25))
    assert parsed.units[0].citation == "Od. 1.1"
    assert parsed.units[0].cts_urn.endswith("perseus-grc2:1.1")
    assert parsed.units[-1].citation == "Od. 24.2"
    assert parsed.document.raw_sha256 == parsed.document.document_id.rsplit(":", 1)[-1]


def test_parser_converts_prose_milestones_to_citable_ranges() -> None:
    parsed = _parse(_tei(prose=True), "odyssey-perseus-eng4")
    first, second = parsed.units[:2]

    assert first.line_start == 1
    assert first.line_end == 3
    assert first.citation == "Od. 1.1–3"
    assert first.original_text == "Book 1 opening. Odysseus travels."
    assert second.line_start == second.line_end == 4


def test_parser_rejects_missing_book_and_malformed_xml() -> None:
    with pytest.raises(OdysseyTeiError, match="books 1–24"):
        _parse(_tei(books=23), "odyssey-perseus-grc2")
    with pytest.raises(OdysseyTeiError, match="Malformed"):
        _parse("<TEI>", "odyssey-perseus-grc2")


def test_parser_reports_and_canonicalizes_upstream_non_monotonic_markers() -> None:
    raw = _tei().replace(
        '<l n="1">Book 3 line one</l><l n="2">Book 3 line two</l>',
        '<l n="2">Book 3 line two</l><l n="1">Book 3 line one</l>',
    )

    parsed = _parse(raw, "odyssey-perseus-grc2")
    book_three = [unit for unit in parsed.units if unit.book == 3]

    assert [unit.line_start for unit in book_three] == [1, 2]
    assert parsed.warnings == (
        "Upstream non-monotonic line marker at "
        "urn:cts:greekLit:tlg0012.tlg002.perseus-grc2:3.1",
    )


def test_parser_applies_auditable_manifest_citation_corrections() -> None:
    raw = _tei(prose=True).replace(
        '<milestone n="4" unit="line"/>Book 6 continues.',
        '<milestone n="1" unit="line"/>Book 6 continues.',
    )

    parsed = parse_odyssey_tei(
        raw,
        version_id="odyssey-perseus-eng4",
        upstream_path="data/eng4.xml",
        upstream_revision=REVISION,
        citation_corrections={(6, 1): 4},
    )
    corrected = [unit for unit in parsed.units if unit.book == 6][1]

    assert corrected.line_start == 4
    assert corrected.source_line_start == 1
    assert corrected.citation_correction.startswith("Applied manifest citation correction")
    assert corrected.citation_correction in parsed.warnings


def test_passage_generation_is_deterministic_and_overlapping() -> None:
    parsed = _parse(_tei(), "odyssey-perseus-grc2")

    first = build_classical_passages(parsed.units, window_size=2, overlap=1)
    second = build_classical_passages(parsed.units, window_size=2, overlap=1)

    assert first == second
    assert len(first) == 24
    assert first[0].line_start == 1
    assert first[0].line_end == 2
    assert first[0].passage_text == "Book 1 line one\nBook 1 line two"


def test_classical_repository_is_idempotent_and_rejects_drift() -> None:
    parsed = _parse(_tei(), "odyssey-perseus-grc2")
    passages = build_classical_passages(parsed.units)
    client = FakeClickHouseClient("corpus")
    repository = ClickHouseClassicalTextRepository(client)  # type: ignore[arg-type]

    first = repository.load_version(parsed, passages)
    second = repository.load_version(parsed, passages)

    assert first.documents_inserted == 1
    assert first.units_inserted == 48
    assert first.passages_inserted == 24
    assert second.documents_inserted == 0
    assert second.units_inserted == 0
    assert second.passages_inserted == 0
    assert client.tables["text_units"][0]["original_text"] == "Book 1 line one"


def test_citation_resolver_accepts_conventional_and_cts_references() -> None:
    resolver = CitationResolver(
        {"odyssey-perseus-grc2": "urn:cts:greekLit:tlg0012.tlg002.perseus-grc2"}
    )

    conventional = resolver.resolve("Od. 9.216-230", "odyssey-perseus-grc2")
    cts = resolver.resolve(
        "urn:cts:greekLit:tlg0012.tlg002.perseus-grc2:9.216-9.230",
        "odyssey-perseus-grc2",
    )

    assert conventional == cts
    assert conventional.citation == "Od. 9.216–230"
    assert conventional.canonical_url.endswith("lines=216-230")
    with pytest.raises(CitationResolutionError, match="one of Odyssey books"):
        resolver.resolve("Od. 25.1", "odyssey-perseus-grc2")
    with pytest.raises(CitationResolutionError, match="exceeds"):
        resolver.resolve("Od. 1.1-900", "odyssey-perseus-grc2")


class FakeTextMcp:
    def __init__(self) -> None:
        self.parallel_calls = 0

    async def get_classical_text(
        self, version_id: str, book: int, line_start: int, line_end: int
    ) -> dict[str, Any]:
        del line_end
        return {
            "version_id": version_id,
            "units": [
                {
                    "text_unit_id": f"text-unit:{version_id}:{book}:{line_start}",
                    "citation": f"Od. {book}.{line_start}",
                    "cts_urn": (
                        "urn:cts:greekLit:tlg0012.tlg002.perseus-grc2:"
                        f"{book}.{line_start}"
                    ),
                    "book": book,
                    "line_start": line_start,
                    "line_end": line_start,
                    "original_text": "ἄνδρα μοι ἔννεπε, μοῦσα",
                }
            ],
        }

    async def get_parallel_classical_text(
        self, version_ids: list[str], book: int, line_start: int, line_end: int
    ) -> list[dict[str, Any]]:
        self.parallel_calls += 1
        return [
            await self.get_classical_text(version, book, line_start, line_end)
            for version in version_ids
        ]


def test_text_api_resolves_and_returns_attributed_parallel_ranges() -> None:
    app = create_app(corpus_registry=CorpusRegistry((OdysseyCorpusAdapter(),)))
    fake = FakeTextMcp()
    app.state.mcp_client_factory = lambda: fake
    client = TestClient(app)

    resolved = client.get(
        "/api/v1/text/resolve",
        params={"reference": "Od. 1.1-2", "version_id": "odyssey-perseus-grc2"},
    )
    text = client.get(
        "/api/v1/text/odyssey-perseus-grc2/1",
        params={"from_line": 1, "to_line": 20},
    )
    parallel = client.get(
        "/api/v1/text/odyssey-perseus-grc2/1/parallel",
        params=[
            ("from_line", "1"),
            ("to_line", "20"),
            ("targets", "odyssey-perseus-eng3"),
        ],
    )
    cached_parallel = client.get(
        "/api/v1/text/odyssey-perseus-grc2/1/parallel",
        params=[
            ("from_line", "1"),
            ("to_line", "20"),
            ("targets", "odyssey-perseus-eng3"),
        ],
    )

    assert resolved.status_code == 200
    assert resolved.json()["cts_urn"].endswith(":1.1-1.2")
    assert text.status_code == 200
    assert text.headers["cache-control"].startswith("public, max-age=3600")
    assert text.json()["attribution"] == "Text provided by the Perseus Digital Library."
    assert text.json()["units"][0]["text"].startswith("ἄνδρα")
    assert parallel.status_code == 200
    assert len(parallel.json()["targets"]) == 1
    assert "not independent" in parallel.json()["warning"]
    assert cached_parallel.json() == parallel.json()
    assert fake.parallel_calls == 1
    assert client.get("/api/v1/text/odyssey-perseus-grc2/25").status_code == 422
    assert (
        client.get(
            "/api/v1/text/odyssey-perseus-grc2/1",
            params={"from_line": 1, "to_line": 500},
        ).status_code
        == 422
    )
