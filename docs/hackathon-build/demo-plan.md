# Demo video plan

Submission requirement: **three minutes or less**, publicly visible on YouTube or
Vimeo, English or English subtitles. Target **2:50**, so a late edit cannot push
it over.

**Cut from stills, not from a live screen recording.** Every frame is a real run
that was captured and committed, plus the architecture diagrams. Nothing is
staged and nothing waits on a service being up while the camera rolls. The
stills are 2x (3024x1900), so a dense one can be cropped to the region a line is
about and still arrive sharp at 1080p.

**Narrated, and captioned.** The voice is Gemini TTS on Vertex AI, rendered by
`docs/demo/video.mjs` from the `vo` line of each shot; the captions stay burned
in, because a judging page often plays muted. Each shot is held for at least as
long as its line takes to speak, plus a beat at each end.

**One spotlight per shot.** Where a line points at something specific, the
frame dims and that rectangle stays lit inside a gold rule, so the narration and
the eye land on the same pixels. Rectangles are normalized to the source image
and live next to the shot in the script.

Numbers in the narration, checked 2026-09-06: **14,685 trusted observations over
2,366 passages**, three journal keepers (Lewis, Clark, Gass), 22 catalogued
archive references, five curated windows.

Assets: `docs/demo/shots/*.png` (36 stills, table in `docs/demo/README.md`) and
`docs/diagrams/*.png`.

## The cut

| # | Time | Asset | On screen | Narration |
|---|---|---|---|---|
| 1 | 0:00-0:12 | `01-landing-hero` | Landing hero; the headline, lede and capability chips lit | "A period film lives on detail. The Lewis and Clark journals hold it: 2,366 passages, from three men who were there." |
| 2 | 0:12-0:21 | `03-corpus-cards` | Both corpus cards; the figure rows lit | "Two corpora, one pipeline. The journals and the poem are researched the same way." |
| 3 | 0:21-0:29 | `05-brief-typed` | Project dashboard cropped to the brief; the typed brief lit | "Ask the way you would brief an art department. The Great Falls portage: the gear they built, the ground they hauled across, and the weather that hit them." |
| 4 | 0:29-0:40 | `p1-planning.png` | Diagram | "Gemini plans the research: which stretch of the expedition, which requirements, and which period words to search. The date window comes from a curated file of segments." |
| 5 | 0:40-0:49 | `41-trace-plan` | Trace cropped to rows 01-03; the coverage row lit | "Five requirements over the Great Falls window. The first pass comes back thin: zero of five." |
| 6 | 0:49-0:58 | `p2-coverage-rounds.png` | Diagram | "Every requirement carries its own success criterion, so coverage is measured one requirement at a time." |
| 7 | 0:58-1:09 | `43-trace-gap-replan` | Same trace, cropped to the gap replan; the vocabulary chips lit | "So it widens the vocabulary for exactly those requirements, reaching for period spellings, searches the same window again, and gets to four of five." |
| 8 | 1:09-1:25 | `p3-specialist-agents.png` | Diagram | "The agent runtime is Google's Agent Development Kit: planner, researcher and auditor in sequence, separated by what each can touch. Only the researcher holds the ClickHouse tools." |
| 9 | 1:25-1:38 | `45-trace-sql` | The statement, full width | "Retrieval is read-only SQL through the official ClickHouse MCP server: parametrized views for the window, vector search, and row policies on the tables." |
| 10 | 1:38-1:48 | `01-system-topology.png` | Diagram | "One read path at runtime, one write path for ingestion and migrations, and 133 migrations behind the schema they share." |
| 11 | 1:48-1:57 | `13-timeline-date-held` | Board cropped to the timeline; the two-band strip lit | "The board opens on the record itself. Every day of the window, and how much of the brief the journals corroborate on it." |
| 12 | 1:57-2:05 | `21-requirement-panel` | Extracts and matrix; the author-by-day matrix lit | "Open a requirement for the verbatim extracts, and for who wrote what, on which day." |
| 13 | 2:05-2:13 | `24-passage-span` | The stored passage; the highlighted span and the SPAN card lit | "Click a quotation and you get the stored passage, unedited, with the exact characters the observation cites: 1,344 to 1,548." |
| 14 | 2:13-2:22 | `31-reference-rights` | The reference drawer; catalogue id and rights lit | "Every archive reference arrives with its provider, its catalogue identifier, and its rights status." |
| 15 | 2:22-2:32 | `50-unmet-requirement` | The disabled tab, `no passage` | "Where these journals are silent, the board says so. The iron-frame boat is in the history books, but not in these three diaries." |
| 16 | 2:32-2:43 | `06-project-odyssey` | Odyssey dashboard; pipeline strip and heading lit | "A second corpus runs the same pipeline. A poem is read, not dated, so it is addressed by book and line." |
| 17 | 2:43-2:50 | `02-landing-full` | The shelf, then the URL card | "SourceCut. Scene research from the sources, with the evidence attached." |

Rendered length 2:50. The table is the plan; `docs/demo/video.mjs` is the
same cut as something that runs, and it is the copy to trust on timing.

## Editing notes

- One move per still: a hold. These frames are a trace, a matrix, a diagram --
  a moving frame is a frame nobody finishes reading.
- Crop to the region the line is about rather than showing the whole page small.
  Shots 5 and 7 are the same still at two crops; they cut, they do not zoom.
- Hold every diagram long enough to finish reading it. They are dense, and a
  viewer who cannot finish one remembers nothing from it.
- The still sits in the top plate and the caption owns the lower third, so
  nothing the narration points at can end up under the type.
- Colour: the app stills are dark and the diagrams are light. Both are matted on
  the app's own ground, so the switch lands on the mat, not on a word.

## What the diagrams are for

Four diagrams carry what no screenshot can.

`p1-planning` and `p2-coverage-rounds` are the agentic loop: a plan the
application validates before it reaches SQL, and a bounded second round driven
by scored coverage. `p3-specialist-agents` is the ADK runtime — three stages
separated by tool access, which is the part worth seeing, because the planner
having no tools is a fact about the graph rather than about the prompt.
`01-system-topology` puts the ClickHouse story in one frame: read-only MCP at
runtime, a separate admin path for writes, row policies on the tables.

**One boundary to hold.** The boards in every still come from the board path —
the Gemini planner and the MCP client directly. The ADK pipeline is a separate
runtime, reached from the CLI and `POST /api/research/agent`. Shot 8 describes
that runtime over its own diagram; it never claims the boards on screen were
produced by it.

`p4-guardrails`, `p5-self-consistency` and `p6-vocabulary-memory` belong in the
written submission, where a reader can take their time.

## Ground rules for the cut

- Every frame comes from a real run. Re-capture a board and re-take its still,
  so the narration and the frame always describe the same session.
- Each line of narration is carried by the frame under it.
- Say what it does, once, and move on. The methodology has its own home in the
  README and the architecture page, where someone checking will look for it.

## Regenerating the stills

Commands in `docs/demo/README.md`. Two things to know: wake ClickHouse Cloud
first (the first connection after an idle period fails while the service
resumes), and the passage drill-down needs the API and MCP server up, since that
panel fetches the surrounding passage.

## Still open before submission

The repository is private and has no LICENSE, nothing is pushed, and there is no
hosted URL — Cloud Run is torn down. Shot 15 shows a URL card, so the deploy has
to happen before the final render.

## Rendering the video

```sh
node docs/demo/video.mjs [--url https://…] [--out path.mp4] [--silent]
```

Needs ffmpeg, a global playwright, and `gcloud` logged in to a project with
Vertex AI enabled (`sourcecut-64338`, or `GOOGLE_CLOUD_PROJECT`). Narration is
synthesized once per line and cached by hash, so re-runs after an edit only
re-speak the lines that changed; `--silent` skips the voice entirely. The script
refuses to write a cut longer than 175 seconds.

Pass `--url` once the hosted deployment exists: the closing card's subtitle is
that address, and it renders empty without it.
