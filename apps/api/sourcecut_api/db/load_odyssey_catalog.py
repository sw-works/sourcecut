from __future__ import annotations

from sourcecut_api.corpora.odyssey import OdysseyCorpusAdapter
from sourcecut_api.db.client import get_clickhouse_client
from sourcecut_api.db.migrations import bootstrap_database
from sourcecut_api.repositories import ClickHouseCatalogRepository


def main() -> None:
    client = get_clickhouse_client()
    bootstrap_database(client)
    result = ClickHouseCatalogRepository(client).load_catalog(OdysseyCorpusAdapter().detail())
    print(
        "Loaded Odyssey catalog: "
        f"{result.corpora_written} corpus, {result.works_written} work, "
        f"{result.versions_written} versions, {result.licenses_written} license"
    )


if __name__ == "__main__":
    main()
