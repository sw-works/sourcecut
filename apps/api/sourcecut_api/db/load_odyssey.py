from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

from pipelines.classics import (
    build_classical_passages,
    load_entity_theme_release,
    load_geography_release,
    load_narrative_release,
    parse_odyssey_tei,
    parse_odyssey_treebank,
)
from pipelines.media.met import load_met_odyssey_release
from sourcecut_api.corpora.odyssey import OdysseyCorpusAdapter
from sourcecut_api.db.client import get_clickhouse_client
from sourcecut_api.db.migrations import bootstrap_database
from sourcecut_api.repositories import (
    ClickHouseCatalogRepository,
    ClickHouseClassicalTextRepository,
    ClickHouseEntityThemeRepository,
    ClickHouseGeographyRepository,
    ClickHouseLinguisticRepository,
    ClickHouseMediaRepository,
    ClickHouseNarrativeRepository,
    ClickHouseVisualCultureRepository,
)
from sourcecut_api.telemetry import telemetry_span

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "manifests" / "odyssey" / "perseus.json"
DEFAULT_NARRATIVE = PROJECT_ROOT / "data" / "reference" / "odyssey_narrative.json"
DEFAULT_GEOGRAPHY = PROJECT_ROOT / "data" / "reference" / "odyssey_geography.json"
DEFAULT_ENTITIES = PROJECT_ROOT / "data" / "reference" / "odyssey_entities_themes.json"
DEFAULT_VISUAL_CULTURE = PROJECT_ROOT / "data" / "reference" / "odyssey_visual_culture.json"
DEFAULT_MET_CACHE = PROJECT_ROOT / "data" / "cache" / "met"


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
        with telemetry_span(
            "sourcecut.odyssey.tei.parse",
            {
                "sourcecut.corpus.id": "odyssey",
                "sourcecut.version.id": str(item["version_id"]),
            },
        ):
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
    annotation = manifest["linguistic_annotations"]
    treebank_content = _source_content(
        str(annotation["upstream_path"]),
        str(annotation["repository"]),
        str(annotation["upstream_revision"]),
        args.source_dir,
    )
    greek = next(item for item in parsed_versions if item.document.version_id.endswith("grc2"))
    with telemetry_span(
        "sourcecut.odyssey.linguistic.enrich",
        {
            "sourcecut.corpus.id": "odyssey",
            "sourcecut.annotation.release_id": str(annotation["annotation_release_id"]),
        },
    ):
        linguistics = parse_odyssey_treebank(
            treebank_content,
            text_units=greek.units,
            upstream_revision=str(annotation["upstream_revision"]),
            upstream_path=str(annotation["upstream_path"]),
            repository_url=str(annotation["repository"]),
            expected_sha256=str(annotation["source_sha256"]),
        )
    linguistic_result = ClickHouseLinguisticRepository(client).load(linguistics)
    narrative = load_narrative_release(DEFAULT_NARRATIVE, greek.units)
    narrative_result = ClickHouseNarrativeRepository(client).load(narrative)
    geography_result = ClickHouseGeographyRepository(client).load(
        load_geography_release(DEFAULT_GEOGRAPHY)
    )
    entity_result = ClickHouseEntityThemeRepository(client).load(
        load_entity_theme_release(
            DEFAULT_ENTITIES,
            tuple(unit for parsed in parsed_versions for unit in parsed.units),
        )
    )
    visual_release = load_met_odyssey_release(DEFAULT_VISUAL_CULTURE, DEFAULT_MET_CACHE)
    ClickHouseMediaRepository(client).load_assets(visual_release.assets)
    visual_result = ClickHouseVisualCultureRepository(client).load(visual_release)
    print(
        f"Loaded {len(parsed_versions)} Odyssey versions: "
        f"{total_units} citable units, {total_passages} passages, "
        f"{linguistic_result.tokens_inserted} tokens, "
        f"{linguistic_result.formulae_inserted} exact formula occurrences"
        f", {narrative_result.events_inserted} narrative events, "
        f"{narrative_result.speeches_inserted} speeches"
        f", {geography_result.nodes_inserted} route nodes"
        f", {entity_result.mentions_inserted} entity mentions"
        f", {visual_result.metadata_inserted} visual assets"
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
