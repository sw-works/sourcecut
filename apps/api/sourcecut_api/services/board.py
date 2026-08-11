from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import mimetypes
import os
import re
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from google import genai
from google.genai import types

from sourcecut_api.integrations.clickhouse_mcp import ClickHouseMcpClient, ClickHouseMcpSettings
from sourcecut_api.models import (
    AgreementCell,
    AssetRequirement,
    BoardConfidence,
    BoardMediaAsset,
    BoardSection,
    EvidenceCitation,
    HistoricalRelationship,
    MediaAsset,
    ResearchBoard,
    RightsStatus,
    VerifiedAsset,
    VisualInspection,
)
from sourcecut_api.telemetry import sanitize_sql

BITTERROOT_START = 18050909
BITTERROOT_END = 18050930
DEFAULT_MODEL = "gemini-2.5-flash"
REUSABLE_RIGHTS = {
    RightsStatus.PUBLIC_DOMAIN,
    RightsStatus.CC0,
    RightsStatus.REUSABLE_WITH_CONDITIONS,
}
STOP_WORDS = {
    "and",
    "for",
    "from",
    "historical",
    "image",
    "lewis",
    "reference",
    "the",
    "visual",
    "with",
}

EVIDENCE_QUERY = f"""
SELECT
    observation_id,
    passage_id,
    author_display_name,
    entry_date,
    category,
    canonical_term,
    source_quote,
    confidence
FROM sourcecut.evidence_window(
    start={BITTERROOT_START},
    end={BITTERROOT_END},
    limit=200
)
LIMIT 200
""".strip()

MEDIA_QUERY = """
SELECT
    asset_id,
    provider,
    provider_id,
    title,
    description,
    creators,
    asset_type,
    creation_date_text,
    creation_year,
    subjects,
    places,
    source_url,
    media_url,
    thumbnail_path,
    rights_status,
    rights_text,
    historical_relationship,
    raw_metadata,
    metadata_sha256
FROM sourcecut.media_assets FINAL
ORDER BY provider, rights_status, asset_type, creation_year, asset_id
LIMIT 200
""".strip()

PASSAGE_EVIDENCE_QUERY = f"""
SELECT passage_id, author_display_name, entry_date, passage_text
FROM sourcecut.passages FINAL
WHERE entry_date BETWEEN {BITTERROOT_START} AND {BITTERROOT_END}
ORDER BY entry_date, author_id, passage_id
LIMIT 200
""".strip()

CATEGORY_REQUIREMENTS = {
    "weather": (
        "Weather and exposure",
        "Visual references for cold, precipitation, and exposed mountain travel.",
        ("snow", "cold", "rain", "mountain", "bitterroot", "rocky"),
    ),
    "terrain": (
        "Route geography and terrain",
        "Maps and landscape references for steep, forested Bitterroot route geography.",
        ("mountain", "trail", "rock", "timber", "bitterroot", "rocky", "map"),
    ),
    "transportation": (
        "Expedition transportation",
        "References for horse travel and constrained movement on mountain trails.",
        ("horse", "trail", "expedition", "lewis", "clark", "bitterroot"),
    ),
    "food": (
        "Food scarcity",
        "Documentary references for expedition provisions and food scarcity.",
        ("food", "hunger", "provision", "expedition", "lewis", "clark"),
    ),
    "shelter": (
        "Camp and shelter",
        "References for temporary camps and shelter in mountain conditions.",
        ("camp", "shelter", "mountain", "expedition", "lewis", "clark"),
    ),
    "equipment": (
        "Clothing and equipment",
        "Documentary references for expedition clothing and field equipment.",
        ("equipment", "clothing", "expedition", "lewis", "clark"),
    ),
}

VISUAL_RESPONSE_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    required=["relevant", "visible_findings", "mismatch_flags"],
    properties={
        "relevant": types.Schema(type=types.Type.BOOLEAN),
        "visible_findings": types.Schema(type=types.Type.STRING),
        "mismatch_flags": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(type=types.Type.STRING),
        ),
    },
)


class RuntimeMcpClient(Protocol):
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


class VisualInspector(Protocol):
    async def inspect(
        self,
        asset: MediaAsset,
        requirement: AssetRequirement,
    ) -> VisualInspection: ...


EventSink = Callable[[str, str, str, str, dict[str, Any], int], None]


class QueryEmbedder(Protocol):
    def embed_query(self, text: str) -> tuple[float, ...]: ...


class GeminiVisualInspector:
    def __init__(
        self,
        client: Any,
        *,
        model: str = DEFAULT_MODEL,
        cache_root: Path = Path("data/archive-cache/loc"),
    ) -> None:
        self._client = client
        self._model = model
        self._cache_root = cache_root.resolve()

    async def inspect(
        self,
        asset: MediaAsset,
        requirement: AssetRequirement,
    ) -> VisualInspection:
        image_path = Path(asset.thumbnail_path).resolve()
        if not image_path.is_relative_to(self._cache_root):
            raise ValueError("Thumbnail path is outside the approved LOC cache")
        if not image_path.is_file():
            raise ValueError(f"Cached thumbnail is missing: {asset.thumbnail_path}")
        mime_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
        prompt = (
            "Inspect only what is visibly present in this archival thumbnail. "
            "Do not infer ownership, date, location, or historical provenance from appearance.\n"
            f"Requirement: {requirement.production_need}\n"
            f"Catalog title: {asset.title}\n"
            "Mark relevant only when visible features help the stated production requirement."
        )

        def generate() -> Any:
            return self._client.models.generate_content(
                model=self._model,
                contents=[
                    prompt,
                    types.Part.from_bytes(data=image_path.read_bytes(), mime_type=mime_type),
                ],
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                    response_schema=VISUAL_RESPONSE_SCHEMA,
                ),
            )

        response = await asyncio.to_thread(generate)
        if isinstance(response.parsed, VisualInspection):
            return response.parsed
        if response.parsed is not None:
            return VisualInspection.model_validate(response.parsed)
        if response.text is None:
            raise ValueError("Gemini returned no visual inspection")
        return VisualInspection.model_validate_json(response.text)


class ResearchBoardService:
    def __init__(
        self,
        mcp_client: RuntimeMcpClient,
        *,
        visual_inspector: VisualInspector | None = None,
        visual_inspection_limit: int = 2,
        event_sink: EventSink | None = None,
        embedder: QueryEmbedder | None = None,
    ) -> None:
        self._mcp = mcp_client
        self._visual_inspector = visual_inspector
        self._visual_inspection_limit = visual_inspection_limit
        self.event_sink = event_sink
        self._embedder = embedder

    async def build_board(self, prompt: str) -> ResearchBoard:
        evidence = await self._load_evidence(prompt)
        requirements = build_asset_requirements(evidence)
        requirements = tuple(
            [await self._with_agreement(requirement) for requirement in requirements]
        )
        assets = await self._load_media_assets()
        reviewed: list[VerifiedAsset] = []
        sections: list[BoardSection] = []
        inspected = 0
        inspection_failures = 0

        for requirement in requirements:
            ranked = await self._rank_assets(requirement, assets)
            requirement_reviews: list[VerifiedAsset] = []
            for asset in ranked[:5]:
                inspection = None
                initial = verify_asset(asset, requirement)
                if (
                    initial.confidence is BoardConfidence.INTERPRETIVE
                    and self._visual_inspector is not None
                    and asset.thumbnail_path
                    and inspected < self._visual_inspection_limit
                ):
                    try:
                        inspection = await self._visual_inspector.inspect(asset, requirement)
                    except Exception:
                        inspection_failures += 1
                    inspected += 1
                verified = verify_asset(asset, requirement, visual_inspection=inspection)
                requirement_reviews.append(verified)
                reviewed.append(verified)

            selected = tuple(
                item
                for item in requirement_reviews
                if item.confidence
                in {
                    BoardConfidence.HIGH,
                    BoardConfidence.SINGLE_SOURCE,
                    BoardConfidence.INTERPRETIVE,
                }
            )[:3]
            if selected:
                sections.append(BoardSection(title=requirement.title, assets=selected))

        warnings = _warnings(reviewed, requirements, assets, inspection_failures)
        self._emit(
            "verification_completed",
            "verification",
            "complete",
            "Archive candidates passed rights and visual verification.",
            {
                "reviewed_count": len(reviewed),
                "inspection_count": inspected,
                "failure_count": inspection_failures,
            },
        )
        authors = sorted({citation.author_display_name for citation in evidence})
        return ResearchBoard(
            prompt=prompt,
            title="Crossing the Bitterroots — September 1805",
            summary=(
                f"Evidence-derived board with {len(requirements)} requirements, "
                f"{sum(len(section.assets) for section in sections)} selected asset references, "
                f"and exact passage drill-down."
            ),
            evidence_matrix=requirements,
            sections=tuple(sections),
            reviewed_assets=tuple(reviewed),
            warnings=warnings,
            sources_used=("Library of Congress", *authors),
        )

    async def _load_evidence(self, prompt: str) -> tuple[EvidenceCitation, ...]:
        columns, rows = await self._run_query(EVIDENCE_QUERY, "evidence")
        observations = tuple(
            EvidenceCitation(
                observation_id=str(_field(row, columns, "observation_id")),
                passage_id=str(_field(row, columns, "passage_id")),
                author_display_name=str(_field(row, columns, "author_display_name")),
                entry_date=int(_field(row, columns, "entry_date")),
                category=str(_field(row, columns, "category")),
                canonical_term=str(_field(row, columns, "canonical_term")),
                source_quote=str(_field(row, columns, "source_quote")),
                confidence=float(_field(row, columns, "confidence")),
            )
            for row in rows
        )
        semantic_rows: list[Any] = []
        semantic_columns: list[str] = []
        if self._embedder is not None:
            vector = await asyncio.to_thread(self._embedder.embed_query, prompt)
            semantic_columns, semantic_rows = await self._run_query(
                _semantic_passage_query(vector), "semantic_evidence"
            )
        semantic_evidence = _derive_passage_evidence(semantic_rows, semantic_columns)
        if observations:
            return _unique_citations((*observations, *semantic_evidence))
        self._emit(
            "fallback",
            "evidence",
            "active",
            "Validated observations were empty; passage-level evidence fallback activated.",
            {"reason": "no_validated_observations"},
        )
        passage_columns, passage_rows = await self._run_query(
            PASSAGE_EVIDENCE_QUERY, "evidence_fallback"
        )
        fallback = _derive_passage_evidence(passage_rows, passage_columns)
        return _unique_citations((*semantic_evidence, *fallback))

    async def _load_media_assets(self) -> tuple[MediaAsset, ...]:
        columns, rows = await self._run_query(MEDIA_QUERY, "media")
        return tuple(_media_asset(row, columns) for row in rows)

    async def _with_agreement(self, requirement: AssetRequirement) -> AssetRequirement:
        term = requirement.search_terms[0].replace("'", "''")
        query = f"""
SELECT author_id, author_display_name, entry_date, mention_count,
       observation_count, passage_ids
FROM sourcecut.author_date_matrix(
    term='{term}', start={BITTERROOT_START}, end={BITTERROOT_END}
)
LIMIT 500
""".strip()
        columns, rows = await self._run_query(query, "agreement")
        if not rows:
            return requirement
        authors = {
            str(_field(row, columns, "author_id")): str(
                _field(row, columns, "author_display_name")
            )
            for row in rows
        }
        indexed = {
            (
                str(_field(row, columns, "author_id")),
                int(_field(row, columns, "entry_date")),
            ): row
            for row in rows
        }
        cells: list[AgreementCell] = []
        for author_id, author_name in authors.items():
            for entry_date in range(BITTERROOT_START, BITTERROOT_END + 1):
                row = indexed.get((author_id, entry_date))
                if row is None:
                    cells.append(
                        AgreementCell(
                            author_id=author_id,
                            author_display_name=author_name,
                            entry_date=entry_date,
                            state="no_entry",
                        )
                    )
                    continue
                mentions = int(_field(row, columns, "mention_count"))
                observations = int(_field(row, columns, "observation_count"))
                cells.append(
                    AgreementCell(
                        author_id=author_id,
                        author_display_name=author_name,
                        entry_date=entry_date,
                        state=(
                            "mentions"
                            if mentions or observations
                            else "entry_without_mention"
                        ),
                        mention_count=mentions,
                        observation_count=observations,
                        passage_ids=tuple(_field(row, columns, "passage_ids")),
                    )
                )
        supporting = [cell for cell in cells if cell.state == "mentions"]
        return requirement.model_copy(
            update={
                "agreement": tuple(cells),
                "corroboration_authors": len({cell.author_id for cell in supporting}),
                "corroboration_days": len({cell.entry_date for cell in supporting}),
            }
        )

    async def _rank_assets(
        self,
        requirement: AssetRequirement,
        token_assets: Sequence[MediaAsset],
    ) -> list[MediaAsset]:
        token_ranked = sorted(
            token_assets,
            key=lambda asset: (_match_score(asset, requirement), asset.asset_id),
            reverse=True,
        )
        if self._embedder is None:
            return token_ranked
        requirement_text = "\n".join(
            (requirement.title, requirement.production_need, *requirement.search_terms)
        )
        vector = await asyncio.to_thread(self._embedder.embed_query, requirement_text)
        columns, rows = await self._run_query(
            _semantic_media_query(vector), "semantic_media"
        )
        semantic_ranked = [_media_asset(row, columns) for row in rows]
        return list(
            {
                asset.asset_id: asset
                for asset in (*semantic_ranked, *token_ranked)
            }.values()
        )

    async def _run_query(self, query: str, stage: str) -> tuple[list[str], list[Any]]:
        started = time.perf_counter()
        try:
            payload = await self._mcp.call_tool("run_query", {"query": query})
            columns, rows = _query_rows(payload)
        except Exception:
            self._emit(
                "mcp_tool_call",
                stage,
                "failed",
                "ClickHouse MCP query failed.",
                {
                    "tool": "run_query",
                    "access_path": "mcp_runtime",
                    "sql": sanitize_sql(query),
                    "row_count": 0,
                },
                int((time.perf_counter() - started) * 1000),
            )
            raise
        self._emit(
            "mcp_tool_call",
            stage,
            "complete",
            f"ClickHouse MCP returned {len(rows)} row(s).",
            {
                "tool": "run_query",
                "access_path": "mcp_runtime",
                "sql": sanitize_sql(query),
                "row_count": len(rows),
            },
            int((time.perf_counter() - started) * 1000),
        )
        return columns, rows

    def _emit(
        self,
        event_type: str,
        stage: str,
        status: str,
        message: str,
        payload: dict[str, Any],
        duration_ms: int = 0,
    ) -> None:
        if self.event_sink is not None:
            self.event_sink(
                event_type,
                stage,
                status,
                message,
                payload,
                duration_ms,
            )


def build_asset_requirements(
    evidence: Sequence[EvidenceCitation],
) -> tuple[AssetRequirement, ...]:
    grouped: defaultdict[str, list[EvidenceCitation]] = defaultdict(list)
    for citation in evidence:
        grouped[citation.category].append(citation)

    requirements: list[AssetRequirement] = []
    for category, (title, need, base_terms) in CATEGORY_REQUIREMENTS.items():
        citations = tuple(grouped.get(category, ()))
        if not citations:
            continue
        observed_terms = tuple(sorted({item.canonical_term.casefold() for item in citations}))
        requirements.append(
            AssetRequirement(
                requirement_id=f"bitterroot:{category}",
                title=title,
                category=category,
                production_need=need,
                search_terms=tuple(dict.fromkeys((*base_terms, *observed_terms))),
                evidence=citations[:12],
            )
        )
    return tuple(requirements)


def _unique_citations(
    citations: Sequence[EvidenceCitation],
) -> tuple[EvidenceCitation, ...]:
    unique: dict[str, EvidenceCitation] = {}
    for citation in citations:
        unique.setdefault(citation.observation_id, citation)
    return tuple(unique.values())


def _derive_passage_evidence(
    rows: Sequence[Any], columns: list[str]
) -> tuple[EvidenceCitation, ...]:
    citations: list[EvidenceCitation] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        passage_id = str(_field(row, columns, "passage_id"))
        passage_text = str(_field(row, columns, "passage_text"))
        lowered = passage_text.casefold()
        for category, terms in _category_terms().items():
            match = next(
                (
                    (term, lowered.find(term.casefold()))
                    for term in terms
                    if lowered.find(term.casefold()) >= 0
                ),
                None,
            )
            if match is None or (passage_id, category) in seen:
                continue
            term, start = match
            quote_start = max(0, start - 100)
            quote_end = min(len(passage_text), start + len(term) + 100)
            quote = passage_text[quote_start:quote_end].strip()
            digest = hashlib.sha256(
                f"{passage_id}\0{category}\0{start}".encode()
            ).hexdigest()[:24]
            citations.append(
                EvidenceCitation(
                    observation_id=f"passage-term:{digest}",
                    passage_id=passage_id,
                    author_display_name=str(
                        _field(row, columns, "author_display_name")
                    ),
                    entry_date=int(_field(row, columns, "entry_date")),
                    category=category,
                    canonical_term=term,
                    source_quote=quote,
                    confidence=1.0,
                )
            )
            seen.add((passage_id, category))
    return tuple(citations)


@lru_cache(maxsize=1)
def _category_terms() -> dict[str, tuple[str, ...]]:
    records = json.loads(
        Path("data/reference/term_expansions.json").read_text(encoding="utf-8")
    )
    grouped: defaultdict[str, list[str]] = defaultdict(list)
    for record in records:
        grouped[str(record["category"])].extend(str(value) for value in record["expansions"])
    return {category: tuple(dict.fromkeys(terms)) for category, terms in grouped.items()}


def verify_asset(
    asset: MediaAsset,
    requirement: AssetRequirement,
    *,
    visual_inspection: VisualInspection | None = None,
) -> VerifiedAsset:
    if asset.rights_status not in REUSABLE_RIGHTS:
        confidence = BoardConfidence.RIGHTS_REJECTED
        reason = "Rejected because item-level rights are not explicitly reusable."
    elif _match_score(asset, requirement) == 0:
        confidence = BoardConfidence.UNSUPPORTED
        reason = "Archive metadata does not match this evidence-derived requirement."
    elif visual_inspection is not None and not visual_inspection.relevant:
        confidence = BoardConfidence.UNSUPPORTED
        reason = "Gemini visual inspection found no visible support for this requirement."
    elif asset.historical_relationship in {
        HistoricalRelationship.PRIMARY,
        HistoricalRelationship.NEAR_CONTEMPORARY,
    }:
        author_count = len({item.author_display_name for item in requirement.evidence})
        confidence = (
            BoardConfidence.HIGH if author_count >= 2 else BoardConfidence.SINGLE_SOURCE
        )
        reason = "Reusable archive metadata matches the requirement and is near-contemporary."
    else:
        confidence = BoardConfidence.INTERPRETIVE
        reason = (
            "Useful visual or contextual reference, but not direct expedition evidence; "
            f"relationship is {asset.historical_relationship}."
        )
    return VerifiedAsset(
        asset=BoardMediaAsset.from_media_asset(asset),
        requirement_id=requirement.requirement_id,
        confidence=confidence,
        production_use=requirement.production_need,
        why_selected=reason,
        evidence=requirement.evidence,
        historical_relationship=asset.historical_relationship,
        visual_inspection=visual_inspection,
    )


def create_visual_inspector(*, api_key: str | None = None) -> GeminiVisualInspector:
    client = genai.Client(api_key=api_key) if api_key else genai.Client()
    return GeminiVisualInspector(
        client,
        model=os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
    )


def _vector_literal(vector: Sequence[float]) -> str:
    if not vector or any(not math.isfinite(value) for value in vector):
        raise ValueError("Embedding vectors must contain finite values")
    return "[" + ",".join(format(float(value), ".9g") for value in vector) + "]"


def _semantic_passage_query(vector: Sequence[float]) -> str:
    return f"""
SELECT passage_id, author_display_name, entry_date, passage_text
FROM sourcecut.passages FINAL
WHERE entry_date BETWEEN {BITTERROOT_START} AND {BITTERROOT_END}
  AND notEmpty(embedding)
ORDER BY cosineDistance(embedding, {_vector_literal(vector)}) ASC
LIMIT 40
""".strip()


def _semantic_media_query(vector: Sequence[float]) -> str:
    return f"""
SELECT
    asset_id, provider, provider_id, title, description, creators, asset_type,
    creation_date_text, creation_year, subjects, places, source_url, media_url,
    thumbnail_path, rights_status, rights_text, historical_relationship,
    raw_metadata, metadata_sha256
FROM sourcecut.media_assets FINAL
WHERE notEmpty(embedding)
ORDER BY cosineDistance(embedding, {_vector_literal(vector)}) ASC
LIMIT 40
""".strip()


def _match_score(asset: MediaAsset, requirement: AssetRequirement) -> int:
    haystack = " ".join(
        (
            asset.title,
            asset.description,
            *asset.subjects,
            *asset.places,
            *asset.creators,
        )
    ).casefold()
    terms = {
        token
        for term in requirement.search_terms
        for token in re.findall(r"[a-z0-9]+", term.casefold())
        if len(token) >= 3 and token not in STOP_WORDS
    }
    return sum(1 for term in terms if term in haystack)


def _warnings(
    reviewed: Sequence[VerifiedAsset],
    requirements: Sequence[AssetRequirement],
    assets: Sequence[MediaAsset],
    inspection_failures: int,
) -> tuple[str, ...]:
    warnings: list[str] = []
    unsupported = sum(item.confidence is BoardConfidence.UNSUPPORTED for item in reviewed)
    interpretive = sum(item.confidence is BoardConfidence.INTERPRETIVE for item in reviewed)
    rejected = sum(asset.rights_status not in REUSABLE_RIGHTS for asset in assets)
    if unsupported:
        warnings.append(f"{unsupported} candidate matches were unsupported and not selected.")
    if interpretive:
        warnings.append(
            f"{interpretive} reviewed candidates are interpretive references, not expedition proof."
        )
    if rejected:
        warnings.append(f"{rejected} assets were excluded by item-level rights filtering.")
    if inspection_failures:
        warnings.append(
            f"{inspection_failures} optional visual inspections failed; candidates stayed "
            "at metadata-derived confidence."
        )
    if not requirements:
        warnings.append("No validated evidence was available; no asset requirement was inferred.")
    return tuple(warnings)


def _query_rows(payload: Any) -> tuple[list[str], list[Any]]:
    if not isinstance(payload, Mapping):
        raise RuntimeError("ClickHouse MCP returned an unexpected query payload")
    columns = payload.get("columns")
    rows = payload.get("rows")
    if not isinstance(columns, list) or not isinstance(rows, list):
        raise RuntimeError("ClickHouse MCP query omitted columns or rows")
    return [str(column) for column in columns], rows


def _field(row: Any, columns: list[str], name: str) -> Any:
    if isinstance(row, Mapping):
        return row[name]
    return row[columns.index(name)]


def _string_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    if isinstance(value, tuple):
        return tuple(str(item) for item in value)
    return ()


def _media_asset(row: Any, columns: list[str]) -> MediaAsset:
    return MediaAsset(
        asset_id=str(_field(row, columns, "asset_id")),
        provider=str(_field(row, columns, "provider")),
        provider_id=str(_field(row, columns, "provider_id")),
        title=str(_field(row, columns, "title")),
        description=str(_field(row, columns, "description")),
        creators=_string_tuple(_field(row, columns, "creators")),
        asset_type=str(_field(row, columns, "asset_type")),
        creation_date_text=str(_field(row, columns, "creation_date_text")),
        creation_year=int(_field(row, columns, "creation_year")),
        subjects=_string_tuple(_field(row, columns, "subjects")),
        places=_string_tuple(_field(row, columns, "places")),
        source_url=str(_field(row, columns, "source_url")),
        media_url=str(_field(row, columns, "media_url")),
        thumbnail_path=str(_field(row, columns, "thumbnail_path")),
        rights_status=str(_field(row, columns, "rights_status")),
        rights_text=str(_field(row, columns, "rights_text")),
        historical_relationship=str(_field(row, columns, "historical_relationship")),
        raw_metadata=str(_field(row, columns, "raw_metadata")),
        metadata_sha256=_hash_text(_field(row, columns, "metadata_sha256")),
    )


def _hash_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("ascii")
    text = str(value)
    match = re.fullmatch(r"b(['\"])([0-9a-f]{64})\1", text)
    return match.group(2) if match else text


async def _build_live_board(prompt: str, *, inspect_visuals: bool) -> ResearchBoard:
    client = ClickHouseMcpClient(ClickHouseMcpSettings.from_env())
    inspector = create_visual_inspector() if inspect_visuals else None
    return await ResearchBoardService(client, visual_inspector=inspector).build_board(prompt)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the SourceCut Bitterroot research board")
    parser.add_argument("prompt")
    parser.add_argument("--skip-visual-inspection", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    board = asyncio.run(
        _build_live_board(args.prompt, inspect_visuals=not args.skip_visual_inspection)
    )
    if args.summary:
        counts = Counter(item.confidence for item in board.reviewed_assets)
        first_citation = (
            board.evidence_matrix[0].evidence[0].model_dump(mode="json")
            if board.evidence_matrix
            else None
        )
        print(
            json.dumps(
                {
                    "title": board.title,
                    "requirement_count": len(board.evidence_matrix),
                    "section_count": len(board.sections),
                    "selected_assets": sum(len(section.assets) for section in board.sections),
                    "confidence_counts": counts,
                    "visual_inspections": sum(
                        item.visual_inspection is not None for item in board.reviewed_assets
                    ),
                    "warnings": board.warnings,
                    "sources_used": board.sources_used,
                    "first_citation": first_citation,
                },
                indent=2,
            )
        )
    else:
        print(board.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
