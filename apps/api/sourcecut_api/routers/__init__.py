from sourcecut_api.routers.boards import create_board_router
from sourcecut_api.routers.claims import create_claim_router
from sourcecut_api.routers.classical_text import create_classical_text_router
from sourcecut_api.routers.corpora import create_corpus_router
from sourcecut_api.routers.entities import create_entity_router
from sourcecut_api.routers.exports import create_export_router
from sourcecut_api.routers.geography import create_geography_router
from sourcecut_api.routers.linguistic import create_linguistic_router
from sourcecut_api.routers.narrative import create_narrative_router
from sourcecut_api.routers.visual_culture import create_visual_culture_router

__all__ = [
    "create_board_router",
    "create_visual_culture_router",
    "create_entity_router",
    "create_export_router",
    "create_geography_router",
    "create_claim_router",
    "create_classical_text_router",
    "create_corpus_router",
    "create_linguistic_router",
    "create_narrative_router",
]
