from sourcecut_api.corpora.base import CorpusAdapter, CorpusRegistry
from sourcecut_api.corpora.odyssey import OdysseyCorpusAdapter


def create_corpus_registry() -> CorpusRegistry:
    return CorpusRegistry((OdysseyCorpusAdapter(),))


__all__ = [
    "CorpusAdapter",
    "CorpusRegistry",
    "OdysseyCorpusAdapter",
    "create_corpus_registry",
]
