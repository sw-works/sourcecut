from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sourcecut_api.models.corpus import CorpusDetail

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client


@dataclass(frozen=True, slots=True)
class CatalogLoadResult:
    corpora_written: int
    works_written: int
    versions_written: int
    licenses_written: int


class ClickHouseCatalogRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def load_catalog(self, detail: CorpusDetail) -> CatalogLoadResult:
        updated_at = datetime.now(UTC)
        corpus = detail.corpus
        self._insert(
            "corpora",
            (
                "corpus_id",
                "title",
                "description",
                "default_work_id",
                "adapter_version",
                "display_policy",
                "status",
                "updated_at",
            ),
            [[
                corpus.corpus_id,
                corpus.title,
                corpus.description,
                corpus.default_work_id,
                corpus.adapter_version,
                corpus.display_policy.value,
                corpus.status.value,
                updated_at,
            ]],
        )
        self._insert(
            "licenses",
            (
                "license_id",
                "spdx_or_rights_code",
                "display_name",
                "canonical_url",
                "attribution_template",
                "share_alike",
                "commercial_use_allowed",
                "derivatives_allowed",
                "bulk_export_allowed",
                "notes",
                "updated_at",
            ),
            [
                [
                    item.license_id,
                    item.spdx_or_rights_code,
                    item.display_name,
                    item.canonical_url,
                    item.attribution_template,
                    item.share_alike,
                    _optional_bool(item.commercial_use_allowed),
                    _optional_bool(item.derivatives_allowed),
                    _optional_bool(item.bulk_export_allowed),
                    item.notes,
                    updated_at,
                ]
                for item in detail.licenses
            ],
        )
        self._insert(
            "works",
            (
                "work_id",
                "corpus_id",
                "cts_work_urn",
                "author_display_name",
                "title",
                "original_language",
                "book_count",
                "metadata",
                "updated_at",
            ),
            [
                [
                    item.work_id,
                    item.corpus_id,
                    item.cts_work_urn,
                    item.author_display_name,
                    item.title,
                    item.original_language,
                    item.book_count,
                    json.dumps(item.metadata, ensure_ascii=False, sort_keys=True),
                    updated_at,
                ]
                for item in detail.works
            ],
        )
        self._insert(
            "source_versions",
            (
                "version_id",
                "work_id",
                "cts_version_urn",
                "version_type",
                "language",
                "label",
                "editor_names",
                "translator_names",
                "bibliographic_description",
                "publication_year",
                "source_url",
                "upstream_revision",
                "license_id",
                "display_decision",
                "source_sha256",
                "raw_manifest",
                "updated_at",
            ),
            [
                [
                    item.version_id,
                    item.work_id,
                    item.cts_version_urn,
                    item.version_type.value,
                    item.language,
                    item.label,
                    list(item.editor_names),
                    list(item.translator_names),
                    item.bibliographic_description,
                    item.publication_year,
                    item.source_url,
                    item.upstream_revision,
                    item.license_id,
                    item.display_decision.value,
                    item.source_sha256,
                    json.dumps(item.raw_manifest, ensure_ascii=False, sort_keys=True),
                    updated_at,
                ]
                for item in detail.versions
            ],
        )
        return CatalogLoadResult(
            corpora_written=1,
            works_written=len(detail.works),
            versions_written=len(detail.versions),
            licenses_written=len(detail.licenses),
        )

    def _insert(
        self,
        table: str,
        columns: Sequence[str],
        rows: list[list[object]],
    ) -> None:
        if not rows:
            return
        self._client.insert(
            table,
            rows,
            column_names=list(columns),
            settings={"async_insert": 1, "wait_for_async_insert": 1},
        )


def _optional_bool(value: bool | None) -> int:
    if value is None:
        return -1
    return int(value)
