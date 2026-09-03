from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from sourcecut_api.examples import (
    ExampleBoard,
    ExampleEvent,
    copy_thumbnails,
    load_example,
)
from sourcecut_api.models import (
    BoardConfidence,
    BoardMediaAsset,
    BoardSection,
    HistoricalRelationship,
    ResearchBoard,
    RightsStatus,
    VerifiedAsset,
)


def asset(asset_id: str, thumbnail_path: str) -> VerifiedAsset:
    return VerifiedAsset(
        asset=BoardMediaAsset(
            asset_id=asset_id,
            provider="loc",
            title="A map of Lewis and Clark's track",
            asset_type="cartographic",
            creation_date_text="1804",
            source_url="https://www.loc.gov/item/79692907/",
            thumbnail_path=thumbnail_path,
            rights_status=RightsStatus.PUBLIC_DOMAIN,
            rights_text="Public domain.",
        ),
        requirement_id="bitterroot-september-1805:terrain",
        confidence=BoardConfidence.HIGH,
        production_use="Terrain references.",
        why_selected="Near-contemporary map matching the requirement.",
        evidence=(),
        historical_relationship=HistoricalRelationship.NEAR_CONTEMPORARY,
    )


def board(*assets: VerifiedAsset) -> ResearchBoard:
    return ResearchBoard(
        prompt="Crossing the Bitterroots.",
        title="Crossing the Bitterroots — September 1805",
        summary="Testing.",
        evidence_matrix=(),
        sections=(BoardSection(title="Terrain", assets=tuple(assets)),) if assets else (),
        reviewed_assets=tuple(assets),
        warnings=(),
        sources_used=("Library of Congress",),
    )


def test_thumbnails_are_copied_next_to_the_web_app(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    source = cache / "79692907.gif"
    source.write_bytes(b"GIF89a")
    asset_dir = tmp_path / "public" / "example-assets"

    thumbnails = copy_thumbnails(
        board(asset("loc:79692907", str(source))), asset_dir=asset_dir, cache_root=cache
    )

    assert thumbnails == {"loc:79692907": "/example-assets/loc-79692907.gif"}
    assert (asset_dir / "loc-79692907.gif").read_bytes() == b"GIF89a"


def test_thumbnails_outside_the_archive_cache_are_skipped(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    outside = tmp_path / "elsewhere.gif"
    outside.write_bytes(b"GIF89a")

    thumbnails = copy_thumbnails(
        board(asset("loc:1", str(outside))),
        asset_dir=tmp_path / "public",
        cache_root=cache,
    )

    assert thumbnails == {}


def test_a_missing_thumbnail_does_not_fail_the_capture(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()

    thumbnails = copy_thumbnails(
        board(asset("loc:1", str(cache / "gone.gif")), asset("loc:2", "")),
        asset_dir=tmp_path / "public",
        cache_root=cache,
    )

    assert thumbnails == {}


def test_only_selected_assets_are_copied(tmp_path: Path) -> None:
    """Reviewed assets include rejected candidates the board never shows."""
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "kept.gif").write_bytes(b"GIF89a")
    (cache / "rejected.gif").write_bytes(b"GIF89a")
    kept = asset("loc:kept", str(cache / "kept.gif"))
    rejected = asset("loc:rejected", str(cache / "rejected.gif"))
    with_rejection = board(kept).model_copy(update={"reviewed_assets": (kept, rejected)})

    thumbnails = copy_thumbnails(
        with_rejection, asset_dir=tmp_path / "public", cache_root=cache
    )

    assert set(thumbnails) == {"loc:kept"}


def test_snapshot_round_trips_through_the_loader(tmp_path: Path) -> None:
    example = ExampleBoard(
        session_id="example-9f3c1a4e",
        captured_at=datetime(2026, 9, 2, tzinfo=UTC),
        prompt="Crossing the Bitterroots.",
        board=board(),
        events=(
            ExampleEvent(
                sequence=1,
                event_type="plan_created",
                stage="planning",
                status="complete",
                message="Planned 6 requirement(s).",
            ),
        ),
    )
    path = tmp_path / "example-board.json"
    path.write_text(json.dumps(example.model_dump(mode="json")), encoding="utf-8")

    loaded = load_example(path)

    assert loaded is not None
    assert loaded.session_id == "example-9f3c1a4e"
    assert loaded.events[0].event_type == "plan_created"
    assert loaded.board.title == "Crossing the Bitterroots — September 1805"


def test_no_snapshot_is_not_an_error(tmp_path: Path) -> None:
    assert load_example(tmp_path / "absent.json") is None
