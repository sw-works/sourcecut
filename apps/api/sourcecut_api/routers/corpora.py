from __future__ import annotations

from fastapi import APIRouter, HTTPException

from sourcecut_api.corpora import CorpusRegistry
from sourcecut_api.models.corpus import CorpusDetail, CorpusRecord, SourceVersionRecord


def create_corpus_router(registry: CorpusRegistry) -> APIRouter:
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
