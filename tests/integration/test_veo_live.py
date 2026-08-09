from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

import pytest

from sourcecut_api.integrations.google_video import create_google_video_clients
from sourcecut_api.models import ShotBrief
from sourcecut_api.services.previs import PrevisSettings

pytestmark = pytest.mark.skipif(
    os.getenv("SOURCECUT_RUN_LIVE_VIDEO_TESTS") != "true",
    reason="set SOURCECUT_RUN_LIVE_VIDEO_TESTS=true with a reviewed brief and cost approval",
)


def test_live_veo_generates_only_after_explicit_cost_approval(tmp_path: Path) -> None:
    settings = PrevisSettings.from_env()
    brief_path = Path(os.environ["SOURCECUT_VIDEO_LIVE_BRIEF_PATH"])
    brief = ShotBrief.model_validate_json(brief_path.read_text(encoding="utf-8"))
    estimated_cost = settings.estimated_cost(brief.duration_seconds)
    assert estimated_cost is not None
    approval = os.getenv("SOURCECUT_VIDEO_LIVE_COST_APPROVED")
    assert approval == "I_APPROVE_UP_TO_10_USD"
    assert estimated_cost <= settings.max_estimated_cost_usd
    assert not settings.generation_blockers
    print(f"Approved estimated maximum charge: ${estimated_cost:.2f}")

    _, generator, _ = create_google_video_clients()
    operation_name = asyncio.run(
        generator.submit(
            "live-acceptance",
            brief,
            (),
            output_gcs_uri=os.getenv("SOURCECUT_VIDEO_LIVE_OUTPUT_GCS_URI"),
        )
    )
    result = None
    for _ in range(36):
        result = asyncio.run(generator.poll(operation_name))
        if result.done:
            break
        time.sleep(10)

    assert result is not None and result.done
    assert not result.blocked, result.safe_error
    assert not result.safe_error
    assert result.video_bytes or result.output_uri
    if result.video_bytes:
        (tmp_path / "live-previs.mp4").write_bytes(result.video_bytes)
