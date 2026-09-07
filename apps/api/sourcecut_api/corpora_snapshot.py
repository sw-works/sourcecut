"""Capture the corpus pipelines as a committed snapshot.

The landing page opens on the corpora themselves, and it is prerendered: it has
to say what they are with no backend reachable. The counts, though, live in
ClickHouse and are read through the read-only MCP role.

So they are captured the way an example board is — by running the real query
once and committing the result — rather than duplicated by hand into a file
that would drift. The page renders the snapshot, and refreshes from
`/api/v1/pipelines` when the API answers.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from sourcecut_api.corpora import create_corpus_registry
from sourcecut_api.models.pipeline import CorpusPipeline

DEFAULT_SNAPSHOT = Path("data/examples/corpora.json")


class CorporaSnapshot(BaseModel):
    """Every corpus and how far its ingestion had run when this was captured."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    captured_at: datetime
    pipelines: tuple[CorpusPipeline, ...]


async def capture() -> CorporaSnapshot:
    from sourcecut_api.agents.planner import load_scopes
    from sourcecut_api.integrations import ClickHouseMcpClient, ClickHouseMcpSettings
    from sourcecut_api.services.pipeline_state import list_pipelines

    registry = create_corpus_registry()
    client = ClickHouseMcpClient(ClickHouseMcpSettings.from_env())
    counts: dict[str, dict[str, int]] = {}
    for record in registry.list():
        counts[record.corpus_id] = await client.get_corpus_pipeline_counts(record.corpus_id)
    return CorporaSnapshot(
        captured_at=datetime.now(UTC),
        pipelines=list_pipelines(registry, counts, scopes=load_scopes()),
    )


def load_snapshot(path: Path = DEFAULT_SNAPSHOT) -> CorporaSnapshot | None:
    if not path.is_file():
        return None
    return CorporaSnapshot.model_validate_json(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture the corpus pipelines for the prerendered pages"
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_SNAPSHOT)
    args = parser.parse_args()

    snapshot = asyncio.run(capture())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(snapshot.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
    )
    for pipeline in snapshot.pipelines:
        done = sum(1 for stage in pipeline.stages if stage.state == "done")
        print(
            f"{pipeline.corpus_id}: {done}/{len(pipeline.stages)} steps complete, "
            f"{len(pipeline.windows)} window(s)"
        )


if __name__ == "__main__":
    main()
