from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Response

from sourcecut_api.models.linguistic import (
    CooccurrenceRequest,
    FormulaResult,
    FormulaSearchRequest,
    FrequencyBucket,
    FrequencyRequest,
    FrequencyResponse,
    SavedSearch,
    SavedSearchCreate,
    TextSearchRequest,
    TextSearchResponse,
    TokenAnalysis,
)
from sourcecut_api.services.linguistic import (
    MemorySavedSearchStore,
    SearchCursorError,
    build_formula_results,
    build_search_response,
    decode_cursor,
)


def create_linguistic_router(
    mcp_client_factory: Any,
    saved_search_store: MemorySavedSearchStore,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["linguistic-search"])

    @router.post("/search/text", response_model=TextSearchResponse)
    async def search_text(request: TextSearchRequest) -> TextSearchResponse:
        try:
            offset = decode_cursor(request.cursor)
            payload = await mcp_client_factory().search_odyssey_text(request, offset)
            return build_search_response(request, payload["rows"], offset)
        except (SearchCursorError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.get("/tokens/{token_id}", response_model=TokenAnalysis)
    async def token_analysis(token_id: str) -> TokenAnalysis:
        try:
            rows = (await mcp_client_factory().get_odyssey_token(token_id))["rows"]
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if not rows:
            raise HTTPException(status_code=404, detail="Token was not found")
        if len(rows) > 1:
            raise HTTPException(status_code=409, detail="Token identity is not unique")
        row = rows[0]
        morphology = row.get("morphology", {})
        if isinstance(morphology, str):
            morphology = json.loads(morphology)
        return TokenAnalysis(
            token_id=str(row["token_id"]),
            surface=str(row["surface"]),
            lemma=str(row["lemma"]),
            part_of_speech=str(row["part_of_speech"]),
            morphology=morphology,
            annotation_source=str(row["annotation_source"]),
            annotation_version=str(row["annotation_version"]),
            annotation_confidence=float(row["annotation_confidence"]),
            review_status=str(row["review_status"]),
            occurrence_count=int(row["occurrence_count"]),
        )

    @router.post("/search/frequency", response_model=FrequencyResponse)
    async def frequency(request: FrequencyRequest) -> FrequencyResponse:
        try:
            rows = await mcp_client_factory().get_odyssey_frequency(request)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return FrequencyResponse(
            query=request.query,
            mode=request.mode,
            group_by=request.group_by,
            buckets=tuple(
                FrequencyBucket(key=str(row["key"]), count=int(row["count"]))
                for row in rows
            ),
            annotation_notice=(
                "Counts use exact imported lemma/form annotations; ambiguity is not collapsed."
            ),
        )

    @router.post("/search/formulae", response_model=tuple[FormulaResult, ...])
    async def formulae(request: FormulaSearchRequest) -> tuple[FormulaResult, ...]:
        return build_formula_results(await mcp_client_factory().get_odyssey_formulae(request))

    @router.post("/search/cooccurrences", response_model=tuple[dict[str, object], ...])
    async def cooccurrences(request: CooccurrenceRequest) -> tuple[dict[str, object], ...]:
        rows = await mcp_client_factory().get_odyssey_cooccurrences(request)
        return tuple(rows)

    @router.post("/saved-searches", response_model=SavedSearch, status_code=201)
    async def save_search(request: SavedSearchCreate) -> SavedSearch:
        return saved_search_store.create(request)

    @router.get("/saved-searches", response_model=tuple[SavedSearch, ...])
    async def list_saved_searches() -> tuple[SavedSearch, ...]:
        return saved_search_store.list()

    @router.delete("/saved-searches/{saved_search_id}", status_code=204)
    async def delete_saved_search(saved_search_id: str) -> Response:
        if not saved_search_store.delete(saved_search_id):
            raise HTTPException(status_code=404, detail="Saved search was not found")
        return Response(status_code=204)

    return router
