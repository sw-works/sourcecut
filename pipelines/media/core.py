from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from http.client import HTTPException
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from sourcecut_api.models import MediaAsset


@dataclass(frozen=True, slots=True)
class HttpPayload:
    body: bytes
    content_type: str


Transport = Callable[[str], HttpPayload]


class CacheConflictError(RuntimeError):
    pass


class ArchiveApiClient:
    def __init__(
        self,
        provider_name: str,
        allowed_media_hosts: set[str],
        *,
        transport: Transport | None = None,
        timeout_seconds: float = 30,
        attempts: int = 3,
    ) -> None:
        self._provider_name = provider_name
        self._allowed_media_hosts = allowed_media_hosts
        self._transport = transport or self._request
        self._timeout_seconds = timeout_seconds
        self._attempts = attempts

    def get_json(self, url: str) -> dict[str, Any]:
        payload = self._get(url)
        if "json" not in payload.content_type.lower():
            raise ValueError(f"{self._provider_name} returned non-JSON content for {url}")
        value = json.loads(payload.body)
        if not isinstance(value, dict):
            raise ValueError(f"{self._provider_name} returned a non-object JSON response for {url}")
        return value

    def get_media(self, url: str) -> HttpPayload:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in self._allowed_media_hosts:
            raise ValueError(f"Refusing non-{self._provider_name} media URL: {url}")
        payload = self._get(url)
        if not payload.content_type.lower().startswith("image/"):
            raise ValueError(f"{self._provider_name} thumbnail is not an image: {url}")
        return payload

    def _get(self, url: str) -> HttpPayload:
        for attempt in range(1, self._attempts + 1):
            try:
                return self._transport(url)
            except (HTTPError, URLError, TimeoutError, HTTPException) as error:
                retryable = (
                    not isinstance(error, HTTPError) or error.code == 429 or error.code >= 500
                )
                if not retryable or attempt == self._attempts:
                    raise
                time.sleep(attempt)
        raise AssertionError("retry loop exhausted")

    def _request(self, url: str) -> HttpPayload:
        request = Request(
            url,
            headers={"User-Agent": f"SourceCut/0.1 ({self._provider_name} archive ingest)"},
        )
        with urlopen(request, timeout=self._timeout_seconds) as response:
            return HttpPayload(
                body=response.read(),
                content_type=response.headers.get_content_type(),
            )


def cached_json(
    client: ArchiveApiClient,
    url: str,
    path: Path,
) -> tuple[dict[str, Any], bool]:
    if path.exists():
        value = json.loads(path.read_bytes())
        if not isinstance(value, dict):
            raise ValueError(f"Cached response is not an object: {path}")
        return value, False
    value = client.get_json(url)
    write_once(path, canonical_json(value).encode())
    return value, True


def cache_thumbnail(
    client: ArchiveApiClient,
    asset: MediaAsset,
    cache_dir: Path,
) -> tuple[Path, bool]:
    existing = tuple((cache_dir / "thumbnails").glob(f"{safe_filename(asset.provider_id)}.*"))
    if len(existing) > 1:
        raise CacheConflictError(f"Multiple cached thumbnails for {asset.provider_id}")
    if existing:
        return existing[0], False
    payload = client.get_media(asset.media_url)
    extension = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }.get(payload.content_type.split(";", 1)[0].lower(), ".img")
    path = cache_dir / "thumbnails" / f"{safe_filename(asset.provider_id)}{extension}"
    return path, write_once(path, payload.body)


def replace_asset_thumbnail(asset: MediaAsset, path: Path) -> MediaAsset:
    return asset.model_copy(update={"thumbnail_path": path.as_posix()})


def write_once(path: Path, data: bytes) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise CacheConflictError(f"Immutable cache conflict at {path}")
        return False
    path.write_bytes(data)
    return True


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", value)


def year_of(value: str) -> int:
    match = re.search(r"(?<!\d)(\d{4})(?!\d)", value)
    return int(match.group(1)) if match else 0


def mappings(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def texts(value: Any, *, split_commas: bool = False) -> tuple[str, ...]:
    """Coerce provider metadata into a tuple of non-empty strings.

    split_commas handles providers (NPS) that pack lists into one
    comma-separated string; the default treats a string as one value.
    """
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, str):
        if split_commas:
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return (value.strip(),) if value.strip() else ()
    return ()


def load_assets_to_clickhouse(assets: Sequence[MediaAsset]) -> int:
    """Shared provider epilogue: bootstrap, embed when enabled, insert.

    Every provider main() must go through this so embeddings are wired
    uniformly — a provider that skips the embedder loads assets that are
    invisible to semantic ranking.
    """
    from pipelines.embeddings import EmbeddingSettings, create_embedder
    from sourcecut_api.db.bootstrap import bootstrap_database
    from sourcecut_api.db.client import get_clickhouse_client
    from sourcecut_api.repositories.media import ClickHouseMediaRepository

    client = get_clickhouse_client()
    try:
        bootstrap_database(client)
        settings = EmbeddingSettings.from_env()
        embedder = create_embedder(settings) if settings.enabled else None
        return ClickHouseMediaRepository(client, embedder=embedder).load_assets(assets)
    finally:
        client.close()
