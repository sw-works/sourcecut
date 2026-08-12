from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

from pipelines.classics import build_classical_passages, parse_odyssey_tei
from sourcecut_api.corpora.odyssey import OdysseyCorpusAdapter
from sourcecut_api.db.client import get_clickhouse_client
from sourcecut_api.db.migrations import bootstrap_database
from sourcecut_api.repositories import (
    ClickHouseCatalogRepository,
    ClickHouseClassicalTextRepository,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "manifests" / "odyssey" / "perseus.json"


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load the pinned Perseus Odyssey corpus")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--source-dir",
        type=Path,
        help="Read pinned TEI filenames from this directory instead of downloading them",
    )
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    detail = OdysseyCorpusAdapter().detail()
    parsed_versions = []
    for item in manifest["versions"]:
        upstream_path = str(item["upstream_path"])
        raw_content = _source_content(
            upstream_path,
            str(manifest["upstream_repository"]),
            str(manifest["upstream_revision"]),
            args.source_dir,
        )
        actual_sha256 = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()
        expected_sha256 = str(item["source_sha256"])
        if actual_sha256 != expected_sha256:
            raise ValueError(
                f"Pinned source hash mismatch for {item['version_id']}: "
                f"expected {expected_sha256}, received {actual_sha256}"
            )
        corrections = {
            (int(correction["book"]), int(correction["unit_index"])): int(
                correction["corrected_line_start"]
            )
            for correction in item.get("citation_corrections", [])
        }
        parsed_versions.append(
            parse_odyssey_tei(
                raw_content,
                version_id=str(item["version_id"]),
                upstream_path=upstream_path,
                upstream_revision=str(manifest["upstream_revision"]),
                citation_corrections=corrections,
            )
        )

    hashes = {item.document.version_id: item.document.raw_sha256 for item in parsed_versions}
    detail = detail.model_copy(
        update={
            "versions": tuple(
                version.model_copy(update={"source_sha256": hashes[version.version_id]})
                for version in detail.versions
            )
        }
    )
    client = get_clickhouse_client()
    bootstrap_database(client)
    ClickHouseCatalogRepository(client).load_catalog(detail)
    repository = ClickHouseClassicalTextRepository(client)
    total_units = 0
    total_passages = 0
    for parsed in parsed_versions:
        passages = build_classical_passages(parsed.units)
        result = repository.load_version(parsed, passages)
        total_units += result.units_inserted
        total_passages += result.passages_inserted
    print(
        f"Loaded {len(parsed_versions)} Odyssey versions: "
        f"{total_units} citable units, {total_passages} passages"
    )


def _source_content(
    upstream_path: str,
    repository: str,
    revision: str,
    source_dir: Path | None,
) -> str:
    if source_dir is not None:
        return (source_dir / Path(upstream_path).name).read_text(encoding="utf-8")
    owner_repo = repository.removeprefix("https://github.com/")
    url = f"https://raw.githubusercontent.com/{owner_repo}/{revision}/{upstream_path}"
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read().decode("utf-8")


if __name__ == "__main__":
    main()
