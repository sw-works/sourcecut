from sourcecut_api.routers.claims import create_claim_router
from sourcecut_api.routers.classical_text import create_classical_text_router
from sourcecut_api.routers.corpora import create_corpus_router
from sourcecut_api.routers.entities import create_entity_router
from sourcecut_api.routers.geography import create_geography_router
from sourcecut_api.routers.linguistic import create_linguistic_router
from sourcecut_api.routers.narrative import create_narrative_router

__all__ = [
    "create_entity_router",
    "create_geography_router",
    "create_claim_router",
    "create_classical_text_router",
    "create_corpus_router",
    "create_linguistic_router",
    "create_narrative_router",
]
