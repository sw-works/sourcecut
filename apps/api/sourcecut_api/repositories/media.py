from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from sourcecut_api.models import MediaAsset

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client

BATCH_SIZE = 10_000
ASYNC_INSERT_SETTINGS = {"async_insert": 1, "wait_for_async_insert": 1}


class MediaAssetDriftError(RuntimeError):
    pass


class ClickHouseMediaRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def load_assets(self, assets: Sequence[MediaAsset]) -> int:
        unique: dict[str, MediaAsset] = {}
        for asset in assets:
            existing = unique.get(asset.asset_id)
            if existing is not None and existing.metadata_sha256 != asset.metadata_sha256:
                raise MediaAssetDriftError(
                    f"Input contains conflicting metadata for {asset.asset_id}"
                )
            unique[asset.asset_id] = asset

        missing = self._missing_assets(tuple(unique.values()))
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
                asset.raw_metadata,
                asset.metadata_sha256,
            ]
            for asset in missing
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
        existing: dict[str, set[str]] = {}
        for index in range(0, len(assets), BATCH_SIZE):
            batch = assets[index : index + BATCH_SIZE]
            rows = self._client.query(
                "SELECT asset_id, metadata_sha256 FROM media_assets "
                "WHERE asset_id IN {ids:Array(String)}",
                parameters={"ids": [asset.asset_id for asset in batch]},
            ).result_rows
            for asset_id, metadata_hash in rows:
                value = metadata_hash.decode("ascii") if isinstance(metadata_hash, bytes) else str(
                    metadata_hash
                )
                existing.setdefault(str(asset_id), set()).add(value)

        missing: list[MediaAsset] = []
        for asset in assets:
            hashes = existing.get(asset.asset_id)
            if hashes is None:
                missing.append(asset)
            elif hashes != {asset.metadata_sha256}:
                raise MediaAssetDriftError(
                    f"media_assets.{asset.asset_id} exists with different metadata"
                )
        return tuple(missing)
