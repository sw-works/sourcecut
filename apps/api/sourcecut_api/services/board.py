from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import mimetypes
import os
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

from google import genai
from google.genai import types

from sourcecut_api.integrations.clickhouse_mcp import ClickHouseMcpClient, ClickHouseMcpSettings
from sourcecut_api.models import (
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
FROM sourcecut.media_assets
ORDER BY provider, rights_status, asset_type, creation_year, asset_id
LIMIT 200
""".strip()

PASSAGE_EVIDENCE_QUERY = f"""
SELECT passage_id, author_display_name, entry_date, passage_text
FROM sourcecut.passages
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

CATEGORY_TERMS = {
    "weather": ("snow", "rain", "cold", "frost", "wet"),
    "terrain": ("mountain", "steep", "rock", "trail", "timber", "creek"),
    "transportation": ("horse", "horses", "road", "trail", "travel"),
    "food": ("food", "hunger", "hungry", "meat", "provisions", "eat"),
    "shelter": ("camp", "shelter", "tent"),
    "equipment": ("blanket", "clothing", "moccasin", "gun", "baggage", "equipment"),
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
    ) -> None:
        self._mcp = mcp_client
        self._visual_inspector = visual_inspector
        self._visual_inspection_limit = visual_inspection_limit

    async def build_board(self, prompt: str) -> ResearchBoard:
        evidence = await self._load_evidence()
        requirements = build_asset_requirements(evidence)
        assets = await self._load_media_assets()
        reviewed: list[VerifiedAsset] = []
        sections: list[BoardSection] = []
        inspected = 0
        inspection_failures = 0

        for requirement in requirements:
            ranked = sorted(
                assets,
                key=lambda asset: (_match_score(asset, requirement), asset.asset_id),
                reverse=True,
            )
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

    async def _load_evidence(self) -> tuple[EvidenceCitation, ...]:
        payload = await self._mcp.call_tool("run_query", {"query": EVIDENCE_QUERY})
        columns, rows = _query_rows(payload)
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
        if observations:
            return observations
        passage_payload = await self._mcp.call_tool(
            "run_query", {"query": PASSAGE_EVIDENCE_QUERY}
        )
        passage_columns, passage_rows = _query_rows(passage_payload)
        return _derive_passage_evidence(passage_rows, passage_columns)

    async def _load_media_assets(self) -> tuple[MediaAsset, ...]:
        payload = await self._mcp.call_tool("run_query", {"query": MEDIA_QUERY})
        columns, rows = _query_rows(payload)
        return tuple(_media_asset(row, columns) for row in rows)


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


def _derive_passage_evidence(
    rows: Sequence[Any], columns: list[str]
) -> tuple[EvidenceCitation, ...]:
    citations: list[EvidenceCitation] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        passage_id = str(_field(row, columns, "passage_id"))
        passage_text = str(_field(row, columns, "passage_text"))
        lowered = passage_text.casefold()
        for category, terms in CATEGORY_TERMS.items():
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
