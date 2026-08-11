from __future__ import annotations

import argparse
import hashlib
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

from pipelines.media.core import (
    ArchiveApiClient,
    cache_thumbnail,
    cached_json,
    canonical_json,
    replace_asset_thumbnail,
)
from sourcecut_api.db.client import get_clickhouse_client
from sourcecut_api.db.migrations import bootstrap_database
from sourcecut_api.models import HistoricalRelationship, MediaAsset, RightsStatus
from sourcecut_api.repositories import ClickHouseMediaRepository

DEFAULT_CACHE_DIR = Path("data/archive-cache/nps")
ALLOWED_MEDIA_HOSTS = {"www.nps.gov", "home.nps.gov"}
DEFAULT_PARKS = "lecl,nepe,biho"


@dataclass(frozen=True, slots=True)
class NpsHarvestResult:
    assets: tuple[MediaAsset, ...]
    rejected_rights: int
    raw_records_cached: int
    thumbnails_cached: int


def normalize_nps(record: Mapping[str, Any]) -> MediaAsset | None:
    rights = " ".join(
        str(record.get(key, "")) for key in ("copyright", "credit", "rights")
    ).strip()
    normalized_rights = rights.casefold()
    if not any(
        marker in normalized_rights
        for marker in ("public domain", "national park service", "u.s. government")
    ):
        return None
    identifier = str(record.get("id", "")).strip()
    if not identifier:
        raise ValueError("NPS record has no id")
    raw = canonical_json(record)
    media_url = _media_url(record)
    date_text = str(record.get("createDate", "") or record.get("date", ""))
    year = _year(date_text)
    asset_type = str(record.get("assetType", "photograph"))
    return MediaAsset(
        asset_id=f"nps:{identifier}",
        provider="National Park Service",
        provider_id=identifier,
        title=str(record.get("title", "Untitled NPS asset")),
        description=str(record.get("description", "")),
        creators=(str(record.get("credit")),) if record.get("credit") else (),
        asset_type=asset_type,
        creation_date_text=date_text,
        creation_year=year,
        subjects=_texts(record.get("tags")),
        places=_texts(record.get("parkCode")),
        source_url=str(record.get("permalink", media_url)),
        media_url=media_url,
        rights_status=RightsStatus.PUBLIC_DOMAIN,
        rights_text=rights,
        historical_relationship=_relationship(asset_type, str(record.get("description", ""))),
        raw_metadata=raw,
        metadata_sha256=hashlib.sha256(raw.encode()).hexdigest(),
    )


def harvest_nps(
    client: ArchiveApiClient,
    cache_dir: Path,
    api_key: str,
    *,
    parks: str = DEFAULT_PARKS,
    max_items: int,
    cache_thumbnails: bool = True,
) -> NpsHarvestResult:
    params = urlencode({"parkCode": parks, "limit": max_items, "api_key": api_key})
    url = f"https://developer.nps.gov/api/v1/multimedia/galleries/assets?{params}"
    cache_name = hashlib.sha256(url.encode()).hexdigest()[:20]
    payload, created = cached_json(
        client,
        url,
        cache_dir / "search" / f"{cache_name}.json",
    )
    assets: dict[str, MediaAsset] = {}
    rejected_rights = 0
    thumbnails_cached = 0
    for record in _mappings(payload.get("data")):
        asset = normalize_nps(record)
        if asset is None:
            rejected_rights += 1
            continue
        if asset.asset_id in assets:
            continue
        if cache_thumbnails and asset.thumbnail_approved and asset.media_url:
            path, thumbnail_created = cache_thumbnail(client, asset, cache_dir)
            asset = replace_asset_thumbnail(asset, path)
            thumbnails_cached += int(thumbnail_created)
        assets[asset.asset_id] = asset
        if len(assets) >= max_items:
            break
    return NpsHarvestResult(
        assets=tuple(assets.values()),
        rejected_rights=rejected_rights,
        raw_records_cached=int(created),
        thumbnails_cached=thumbnails_cached,
    )


def _media_url(record: Mapping[str, Any]) -> str:
    file_info = record.get("fileInfo")
    candidates: list[str] = []
    if isinstance(file_info, Mapping):
        candidates.append(str(file_info.get("url", "")))
    elif isinstance(file_info, list):
        candidates.extend(str(item.get("url", "")) for item in _mappings(file_info))
    candidates.append(str(record.get("url", "")))
    for candidate in candidates:
        parsed = urlparse(candidate)
        if parsed.scheme == "https" and parsed.hostname in ALLOWED_MEDIA_HOSTS:
            return candidate
    return ""


def _relationship(asset_type: str, description: str) -> HistoricalRelationship:
    searchable = f"{asset_type} {description}".casefold()
    if any(marker in searchable for marker in ("replica", "reconstruction", "reenact")):
        return HistoricalRelationship.REPLICA
    if any(marker in searchable for marker in ("landscape", "environment", "habitat")):
        return HistoricalRelationship.PERIOD_COMPARATIVE
    return HistoricalRelationship.LATER_REPRESENTATION


def _mappings(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _texts(value: Any) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(",") if part.strip())
    return ()


def _year(value: str) -> int:
    match = re.search(r"(?<!\d)(\d{4})(?!\d)", value)
    return int(match.group(1)) if match else 0


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Harvest rights-approved NPS media")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--parks", default=DEFAULT_PARKS)
    parser.add_argument("--max-items", type=int, default=500)
    parser.add_argument("--no-thumbnails", action="store_true")
    args = parser.parse_args(argv)
    if args.max_items < 1:
        parser.error("--max-items must be at least 1")
    key = os.getenv("NPS_API_KEY")
    if not key:
        raise SystemExit("NPS_API_KEY is required")

    result = harvest_nps(
        ArchiveApiClient("NPS", ALLOWED_MEDIA_HOSTS),
        args.cache_dir,
        key,
        parks=args.parks,
        max_items=args.max_items,
        cache_thumbnails=not args.no_thumbnails,
    )
    client = get_clickhouse_client()
    try:
        bootstrap_database(client)
        inserted = ClickHouseMediaRepository(client).load_assets(result.assets)
    finally:
        client.close()
    print(
        f"Accepted {len(result.assets)} public-domain item(s); "
        f"rights-rejected {result.rejected_rights}; inserted {inserted}; "
        f"cached {result.raw_records_cached} response(s) and "
        f"{result.thumbnails_cached} thumbnail(s)."
    )


if __name__ == "__main__":
    main()
