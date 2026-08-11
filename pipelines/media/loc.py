from __future__ import annotations

import argparse
import hashlib
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

from pipelines.embeddings import EmbeddingSettings, create_embedder
from pipelines.media.core import (
    ArchiveApiClient,
    CacheConflictError,
    HttpPayload,
    Transport,
    cache_thumbnail,
    cached_json,
    canonical_json,
    replace_asset_thumbnail,
    safe_filename,
)
from sourcecut_api.db.client import get_clickhouse_client
from sourcecut_api.db.migrations import bootstrap_database
from sourcecut_api.models import HistoricalRelationship, MediaAsset, RightsStatus
from sourcecut_api.repositories import ClickHouseMediaRepository

__all__ = ["CacheConflictError", "HttpPayload", "LocApiClient"]

LOC_BASE_URL = "https://www.loc.gov"
LOC_ITEM_URL = f"{LOC_BASE_URL}/item"
DEFAULT_CACHE_DIR = Path("data/archive-cache/loc")
ALLOWED_MEDIA_HOSTS = {"cdn.loc.gov", "tile.loc.gov"}
DEFAULT_ITEM_IDS = (
    "mtjbib012807",
    "mtjbib014558",
    "mtjbib016499",
    "2017814842",
    "90715923",
    "mt0144",
)


@dataclass(frozen=True, slots=True)
class LocQuery:
    endpoint: str
    query: str = ""
    facets: tuple[str, ...] = ()
    page_size: int = 100

    def url(self) -> str:
        params: list[tuple[str, str | int]] = [
            ("fo", "json"),
            ("at", "results,pagination"),
            ("c", self.page_size),
        ]
        if self.query:
            params.append(("q", self.query))
        if self.facets:
            params.append(("fa", "|".join(self.facets)))
        return f"{LOC_BASE_URL}/{self.endpoint.strip('/')}/?{urlencode(params)}"


DEFAULT_MAP_QUERY = LocQuery(
    endpoint="maps",
    facets=("subject:lewis and clark expedition", "digitized:true"),
)


@dataclass(frozen=True, slots=True)
class LocHarvestResult:
    assets: tuple[MediaAsset, ...]
    raw_records_cached: int
    thumbnails_cached: int


class LocApiClient(ArchiveApiClient):
    def __init__(
        self,
        *,
        transport: Transport | None = None,
        timeout_seconds: float = 30,
        attempts: int = 3,
    ) -> None:
        super().__init__(
            "LOC",
            ALLOWED_MEDIA_HOSTS,
            transport=transport,
            timeout_seconds=timeout_seconds,
            attempts=attempts,
        )


def harvest_loc(
    client: LocApiClient,
    cache_dir: Path,
    *,
    queries: Sequence[LocQuery] = (DEFAULT_MAP_QUERY,),
    item_ids: Sequence[str] = DEFAULT_ITEM_IDS,
    max_items: int | None = None,
    cache_thumbnails: bool = True,
) -> LocHarvestResult:
    cache_dir.mkdir(parents=True, exist_ok=True)
    provider_ids: list[str] = list(item_ids)
    search_cache_count = 0
    for query in queries:
        url = query.url()
        cache_name = hashlib.sha256(url.encode()).hexdigest()[:16]
        payload, created = cached_json(
            client,
            url,
            cache_dir / "search" / f"{cache_name}.json",
        )
        search_cache_count += int(created)
        for result in _objects(payload.get("results")):
            provider_id = _provider_id(result)
            if provider_id:
                provider_ids.append(provider_id)

    assets: list[MediaAsset] = []
    raw_records_cached = search_cache_count
    thumbnails_cached = 0
    seen: set[str] = set()
    for provider_id in provider_ids:
        if provider_id in seen:
            continue
        seen.add(provider_id)
        if max_items is not None and len(assets) >= max_items:
            break
        item_params = urlencode({"fo": "json", "at": "item,resources"})
        item_url = f"{LOC_ITEM_URL}/{provider_id}/?{item_params}"
        payload, created = cached_json(
            client,
            item_url,
            cache_dir / "items" / f"{safe_filename(provider_id)}.json",
        )
        raw_records_cached += int(created)
        asset = normalize_loc_item(payload, provider_id=provider_id)
        if cache_thumbnails and asset.thumbnail_approved and asset.media_url:
            thumbnail_path, thumbnail_created = cache_thumbnail(client, asset, cache_dir)
            asset = replace_asset_thumbnail(asset, thumbnail_path)
            thumbnails_cached += int(thumbnail_created)
        assets.append(asset)

    return LocHarvestResult(
        assets=tuple(assets),
        raw_records_cached=raw_records_cached,
        thumbnails_cached=thumbnails_cached,
    )


def normalize_loc_item(payload: Mapping[str, Any], *, provider_id: str) -> MediaAsset:
    item = payload.get("item")
    if not isinstance(item, Mapping):
        raise ValueError(f"LOC item response {provider_id} has no item object")
    raw_metadata = canonical_json(payload)
    rights_text = _rights_text(item)
    rights_status = classify_loc_rights(item, rights_text)
    creation_date = _first_text(item.get("date")) or _first_text(item.get("dates"))
    creation_year = _year(creation_date)
    title = _first_text(item.get("title"))
    if not title:
        raise ValueError(f"LOC item {provider_id} has no title")
    source_url = _https_url(_first_text(item.get("url"))) or f"{LOC_ITEM_URL}/{provider_id}/"
    media_url = _thumbnail_url(payload)
    return MediaAsset(
        asset_id=f"loc:{provider_id}",
        provider="Library of Congress",
        provider_id=provider_id,
        title=title,
        description=_joined_text(item.get("description")),
        creators=_text_tuple(item.get("contributor") or item.get("contributors")),
        asset_type=_first_text(item.get("original_format")) or "unknown",
        creation_date_text=creation_date,
        creation_year=creation_year,
        subjects=_text_tuple(item.get("subject") or item.get("subjects")),
        places=_text_tuple(item.get("location") or item.get("locations")),
        source_url=source_url,
        media_url=media_url,
        rights_status=rights_status,
        rights_text=rights_text,
        historical_relationship=_historical_relationship(item, creation_year),
        raw_metadata=raw_metadata,
        metadata_sha256=hashlib.sha256(raw_metadata.encode()).hexdigest(),
    )


def classify_loc_rights(item: Mapping[str, Any], rights_text: str) -> RightsStatus:
    if bool(item.get("access_restricted")):
        return RightsStatus.RESTRICTED
    normalized = re.sub(r"<[^>]+>", " ", rights_text).casefold()
    if any(
        marker in normalized
        for marker in (
            "public domain",
            "no known restrictions",
            "free to use and reuse",
            "unaware of any copyright or other restrictions",
        )
    ):
        return RightsStatus.PUBLIC_DOMAIN
    if "creative commons zero" in normalized or "cc0" in normalized:
        return RightsStatus.CC0
    if any(marker in normalized for marker in ("permission required", "restricted", "copyrighted")):
        return RightsStatus.RESTRICTED
    if rights_text and any(
        marker in normalized for marker in ("may be used", "may be reproduced", "credit line")
    ):
        return RightsStatus.REUSABLE_WITH_CONDITIONS
    return RightsStatus.RIGHTS_UNCLEAR


def _provider_id(item: Mapping[str, Any]) -> str:
    value = _first_text(item.get("id"))
    match = re.search(r"(?:www\.)?loc\.gov/item/([^/]+)", value)
    return match.group(1) if match else ""


def _thumbnail_url(payload: Mapping[str, Any]) -> str:
    resources = payload.get("resources")
    for resource in _objects(resources):
        candidate = _https_url(_first_text(resource.get("image")))
        parsed = urlparse(candidate)
        if candidate and parsed.hostname in ALLOWED_MEDIA_HOSTS:
            return candidate
    return ""


def _rights_text(item: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for field in ("rights_information", "rights_advisory", "rights", "restriction"):
        text = _joined_text(item.get(field))
        if text and text not in parts:
            parts.append(text)
    return "\n\n".join(parts)


def _historical_relationship(
    item: Mapping[str, Any], creation_year: int
) -> HistoricalRelationship:
    searchable = " ".join(
        (
            _first_text(item.get("title")),
            _joined_text(item.get("subject") or item.get("subjects")),
        )
    ).casefold()
    expedition_related = "lewis and clark" in searchable or (
        "meriwether lewis" in searchable or "william clark" in searchable
    )
    if expedition_related and 1803 <= creation_year <= 1815:
        return HistoricalRelationship.NEAR_CONTEMPORARY
    if creation_year and creation_year <= 1900:
        return HistoricalRelationship.PERIOD_COMPARATIVE
    if creation_year:
        return HistoricalRelationship.LATER_REPRESENTATION
    return HistoricalRelationship.UNKNOWN


def _year(value: str) -> int:
    match = re.search(r"(?<!\d)(\d{4})(?!\d)", value)
    return int(match.group(1)) if match else 0


def _objects(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, list):
        return (entry for entry in value if isinstance(entry, Mapping))
    return ()


def _text_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, list):
        return tuple(str(entry).strip() for entry in value if str(entry).strip())
    return ()


def _joined_text(value: Any) -> str:
    return "\n".join(_text_tuple(value))


def _first_text(value: Any) -> str:
    values = _text_tuple(value)
    return values[0] if values else ""


def _https_url(value: str) -> str:
    if value.startswith("//"):
        return f"https:{value}"
    if value.startswith("http://"):
        return f"https://{value.removeprefix('http://')}"
    return value if value.startswith("https://") else ""


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Harvest and load the LOC Bitterroot media corpus")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--max-items", type=int)
    parser.add_argument("--no-thumbnails", action="store_true")
    args = parser.parse_args(argv)
    if args.max_items is not None and args.max_items < 1:
        parser.error("--max-items must be at least 1")

    result = harvest_loc(
        LocApiClient(),
        args.cache_dir,
        max_items=args.max_items,
        cache_thumbnails=not args.no_thumbnails,
    )
    clickhouse = get_clickhouse_client()
    try:
        bootstrap_database(clickhouse)
        embedding_settings = EmbeddingSettings.from_env()
        embedder = create_embedder(embedding_settings) if embedding_settings.enabled else None
        inserted = ClickHouseMediaRepository(
            clickhouse, embedder=embedder
        ).load_assets(result.assets)
    finally:
        clickhouse.close()
    print(
        f"Harvested {len(result.assets)} LOC asset(s); inserted {inserted}; "
        f"cached {result.raw_records_cached} raw response(s) and "
        f"{result.thumbnails_cached} thumbnail(s)"
    )


if __name__ == "__main__":
    main()
