"""Build a corpus's pipeline state from what is actually in the database.

Every number here is counted through the read-only MCP role, so the page cannot
claim more evidence than the research path could cite. Nothing is estimated: a
step with no rows says so.
"""

from __future__ import annotations

from pathlib import Path

from sourcecut_api.corpora import CorpusRegistry
from sourcecut_api.models.corpus import CorpusDetail
from sourcecut_api.models.pipeline import (
    CorpusPipeline,
    PipelineStage,
    ResearchWindow,
    StageState,
)

EXAMPLE_DIR = Path("data/examples")


def _state(count: int, complete: int | None = None) -> StageState:
    if count <= 0:
        return StageState.EMPTY
    if complete is not None and count < complete:
        return StageState.PARTIAL
    return StageState.DONE


def _format_window(start: int, end: int) -> str:
    def spell(value: int) -> str:
        text = str(value)
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"

    return f"{spell(start)} → {spell(end)}"


def _lewis_and_clark_stages(counts: dict[str, int]) -> tuple[PipelineStage, ...]:
    return (
        PipelineStage(
            key="acquire",
            label="Acquire",
            state=StageState.DONE,
            summary=(
                "Two public-domain editions: Project Gutenberg 8419 and the 1904 Hosmer "
                "edition of Gass, from the Internet Archive."
            ),
            command="sourcecut-load-gutenberg · sourcecut-load-gass",
        ),
        PipelineStage(
            key="parse",
            label="Parse",
            state=_state(counts.get("entries", 0)),
            summary="Dated journal entries, one parser per edition's heading style.",
            counts=(
                ("entries", counts.get("entries", 0)),
                ("diarists", counts.get("authors", 0)),
            ),
        ),
        PipelineStage(
            key="segment",
            label="Segment",
            state=_state(counts.get("passages", 0)),
            summary="Entries cut into passages that carry their character offsets.",
            counts=(("passages", counts.get("passages", 0)),),
        ),
        PipelineStage(
            key="extract",
            label="Extract",
            state=_state(counts.get("observations", 0)),
            summary=(
                "Observations tied to the exact characters they came from, in the segments "
                "the research scopes name."
            ),
            counts=(
                ("observations", counts.get("observations", 0)),
                ("distinct terms", counts.get("terms", 0)),
            ),
            command="sourcecut-extract-passages --source-id … --start-date … --end-date …",
        ),
        PipelineStage(
            key="reference",
            label="Reference",
            state=_state(counts.get("media_assets", 0)),
            summary="Library of Congress items reviewed for item-level rights.",
            counts=(
                ("archive references", counts.get("media_assets", 0)),
                ("route waypoints", counts.get("route_waypoints", 0)),
            ),
        ),
    )


def _odyssey_stages(counts: dict[str, int]) -> tuple[PipelineStage, ...]:
    return (
        PipelineStage(
            key="acquire",
            label="Acquire",
            state=StageState.DONE,
            summary=(
                "Perseus TEI at a pinned revision: the Greek, Murray's translation, and "
                "Butler's, under CC BY-SA."
            ),
            command="sourcecut-load-odyssey --source-dir data/offline/odyssey",
        ),
        PipelineStage(
            key="parse",
            label="Parse",
            state=_state(counts.get("text_units", 0)),
            summary="Lines addressed by book and line, not by date — the poem has no calendar.",
            counts=(
                ("lines", counts.get("text_units", 0)),
                ("tokens", counts.get("tokens", 0)),
            ),
        ),
        PipelineStage(
            key="segment",
            label="Segment",
            state=_state(counts.get("passages", 0)),
            summary="Citable passages across the three versions.",
            counts=(("passages", counts.get("passages", 0)),),
        ),
        PipelineStage(
            key="extract",
            label="Extract",
            state=StageState.PARTIAL,
            summary=(
                "Annotation layers rather than observations: repeated formulae, narrative "
                "events in both reading and story order, and named places. The reviewed "
                "claim layer has not been populated."
            ),
            counts=(
                ("formula occurrences", counts.get("formula_occurrences", 0)),
                ("narrative events", counts.get("narrative_events", 0)),
                ("places", counts.get("places", 0)),
                ("reviewed claims", counts.get("claims", 0)),
            ),
        ),
        PipelineStage(
            key="reference",
            label="Reference",
            state=_state(counts.get("media_assets", 0)),
            summary=(
                "Route proposals are kept as competing hypotheses with disputed "
                "coordinates, never as one line on a map."
            ),
            counts=(
                ("route hypotheses", counts.get("route_hypotheses", 0)),
                ("visual references", counts.get("media_assets", 0)),
            ),
        ),
    )


def _lewis_and_clark_windows(
    scopes: tuple[object, ...], example_dir: Path
) -> tuple[ResearchWindow, ...]:
    windows: list[ResearchWindow] = []
    for scope in scopes:
        scope_id = getattr(scope, "scope_id", "")
        windows.append(
            ResearchWindow(
                scope_id=scope_id,
                title=getattr(scope, "title", scope_id),
                span=_format_window(
                    getattr(scope, "window_start", 0), getattr(scope, "window_end", 0)
                ),
                captured=(example_dir / f"{scope_id}.json").is_file(),
            )
        )
    return tuple(windows)


def build_corpus_pipeline(
    detail: CorpusDetail,
    counts: dict[str, int],
    *,
    scopes: tuple[object, ...] = (),
    example_dir: Path = EXAMPLE_DIR,
) -> CorpusPipeline:
    corpus = detail.corpus
    if corpus.corpus_id == "odyssey":
        stages = _odyssey_stages(counts)
        windows = (
            ResearchWindow(
                scope_id="odyssey-books",
                title="The poem, addressed by book and line",
                span="Books 1–24",
            ),
        )
    else:
        stages = _lewis_and_clark_stages(counts)
        windows = _lewis_and_clark_windows(scopes, example_dir)
    return CorpusPipeline(
        corpus_id=corpus.corpus_id,
        title=corpus.title,
        description=corpus.description,
        status=str(corpus.status),
        display_policy=str(corpus.display_policy),
        licenses=tuple(item.display_name for item in detail.licenses),
        sources=tuple(version.label for version in detail.versions),
        stages=stages,
        windows=windows,
        known_limitations=detail.known_limitations,
    )


def list_pipelines(
    registry: CorpusRegistry,
    counts_by_corpus: dict[str, dict[str, int]],
    *,
    scopes: tuple[object, ...] = (),
    example_dir: Path = EXAMPLE_DIR,
) -> tuple[CorpusPipeline, ...]:
    pipelines: list[CorpusPipeline] = []
    for record in registry.list():
        detail = registry.get(record.corpus_id)
        if detail is None:
            continue
        pipelines.append(
            build_corpus_pipeline(
                detail,
                counts_by_corpus.get(record.corpus_id, {}),
                scopes=scopes if record.corpus_id == "lewis-and-clark" else (),
                example_dir=example_dir,
            )
        )
    return tuple(pipelines)
