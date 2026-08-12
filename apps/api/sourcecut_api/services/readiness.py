from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from sourcecut_api.corpora.odyssey import PERSEUS_REVISION

PROJECT_ROOT = Path(__file__).resolve().parents[4]
MANIFEST_PATH = PROJECT_ROOT / "data" / "manifests" / "odyssey" / "perseus.json"
OFFLINE_ROOT = PROJECT_ROOT / "data" / "offline" / "odyssey"
SNAPSHOT_PATH = OFFLINE_ROOT / "known-good-board.json"


def readiness_report() -> dict[str, Any]:
    failures: list[str] = []
    manifest: dict[str, Any] = {}
    if not MANIFEST_PATH.is_file():
        failures.append("pinned corpus manifest missing")
    else:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        if manifest.get("upstream_revision") != PERSEUS_REVISION:
            failures.append("corpus manifest revision does not match application pin")
        for version in manifest.get("versions", []):
            path = OFFLINE_ROOT / Path(str(version["upstream_path"])).name
            _check_hash(path, str(version["source_sha256"]), failures)
        annotation = manifest.get("linguistic_annotations", {})
        if annotation:
            path = OFFLINE_ROOT / Path(str(annotation["upstream_path"])).name
            _check_hash(path, str(annotation["source_sha256"]), failures)
    if not SNAPSHOT_PATH.is_file():
        failures.append("known-good board snapshot missing")
    live_research = bool(os.getenv("CLICKHOUSE_MCP_URL") and os.getenv("CLICKHOUSE_MCP_AUTH_TOKEN"))
    return {
        "status": "ready" if not failures and live_research else "degraded",
        "corpus_id": "odyssey",
        "release_revision": manifest.get("upstream_revision", ""),
        "offline_corpus_ready": not failures,
        "live_research_configured": live_research,
        "available_modes": [
            "reader",
            "voyage_graph",
            "metadata_only_assets",
            "completed_board_replay",
            "parallel_text_without_alignment",
        ],
        "failures": failures,
    }


def _check_hash(path: Path, expected: str, failures: list[str]) -> None:
    if not path.is_file():
        failures.append(f"offline source missing: {path.name}")
        return
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        failures.append(f"offline source hash mismatch: {path.name}")
