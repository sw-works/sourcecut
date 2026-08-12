from __future__ import annotations

import argparse
import hashlib
import json
import os
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
    mappings,
    replace_asset_thumbnail,
    texts,
    year_of,
)
from sourcecut_api.db.client import get_clickhouse_client
from sourcecut_api.db.migrations import bootstrap_database
from sourcecut_api.models import HistoricalRelationship, MediaAsset, RightsStatus
from sourcecut_api.repositories import ClickHouseMediaRepository

DEFAULT_CACHE_DIR = Path("data/archive-cache/smithsonian")
DEFAULT_QUERIES_FILE = Path("data/curation/smithsonian-media-queries.json")
ALLOWED_MEDIA_HOSTS = {"ids.si.edu"}


@dataclass(frozen=True, slots=True)
class SmithsonianHarvestResult:
    assets: tuple[MediaAsset, ...]
    rejected_rights: int
    raw_records_cached: int
    thumbnails_cached: int


def normalize_smithsonian(record: Mapping[str, Any]) -> MediaAsset | None:
    content = _mapping(record.get("content"))
    descriptive = _mapping(content.get("descriptiveNonRepeating"))
    media = mappings(_mapping(descriptive.get("online_media")).get("media"))
    candidate = next(
        (
            item
            for item in media
            if "CC0" in str(item.get("usage", "")).upper()
            and _approved_media_url(item)
        ),
        None,
    )
    if candidate is None:
        return None

    identifier = str(record.get("id", "")).strip()
    if not identifier:
        raise ValueError("Smithsonian record has no id")
    raw = canonical_json(record)
    title = _nested_text(descriptive, "title", "content") or str(record.get("title", ""))
    indexed = _mapping(content.get("indexedStructured"))
    freetext = _mapping(content.get("freetext"))
    date_text = _first_content(freetext.get("date"))
    year = year_of(date_text)
    source_url = (
        _nested_text(descriptive, "record_link")
        or _nested_text(descriptive, "url")
        or str(record.get("url", ""))
    )
    subjects = _texts(indexed.get("topic")) + _texts(indexed.get("object_type"))
    return MediaAsset(
        asset_id=f"si:{identifier}",
        provider="Smithsonian Open Access",
        provider_id=identifier,
        title=title or "Untitled Smithsonian object",
        description=_first_content(freetext.get("notes")),
        creators=_texts(indexed.get("name")),
        asset_type=_first_content(freetext.get("physicalDescription")) or "collection object",
        creation_date_text=date_text,
        creation_year=year,
        subjects=subjects,
        places=_texts(indexed.get("place")),
        source_url=source_url,
        media_url=_approved_media_url(candidate),
        rights_status=RightsStatus.PUBLIC_DOMAIN,
        rights_text="CC0",
        historical_relationship=_relationship(year),
        raw_metadata=raw,
        metadata_sha256=hashlib.sha256(raw.encode()).hexdigest(),
    )


def harvest_smithsonian(
    client: ArchiveApiClient,
    cache_dir: Path,
    api_key: str,
    queries: Sequence[str],
    *,
    max_items: int,
    cache_thumbnails: bool = True,
) -> SmithsonianHarvestResult:
    assets: dict[str, MediaAsset] = {}
    rejected_rights = 0
    raw_records_cached = 0
    thumbnails_cached = 0
    for query in queries:
        if len(assets) >= max_items:
            break
        rows = min(1000, max_items - len(assets))
        params = urlencode({"q": query, "rows": rows, "api_key": api_key})
        url = f"https://api.si.edu/openaccess/api/v1.0/search?{params}"
        cache_name = hashlib.sha256(url.encode()).hexdigest()[:20]
        payload, created = cached_json(
            client,
            url,
            cache_dir / "search" / f"{cache_name}.json",
        )
        raw_records_cached += int(created)
        for record in mappings(_mapping(payload.get("response")).get("rows")):
            asset = normalize_smithsonian(record)
            if asset is None:
                rejected_rights += 1
                continue
            if asset.asset_id in assets:
                continue
            if cache_thumbnails and asset.thumbnail_approved:
                path, thumbnail_created = cache_thumbnail(client, asset, cache_dir)
                asset = replace_asset_thumbnail(asset, path)
                thumbnails_cached += int(thumbnail_created)
            assets[asset.asset_id] = asset
            if len(assets) >= max_items:
                break
    return SmithsonianHarvestResult(
        assets=tuple(assets.values()),
        rejected_rights=rejected_rights,
        raw_records_cached=raw_records_cached,
        thumbnails_cached=thumbnails_cached,
    )


def _load_queries(path: Path) -> tuple[str, ...]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"Expected a non-empty string list in {path}")
    return tuple(value)


def _approved_media_url(item: Mapping[str, Any]) -> str:
    for field in ("content", "thumbnail"):
        value = str(item.get(field, ""))
        parsed = urlparse(value)
        if parsed.scheme == "https" and parsed.hostname in ALLOWED_MEDIA_HOSTS:
            return value
    return ""


def _relationship(year: int) -> HistoricalRelationship:
    if 1803 <= year <= 1815:
        return HistoricalRelationship.NEAR_CONTEMPORARY
    if year and year <= 1900:
        return HistoricalRelationship.PERIOD_COMPARATIVE
    return HistoricalRelationship.PERIOD_COMPARATIVE


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _texts(value: Any) -> tuple[str, ...]:
    return texts(value)


def _nested_text(value: Mapping[str, Any], *path: str) -> str:
    current: Any = value
    for part in path:
        current = _mapping(current).get(part)
    return str(current).strip() if current is not None else ""


def _first_content(value: Any) -> str:
    first = next(iter(mappings(value)), {})
    return str(first.get("content", "")).strip()


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Harvest Smithsonian CC0 media")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES_FILE)
    parser.add_argument("--max-items", type=int, default=2000)
    parser.add_argument("--no-thumbnails", action="store_true")
    args = parser.parse_args(argv)
    if args.max_items < 1:
        parser.error("--max-items must be at least 1")
    key = os.getenv("SMITHSONIAN_API_KEY")
    if not key:
        raise SystemExit("SMITHSONIAN_API_KEY is required")

    result = harvest_smithsonian(
        ArchiveApiClient("Smithsonian", ALLOWED_MEDIA_HOSTS),
        args.cache_dir,
        key,
        _load_queries(args.queries),
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
        f"Accepted {len(result.assets)} CC0 item(s); "
        f"rights-rejected {result.rejected_rights}; inserted {inserted}; "
        f"cached {result.raw_records_cached} response(s) and "
        f"{result.thumbnails_cached} thumbnail(s)."
    )


if __name__ == "__main__":
    main()
