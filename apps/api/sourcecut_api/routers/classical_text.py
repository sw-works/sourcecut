from __future__ import annotations

from collections import OrderedDict
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response

from sourcecut_api.corpora import CorpusRegistry
from sourcecut_api.models.classical_text import (
    ParallelPassage,
    ResolvedCitation,
    TextRangeResponse,
    TextUnitView,
)
from sourcecut_api.models.corpus import LicenseRecord, SourceVersionRecord
from sourcecut_api.services.citations import CitationResolutionError, CitationResolver


def create_classical_text_router(registry: CorpusRegistry, mcp_client_factory: Any) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["classical-text"])
    detail = registry.get("odyssey")
    versions = {item.version_id: item for item in detail.versions} if detail else {}
    licenses = {item.license_id: item for item in detail.licenses} if detail else {}
    resolver = CitationResolver(
        {item.version_id: item.cts_version_urn for item in versions.values()}
    )
    parallel_cache: OrderedDict[tuple[object, ...], ParallelPassage] = OrderedDict()

    @router.get("/text/resolve", response_model=ResolvedCitation)
    async def resolve_citation(reference: str, version_id: str) -> ResolvedCitation:
        try:
            return resolver.resolve(reference, version_id)
        except CitationResolutionError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.get("/text/{version_id}/{book}", response_model=TextRangeResponse)
    async def get_text(
        version_id: str,
        book: int,
        response: Response,
        from_line: int = Query(1, ge=1),
        to_line: int = Query(80, ge=1),
    ) -> TextRangeResponse:
        _cache_immutable_text(response)
        version = _version(versions, version_id)
        _validate_range(book, from_line, to_line)
        payload = await mcp_client_factory().get_classical_text(
            version_id, book, from_line, to_line
        )
        rows = payload.get("units", [])
        if not rows:
            raise HTTPException(status_code=404, detail="Text range was not found")
        return _text_response(
            version, licenses[version.license_id], book, from_line, to_line, rows
        )

    @router.get("/text/{version_id}/{book}/parallel", response_model=ParallelPassage)
    async def get_parallel_text(
        version_id: str,
        book: int,
        response: Response,
        from_line: int = Query(1, ge=1),
        to_line: int = Query(80, ge=1),
        targets: list[str] = Query(default=[]),
    ) -> ParallelPassage:
        _cache_immutable_text(response)
        _validate_range(book, from_line, to_line)
        source_version = _version(versions, version_id)
        target_versions = [_version(versions, target) for target in targets]
        cache_key = (version_id, tuple(targets), book, from_line, to_line)
        cached = parallel_cache.get(cache_key)
        if cached is not None:
            parallel_cache.move_to_end(cache_key)
            return cached
        requested = [version_id, *targets]
        payloads = await mcp_client_factory().get_parallel_classical_text(
            requested, book, from_line, to_line
        )
        by_version = {str(item["version_id"]): item.get("units", []) for item in payloads}
        source = _text_response(
            source_version,
            licenses[source_version.license_id],
            book,
            from_line,
            to_line,
            by_version.get(version_id, []),
        )
        result = ParallelPassage(
            source=source,
            targets=tuple(
                _text_response(
                    version,
                    licenses[version.license_id],
                    book,
                    from_line,
                    to_line,
                    by_version.get(version.version_id, []),
                )
                for version in target_versions
            ),
        )
        parallel_cache[cache_key] = result
        parallel_cache.move_to_end(cache_key)
        if len(parallel_cache) > 256:
            parallel_cache.popitem(last=False)
        return result

    return router


def _cache_immutable_text(response: Response) -> None:
    response.headers["Cache-Control"] = "public, max-age=3600, stale-while-revalidate=86400"


def _version(
    versions: dict[str, SourceVersionRecord], version_id: str
) -> SourceVersionRecord:
    version = versions.get(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Odyssey version was not found")
    return version


def _validate_range(book: int, from_line: int, to_line: int) -> None:
    if not 1 <= book <= 24:
        raise HTTPException(status_code=422, detail="Book must be between 1 and 24")
    if to_line < from_line:
        raise HTTPException(status_code=422, detail="Line range is reversed")
    if to_line - from_line > 199:
        raise HTTPException(status_code=422, detail="Text requests are limited to 200 lines")


def _text_response(
    version: SourceVersionRecord,
    license_record: LicenseRecord,
    book: int,
    from_line: int,
    to_line: int,
    rows: list[dict[str, object]],
) -> TextRangeResponse:
    units = tuple(
        TextUnitView(
            text_unit_id=str(row["text_unit_id"]),
            citation=str(row["citation"]),
            cts_urn=str(row["cts_urn"]),
            book=int(row["book"]),
            line_start=int(row["line_start"]),
            line_end=int(row["line_end"]),
            text=str(row["original_text"]),
        )
        for row in rows
    )
    actual_start = min((unit.line_start for unit in units), default=from_line)
    actual_end = max((unit.line_end for unit in units), default=to_line)
    return TextRangeResponse(
        version_id=version.version_id,
        version_label=version.label,
        language=version.language,
        book=book,
        line_start=actual_start,
        line_end=actual_end,
        cts_urn=f"{version.cts_version_urn}:{book}.{actual_start}-{book}.{actual_end}",
        display_decision=version.display_decision,
        bibliographic_description=version.bibliographic_description,
        attribution=license_record.attribution_template,
        source_url=version.source_url,
        license_name=license_record.display_name,
        license_url=license_record.canonical_url,
        units=units,
        previous_line=max(1, actual_start - 80) if actual_start > 1 else None,
        next_line=actual_end + 1,
    )
