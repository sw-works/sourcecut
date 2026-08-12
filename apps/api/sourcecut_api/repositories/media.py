from __future__ import annotations

import json
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from sourcecut_api.models import MediaAsset

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client

BATCH_SIZE = 10_000
ASYNC_INSERT_SETTINGS = {"async_insert": 1, "wait_for_async_insert": 1}


class MediaAssetDriftError(RuntimeError):
    pass


class ClickHouseMediaRepository:
    def __init__(self, client: Client, *, embedder: Any | None = None) -> None:
        self._client = client
        self._embedder = embedder

    def load_assets(self, assets: Sequence[MediaAsset]) -> int:
        unique: dict[str, MediaAsset] = {}
        for asset in assets:
            existing = unique.get(asset.asset_id)
            if existing is not None and existing.metadata_sha256 != asset.metadata_sha256:
                raise MediaAssetDriftError(
                    f"Input contains conflicting metadata for {asset.asset_id}"
                )
            unique[asset.asset_id] = asset

        assets_to_load = self._missing_assets(tuple(unique.values()))
        vectors = (
            self._embedder.embed_documents(
                [
                    "\n".join((asset.title, asset.description, *asset.subjects))
                    for asset in assets_to_load
                ]
            )
            if self._embedder is not None
            else (None,) * len(assets_to_load)
        )
        rows = [
            [
                asset.asset_id,
                asset.provider,
                asset.provider_id,
                asset.title,
                asset.description,
                list(asset.creators),
                asset.asset_type,
                asset.creation_date_text,
                asset.creation_year,
                list(asset.subjects),
                list(asset.places),
                asset.source_url,
                asset.media_url,
                asset.thumbnail_path,
                asset.rights_status,
                asset.rights_text,
                asset.historical_relationship,
                json.loads(asset.raw_metadata),
                asset.metadata_sha256,
                *(
                    [list(vector), self._embedder.settings.model]
                    if vector is not None
                    else []
                ),
            ]
            for asset, vector in zip(assets_to_load, vectors, strict=True)
        ]
        columns = [
            "asset_id",
            "provider",
            "provider_id",
            "title",
            "description",
            "creators",
            "asset_type",
            "creation_date_text",
            "creation_year",
            "subjects",
            "places",
            "source_url",
            "media_url",
            "thumbnail_path",
            "rights_status",
            "rights_text",
            "historical_relationship",
            "raw_metadata",
            "metadata_sha256",
            *(["embedding", "embedding_model"] if self._embedder is not None else []),
        ]
        inserted = 0
        for index in range(0, len(rows), BATCH_SIZE):
            batch = rows[index : index + BATCH_SIZE]
            self._client.insert(
                "media_assets",
                batch,
                column_names=columns,
                settings=ASYNC_INSERT_SETTINGS if len(batch) < 1_000 else None,
            )
            inserted += len(batch)
        return inserted

    def _missing_assets(self, assets: Sequence[MediaAsset]) -> tuple[MediaAsset, ...]:
        # Skip unchanged assets so a re-harvest does not write a newer
        # ReplacingMergeTree version that clobbers backfilled embeddings; fail
        # loudly when a provider changed an asset's metadata under the same id.
        if not assets:
            return ()
        result = self._client.query(
            "SELECT asset_id, metadata_sha256 FROM media_assets FINAL "
            "WHERE asset_id IN {ids:Array(String)}",
            parameters={"ids": [asset.asset_id for asset in assets]},
        )
        existing = {
            str(asset_id): _hash_text(metadata_hash)
            for asset_id, metadata_hash in result.result_rows
        }
        missing: list[MediaAsset] = []
        for asset in assets:
            stored = existing.get(asset.asset_id)
            if stored is None:
                missing.append(asset)
            elif stored != asset.metadata_sha256:
                raise MediaAssetDriftError(
                    f"{asset.asset_id} exists with different metadata; refusing to "
                    "silently replace a stored asset"
                )
        return tuple(missing)


def _hash_text(value: object) -> str:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("ascii")
    return str(value)
