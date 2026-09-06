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
from sourcecut_api.models.previs import (
    ConsistencyReport,
    EvidenceStrictness,
    PrevisJob,
    ShotBrief,
    ShotType,
)

SNAPSHOT_VERSION = 1
DEFAULT_SNAPSHOT = Path("data/examples/example-board.json")
DEFAULT_ASSET_DIR = Path("apps/web/public/example-assets")
ASSET_URL_PREFIX = "/example-assets"
# A generated clip is minutes of provider work; a capture waits rather than
# reporting a job that is still running as a finished one.
PREVIS_POLL_SECONDS = 10
PREVIS_TIMEOUT_SECONDS = 900


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


class CapturedPrevis(BaseModel):
    """One previsualization, kept the way the board around it is kept.

    A previs job outlives its research session in the previs store, but nothing
    durable points at it: the job id lives in one browser's local storage. So a
    capture copies the clip next to the web app the way it already copies
    archive thumbnails, and records the brief and the critic's report beside
    it. The board page can then play a real, reviewed clip with no API, no
    bucket and no session — and, as with the board, it has to have come from a
    real run. Nothing here is written by hand.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    section_title: str
    brief: ShotBrief
    job: PrevisJob
    report: ConsistencyReport | None = None
    disclosure: str
    # A path under the web app's public directory, as with asset_thumbnails.
    video_url: str


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
    previs: CapturedPrevis | None = None


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


async def capture_previs(
    session_id: str,
    board: ResearchBoard,
    *,
    section_title: str,
    shot_type: ShotType,
    strictness: EvidenceStrictness,
    duration_seconds: int,
    asset_dir: Path,
) -> CapturedPrevis:
    """Produce one reviewed clip for a section and copy it next to the web app.

    This spends money: it is only ever reached behind --approve-paid. The
    approval the API requires of a person is given here explicitly, against the
    fingerprint of the brief that was actually built, so a brief that changed
    between building and approving cannot be generated by accident.
    """
    from sourcecut_api.models.previs import GenerationApproval, PrevisJobStatus
    from sourcecut_api.models.previs import ShotBriefRequest
    from sourcecut_api.services.previs import create_previs_service

    service = create_previs_service()
    titles = [section.title for section in board.sections]
    if section_title not in titles:
        raise SystemExit(
            f"No board section titled {section_title!r}. This board has: "
            + ", ".join(repr(title) for title in titles)
        )

    envelope = await service.create_brief(
        session_id,
        board,
        ShotBriefRequest(
            board_section_title=section_title,
            shot_type=shot_type,
            strictness=strictness,
            duration_seconds=duration_seconds,
        ),
    )
    if not envelope.can_generate:
        raise SystemExit("Previs is blocked: " + " ".join(envelope.blockers))

    job = await service.generate(
        envelope.brief.shot_brief_id,
        GenerationApproval(approved=True, brief_fingerprint=envelope.brief_fingerprint),
    )
    waited = 0
    while job.job.status in (
        PrevisJobStatus.QUEUED,
        PrevisJobStatus.GENERATING,
        PrevisJobStatus.REVIEWING,
    ):
        if waited >= PREVIS_TIMEOUT_SECONDS:
            raise SystemExit(
                f"Previs job {job.job.job_id} was still {job.job.status.value} after "
                f"{PREVIS_TIMEOUT_SECONDS}s. The job is safe; recover it by id."
            )
        await asyncio.sleep(PREVIS_POLL_SECONDS)
        waited += PREVIS_POLL_SECONDS
        job = await service.get_job(job.job.job_id)

    if job.job.status is not PrevisJobStatus.COMPLETE:
        raise SystemExit(
            f"Previs job {job.job.job_id} ended {job.job.status.value}: "
            f"{job.job.safe_error or 'no reason reported'}"
        )

    # A clip nobody checked is exactly what this project refuses to publish.
    job = await service.review(job.job.job_id)

    content, media_type = service.read_video(job.job.job_id)
    suffix = ".mp4" if media_type == "video/mp4" else Path(job.job.output_uri).suffix
    asset_dir.mkdir(parents=True, exist_ok=True)
    target = asset_dir / f"previs-{job.job.job_id}{suffix}"
    target.write_bytes(content)

    return CapturedPrevis(
        section_title=section_title,
        brief=envelope.brief,
        job=job.job,
        report=job.report,
        disclosure=job.disclosure,
        video_url=f"{ASSET_URL_PREFIX}/{target.name}",
    )


async def capture(
    prompt: str,
    *,
    session_id: str | None = None,
    asset_dir: Path = DEFAULT_ASSET_DIR,
    previs_section: str | None = None,
    previs_shot_type: ShotType = ShotType.ESTABLISHING,
    previs_strictness: EvidenceStrictness = EvidenceStrictness.STRICT,
    previs_duration: int = 8,
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
    resolved_session = session_id or f"example-{uuid.uuid4().hex[:8]}"
    previs = (
        await capture_previs(
            resolved_session,
            board,
            section_title=previs_section,
            shot_type=previs_shot_type,
            strictness=previs_strictness,
            duration_seconds=previs_duration,
            asset_dir=asset_dir,
        )
        if previs_section
        else None
    )
    return ExampleBoard(
        session_id=resolved_session,
        captured_at=datetime.now(UTC),
        prompt=prompt,
        board=board,
        events=tuple(events),
        asset_thumbnails=copy_thumbnails(board, asset_dir=asset_dir),
        previs=previs,
    )


async def attach_previs(
    snapshot: Path,
    *,
    section_title: str,
    shot_type: ShotType,
    strictness: EvidenceStrictness,
    duration_seconds: int,
    asset_dir: Path,
) -> ExampleBoard:
    """Add a previs to a snapshot already captured, without rebuilding it.

    Re-running the research to attach a clip would throw the board away: the
    planner is not deterministic, and a second run over the same scope has
    already come back with fewer requirements met than the one it replaced.
    So the board is read from disk and only the previs is new.
    """
    existing = load_example(snapshot)
    if existing is None:
        raise SystemExit(f"No captured snapshot at {snapshot}")
    previs = await capture_previs(
        existing.session_id,
        existing.board,
        section_title=section_title,
        shot_type=shot_type,
        strictness=strictness,
        duration_seconds=duration_seconds,
        asset_dir=asset_dir,
    )
    return existing.model_copy(update={"previs": previs})


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
    parser.add_argument(
        "--previs-section",
        help=(
            "Board section title to previsualise. Costs money: requires "
            "--approve-paid."
        ),
    )
    parser.add_argument(
        "--previs-shot-type",
        default=ShotType.ESTABLISHING.value,
        choices=[member.value for member in ShotType],
    )
    parser.add_argument(
        "--previs-strictness",
        default=EvidenceStrictness.STRICT.value,
        choices=[member.value for member in EvidenceStrictness],
    )
    parser.add_argument("--previs-duration", type=int, default=8)
    parser.add_argument(
        "--attach-to",
        type=Path,
        help=(
            "Add a previs to this already-captured snapshot instead of running "
            "the research again. Writes back to --out (default: the same file)."
        ),
    )
    parser.add_argument(
        "--approve-paid",
        action="store_true",
        help="Approve one paid video generation. Without it --previs-section is refused.",
    )
    args = parser.parse_args()

    if args.attach_to and not args.previs_section:
        raise SystemExit("--attach-to needs --previs-section to say what to previsualise.")

    # The paid step is opt-in twice: name a section, and say so. A capture must
    # never be able to spend because a default changed.
    if args.previs_section and not args.approve_paid:
        raise SystemExit(
            "--previs-section runs one paid video generation. Re-run with "
            "--approve-paid to authorise it."
        )

    if args.attach_to:
        out = args.out if args.out != DEFAULT_SNAPSHOT else args.attach_to
        example = asyncio.run(
            attach_previs(
                args.attach_to,
                section_title=args.previs_section,
                shot_type=ShotType(args.previs_shot_type),
                strictness=EvidenceStrictness(args.previs_strictness),
                duration_seconds=args.previs_duration,
                asset_dir=args.asset_dir,
            )
        )
        out.write_text(
            json.dumps(example.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
        )
        assert example.previs is not None
        findings = len(example.previs.report.findings) if example.previs.report else 0
        print(
            f"Attached previs to {out}: {example.previs.video_url}, "
            f"{findings} consistency finding(s), "
            f"est. ${example.previs.job.estimated_cost_usd:.2f}."
        )
        return

    example = asyncio.run(
        capture(
            args.prompt,
            session_id=args.session_id,
            asset_dir=args.asset_dir,
            previs_section=args.previs_section,
            previs_shot_type=ShotType(args.previs_shot_type),
            previs_strictness=EvidenceStrictness(args.previs_strictness),
            previs_duration=args.previs_duration,
        )
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
    if example.previs:
        findings = len(example.previs.report.findings) if example.previs.report else 0
        print(
            f"Captured previs for {example.previs.section_title!r}: "
            f"{example.previs.video_url}, {findings} consistency finding(s), "
            f"est. ${example.previs.job.estimated_cost_usd:.2f}."
        )


if __name__ == "__main__":
    main()
