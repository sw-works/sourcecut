"""Capture one real research run as a committed example board.

The landing page opens on a finished board rather than an empty form, so a
visitor sees real work before deciding whether to spend ninety seconds on a
live run — and so the page still says something when ClickHouse is
unreachable or a credential has expired.

That example is a genuine run, captured here and committed: the board, the
timeline events it emitted, and copies of the archive thumbnails it selected.
Nothing is synthesised. The snapshot records when it ran and under which
session id so the page can say plainly that it is an example rather than
passing a cached board off as fresh.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from sourcecut_api.models import ResearchBoard

SNAPSHOT_VERSION = 1
DEFAULT_SNAPSHOT = Path("data/examples/example-board.json")
DEFAULT_ASSET_DIR = Path("apps/web/public/example-assets")
ASSET_URL_PREFIX = "/example-assets"


class ExampleEvent(BaseModel):
    """One timeline event, in the shape the web timeline already renders."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int
    event_type: str
    stage: str
    status: str
    message: str
    payload: dict[str, Any] = {}
    duration_ms: int = 0


class ExampleBoard(BaseModel):
    """A captured run, with everything the landing page needs to render it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_version: int = SNAPSHOT_VERSION
    session_id: str
    captured_at: datetime
    prompt: str
    board: ResearchBoard
    events: tuple[ExampleEvent, ...] = ()
    # asset_id -> a path under the web app's public directory. Thumbnails are
    # copied out of the archive cache so the example renders with the API down.
    asset_thumbnails: dict[str, str] = {}


def load_example(path: Path = DEFAULT_SNAPSHOT) -> ExampleBoard | None:
    """Read the committed snapshot, or None when none has been captured."""
    if not path.is_file():
        return None
    return ExampleBoard.model_validate_json(path.read_text(encoding="utf-8"))


def copy_thumbnails(
    board: ResearchBoard,
    *,
    asset_dir: Path,
    cache_root: Path = Path("data/archive-cache/loc"),
) -> dict[str, str]:
    """Copy each selected asset's cached thumbnail next to the web app.

    Only assets that made it into a board section are copied: the reviewed set
    includes rejected candidates the page never shows. A missing or
    out-of-cache thumbnail is skipped rather than failing the capture — the
    card falls back to its empty well.
    """
    resolved_cache = cache_root.resolve()
    selected = {
        item.asset.asset_id: item.asset
        for section in board.sections
        for item in section.assets
    }
    if not selected:
        return {}
    asset_dir.mkdir(parents=True, exist_ok=True)
    thumbnails: dict[str, str] = {}
    for asset_id, asset in sorted(selected.items()):
        if not asset.thumbnail_path:
            continue
        source = Path(asset.thumbnail_path).resolve()
        if not source.is_relative_to(resolved_cache) or not source.is_file():
            continue
        target = asset_dir / f"{asset_id.replace(':', '-')}{source.suffix}"
        shutil.copyfile(source, target)
        thumbnails[asset_id] = f"{ASSET_URL_PREFIX}/{target.name}"
    return thumbnails


async def capture(
    prompt: str,
    *,
    session_id: str | None = None,
    asset_dir: Path = DEFAULT_ASSET_DIR,
) -> ExampleBoard:
    """Run the real board path once and return it as a snapshot."""
    # Imported here so `--help` and the loader work without ClickHouse
    # configuration present.
    from sourcecut_api.services.board import create_board_service

    events: list[ExampleEvent] = []

    def sink(
        event_type: str,
        stage: str,
        status: str,
        message: str,
        payload: dict[str, Any],
        duration_ms: int,
    ) -> None:
        events.append(
            ExampleEvent(
                sequence=len(events) + 1,
                event_type=event_type,
                stage=stage,
                status=status,
                message=message,
                payload=payload or {},
                duration_ms=duration_ms,
            )
        )

    service = create_board_service(event_sink=sink)
    board = await service.build_board(prompt)
    return ExampleBoard(
        session_id=session_id or f"example-{uuid.uuid4().hex[:8]}",
        captured_at=datetime.now(UTC),
        prompt=prompt,
        board=board,
        events=tuple(events),
        asset_thumbnails=copy_thumbnails(board, asset_dir=asset_dir),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture one real research run as the committed example board"
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default=(
            "Crossing the Bitterroot Mountains, September 1805. I need terrain, "
            "weather, what they were eating, and what the horses were doing."
        ),
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--asset-dir", type=Path, default=DEFAULT_ASSET_DIR)
    parser.add_argument("--session-id")
    args = parser.parse_args()

    example = asyncio.run(
        capture(args.prompt, session_id=args.session_id, asset_dir=args.asset_dir)
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(example.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    coverage = example.board.coverage
    met = f"{coverage.met_count} of {len(coverage.entries)}" if coverage else "unknown"
    print(
        f"Captured {args.out}: {len(example.board.evidence_matrix)} requirement(s), "
        f"{met} covered, {len(example.events)} event(s), "
        f"{len(example.asset_thumbnails)} thumbnail(s)."
    )


if __name__ == "__main__":
    main()
