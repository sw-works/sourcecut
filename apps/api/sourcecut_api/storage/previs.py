from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Any, Protocol, TypeVar
from urllib.parse import urlparse

from pydantic import BaseModel

from sourcecut_api.models import ConsistencyReport, PrevisJob, ShotBrief

SAFE_ID = re.compile(r"^[A-Za-z0-9-]{1,128}$")
ModelT = TypeVar("ModelT", bound=BaseModel)


class PrevisStore(Protocol):
    def save_brief(self, brief: ShotBrief) -> None: ...

    def load_brief(self, brief_id: str) -> ShotBrief: ...

    def save_references(
        self, brief_id: str, references: tuple[tuple[str, bytes, str], ...]
    ) -> None: ...

    def read_references(
        self, brief_id: str, asset_ids: tuple[str, ...]
    ) -> tuple[tuple[bytes, str], ...]: ...

    def save_job(self, job: PrevisJob) -> None: ...

    def load_job(self, job_id: str) -> PrevisJob: ...

    def save_report(self, report: ConsistencyReport) -> None: ...

    def load_report(self, job_id: str) -> ConsistencyReport | None: ...

    def save_video(self, job_id: str, content: bytes) -> str: ...

    def materialize_provider_video(self, job_id: str, provider_uri: str) -> str: ...

    def read_video(self, job_id: str) -> tuple[bytes, str]: ...

    def provider_output_prefix(self, job_id: str) -> str | None: ...


class FilePrevisStore:
    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()

    def save_brief(self, brief: ShotBrief) -> None:
        self._save_model(self._brief_path(brief.shot_brief_id), brief)

    def load_brief(self, brief_id: str) -> ShotBrief:
        return self._load_model(self._brief_path(brief_id), ShotBrief)

    def save_references(
        self, brief_id: str, references: tuple[tuple[str, bytes, str], ...]
    ) -> None:
        directory = self._brief_path(brief_id).parent / "references"
        manifest: dict[str, dict[str, str]] = {}
        for asset_id, content, mime_type in references:
            name = f"{_asset_key(asset_id)}.bin"
            directory.mkdir(parents=True, exist_ok=True)
            (directory / name).write_bytes(content)
            manifest[asset_id] = {"name": name, "mime_type": mime_type}
        path = directory / "manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

    def read_references(
        self, brief_id: str, asset_ids: tuple[str, ...]
    ) -> tuple[tuple[bytes, str], ...]:
        directory = self._brief_path(brief_id).parent / "references"
        path = directory / "manifest.json"
        if not asset_ids:
            return ()
        if not path.is_file():
            raise FileNotFoundError("Previs reference manifest was not found")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        return tuple(
            (
                (directory / manifest[asset_id]["name"]).read_bytes(),
                manifest[asset_id]["mime_type"],
            )
            for asset_id in asset_ids
        )

    def save_job(self, job: PrevisJob) -> None:
        self._save_model(self._job_path(job.job_id), job)

    def load_job(self, job_id: str) -> PrevisJob:
        return self._load_model(self._job_path(job_id), PrevisJob)

    def save_report(self, report: ConsistencyReport) -> None:
        self._save_model(self._report_path(report.job_id), report)

    def load_report(self, job_id: str) -> ConsistencyReport | None:
        path = self._report_path(job_id)
        if not path.is_file():
            return None
        return self._load_model(path, ConsistencyReport)

    def save_video(self, job_id: str, content: bytes) -> str:
        if not content:
            raise ValueError("Generated video is empty")
        path = self._video_path(job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(content)
        temporary.replace(path)
        return str(path)

    def materialize_provider_video(self, job_id: str, provider_uri: str) -> str:
        raise ValueError(f"Local previs storage cannot materialize {provider_uri!r}")

    def read_video(self, job_id: str) -> tuple[bytes, str]:
        path = self._video_path(job_id)
        if not path.is_file():
            raise FileNotFoundError(f"Previs video was not found for {job_id}")
        return path.read_bytes(), "video/mp4"

    def provider_output_prefix(self, job_id: str) -> str | None:
        _safe_id(job_id)
        return None

    def _brief_path(self, brief_id: str) -> Path:
        return self._root / "briefs" / _safe_id(brief_id) / "brief.json"

    def _job_path(self, job_id: str) -> Path:
        return self._root / "jobs" / _safe_id(job_id) / "manifest.json"

    def _report_path(self, job_id: str) -> Path:
        return self._root / "jobs" / _safe_id(job_id) / "review.json"

    def _video_path(self, job_id: str) -> Path:
        return self._root / "jobs" / _safe_id(job_id) / "output.mp4"

    @staticmethod
    def _save_model(path: Path, model: BaseModel) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(model.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _load_model(path: Path, model_type: type[ModelT]) -> ModelT:
        if not path.is_file():
            raise FileNotFoundError(path)
        return model_type.model_validate_json(path.read_text(encoding="utf-8"))


class GcsPrevisStore:
    def __init__(self, uri: str, *, client: Any | None = None) -> None:
        parsed = urlparse(uri)
        if parsed.scheme != "gs" or not parsed.netloc:
            raise ValueError("GCS previs storage URI must be gs://bucket[/prefix]")
        if client is None:
            from google.cloud import storage

            client = storage.Client()
        self._client = client
        self._bucket_name = parsed.netloc
        self._bucket = client.bucket(parsed.netloc)
        self._prefix = parsed.path.strip("/")

    def save_brief(self, brief: ShotBrief) -> None:
        self._save_model(self._key("briefs", brief.shot_brief_id, "brief.json"), brief)

    def load_brief(self, brief_id: str) -> ShotBrief:
        return self._load_model(
            self._key("briefs", _safe_id(brief_id), "brief.json"), ShotBrief
        )

    def save_references(
        self, brief_id: str, references: tuple[tuple[str, bytes, str], ...]
    ) -> None:
        manifest: dict[str, dict[str, str]] = {}
        for asset_id, content, mime_type in references:
            name = f"{_asset_key(asset_id)}.bin"
            key = self._key("briefs", _safe_id(brief_id), "references", name)
            self._bucket.blob(key).upload_from_string(content, content_type=mime_type)
            manifest[asset_id] = {"name": name, "mime_type": mime_type}
        manifest_key = self._key(
            "briefs", _safe_id(brief_id), "references", "manifest.json"
        )
        self._bucket.blob(manifest_key).upload_from_string(
            json.dumps(manifest, sort_keys=True), content_type="application/json"
        )

    def read_references(
        self, brief_id: str, asset_ids: tuple[str, ...]
    ) -> tuple[tuple[bytes, str], ...]:
        if not asset_ids:
            return ()
        manifest_key = self._key(
            "briefs", _safe_id(brief_id), "references", "manifest.json"
        )
        manifest = json.loads(self._bucket.blob(manifest_key).download_as_text())
        return tuple(
            (
                self._bucket.blob(
                    self._key(
                        "briefs",
                        _safe_id(brief_id),
                        "references",
                        manifest[asset_id]["name"],
                    )
                ).download_as_bytes(),
                manifest[asset_id]["mime_type"],
            )
            for asset_id in asset_ids
        )

    def save_job(self, job: PrevisJob) -> None:
        self._save_model(self._key("jobs", job.job_id, "manifest.json"), job)

    def load_job(self, job_id: str) -> PrevisJob:
        return self._load_model(
            self._key("jobs", _safe_id(job_id), "manifest.json"), PrevisJob
        )

    def save_report(self, report: ConsistencyReport) -> None:
        self._save_model(self._key("jobs", report.job_id, "review.json"), report)

    def load_report(self, job_id: str) -> ConsistencyReport | None:
        key = self._key("jobs", _safe_id(job_id), "review.json")
        blob = self._bucket.blob(key)
        if not blob.exists():
            return None
        return ConsistencyReport.model_validate_json(blob.download_as_text())

    def save_video(self, job_id: str, content: bytes) -> str:
        if not content:
            raise ValueError("Generated video is empty")
        key = self._key("jobs", _safe_id(job_id), "output.mp4")
        self._bucket.blob(key).upload_from_string(content, content_type="video/mp4")
        return f"gs://{self._bucket_name}/{key}"

    def materialize_provider_video(self, job_id: str, provider_uri: str) -> str:
        parsed = urlparse(provider_uri)
        if parsed.scheme != "gs" or not parsed.netloc or not parsed.path.strip("/"):
            raise ValueError("Provider video URI must be a GCS object")
        source_bucket = self._client.bucket(parsed.netloc)
        source = source_bucket.blob(parsed.path.strip("/"))
        destination_key = self._key("jobs", _safe_id(job_id), "output.mp4")
        destination = self._bucket.blob(destination_key)
        if parsed.netloc == self._bucket_name and source.name == destination.name:
            return provider_uri
        source_bucket.copy_blob(source, self._bucket, new_name=destination_key)
        return f"gs://{self._bucket_name}/{destination_key}"

    def read_video(self, job_id: str) -> tuple[bytes, str]:
        key = self._key("jobs", _safe_id(job_id), "output.mp4")
        blob = self._bucket.blob(key)
        if not blob.exists():
            raise FileNotFoundError(f"Previs video was not found for {job_id}")
        return blob.download_as_bytes(), blob.content_type or "video/mp4"

    def provider_output_prefix(self, job_id: str) -> str | None:
        key = self._key("jobs", _safe_id(job_id), "provider")
        return f"gs://{self._bucket_name}/{key}/"

    def _key(self, *parts: str) -> str:
        key = str(PurePosixPath(*(part for part in (self._prefix, *parts) if part)))
        return key.lstrip("/")

    def _save_model(self, key: str, model: BaseModel) -> None:
        self._bucket.blob(key).upload_from_string(
            model.model_dump_json(indent=2), content_type="application/json"
        )

    def _load_model(self, key: str, model_type: type[ModelT]) -> ModelT:
        blob = self._bucket.blob(key)
        if not blob.exists():
            raise FileNotFoundError(key)
        return model_type.model_validate_json(blob.download_as_text())


def create_previs_store(uri: str) -> PrevisStore:
    if uri.startswith("gs://"):
        return GcsPrevisStore(uri)
    return FilePrevisStore(uri)


def _safe_id(value: str) -> str:
    if not SAFE_ID.fullmatch(value):
        raise ValueError("Previs identifier contains unsupported characters")
    return value


def _asset_key(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode()).hexdigest()[:32]
