from sourcecut_api.corpora.base import CorpusAdapter, CorpusRegistry
from sourcecut_api.corpora.lewis_and_clark import LewisAndClarkCorpusAdapter
from sourcecut_api.corpora.odyssey import OdysseyCorpusAdapter


def create_corpus_registry() -> CorpusRegistry:
    return CorpusRegistry((LewisAndClarkCorpusAdapter(), OdysseyCorpusAdapter()))


__all__ = [
    "CorpusAdapter",
    "LewisAndClarkCorpusAdapter",
    "CorpusRegistry",
    "OdysseyCorpusAdapter",
    "create_corpus_registry",
]
