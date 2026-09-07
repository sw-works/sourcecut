from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from sourcecut_api.agents.planner import load_scopes
from sourcecut_api.corpora import CorpusRegistry
from sourcecut_api.models.corpus import CorpusDetail, CorpusRecord, SourceVersionRecord
from sourcecut_api.models.pipeline import CorpusPipeline
from sourcecut_api.services.pipeline_state import list_pipelines


def create_corpus_router(
    registry: CorpusRegistry, mcp_client_factory: Any | None = None
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["corpora"])

    @router.get("/corpora", response_model=tuple[CorpusRecord, ...])
    async def list_corpora() -> tuple[CorpusRecord, ...]:
        return registry.list()

    @router.get("/corpora/{corpus_id}", response_model=CorpusDetail)
    async def get_corpus(corpus_id: str) -> CorpusDetail:
        detail = registry.get(corpus_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Corpus was not found")
        return detail

    @router.get("/pipelines", response_model=tuple[CorpusPipeline, ...])
    async def pipelines() -> tuple[CorpusPipeline, ...]:
        """Every corpus, and how far its ingestion has run.

        Counts are read through the same read-only role the research path uses,
        so a number on this page is a number a board could cite. A corpus whose
        counts cannot be read still lists its sources and rights.
        """
        counts: dict[str, dict[str, int]] = {}
        if mcp_client_factory is not None:
            client = mcp_client_factory()
            for record in registry.list():
                try:
                    counts[record.corpus_id] = await client.get_corpus_pipeline_counts(
                        record.corpus_id
                    )
                except Exception:
                    counts[record.corpus_id] = {}
        try:
            scopes = load_scopes()
        except Exception:
            scopes = ()
        return list_pipelines(registry, counts, scopes=scopes)

    @router.get("/works/{work_id}/versions", response_model=tuple[SourceVersionRecord, ...])
    async def list_work_versions(work_id: str) -> tuple[SourceVersionRecord, ...]:
        for corpus in registry.list():
            detail = registry.get(corpus.corpus_id)
            if detail is None:
                continue
            if any(work.work_id == work_id for work in detail.works):
                return tuple(version for version in detail.versions if version.work_id == work_id)
        raise HTTPException(status_code=404, detail="Work was not found")

    return router
