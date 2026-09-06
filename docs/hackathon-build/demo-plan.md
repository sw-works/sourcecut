# Demo video plan

Submission requirement: **three minutes or less**, publicly visible on YouTube or
Vimeo, English or English subtitles. Target **2:50**, so a late edit cannot push
it over.

**Cut from stills, not from a live screen recording.** Every frame is a real run
that was captured and committed, plus the architecture diagrams. Nothing is
staged and nothing waits on a service being up while the camera rolls. The
stills are 2× (3024×1900), so a 1080p timeline can push in on any of them
without softening.

Numbers in the narration, checked 2026-09-06: **14,685 trusted observations over
2,366 passages**, three journal keepers (Lewis, Clark, Gass), 22 catalogued
archive references, five curated windows.

Assets: `docs/demo/shots/*.png` (32 stills, table in `docs/demo/README.md`) and
`docs/diagrams/*.png`.

## The cut

| # | Time | Asset | On screen | Narration |
|---|---|---|---|---|
| 1 | 0:00–0:10 | `01-landing-hero` | Slow push in on Clark's 1814 track map | "A period film lives on detail. The Lewis and Clark journals hold it — 2,366 passages from three men who were there." |
| 2 | 0:10–0:20 | `03-landing-brief-typed` | The brief in the box, held | "Ask the way you'd brief an art department: the Great Falls portage, the gear they built, the ground they hauled across." |
| 3 | 0:20–0:32 | `10-board-top` | The finished board | "A minute later, a research board — every detail carrying the journal passage behind it." |
| 4 | 0:32–0:45 | `p1-planning.png` | Diagram | "The model plans the research: which stretch of the expedition, which requirements, and the period words to search for. The date window comes from a curated file of expedition segments." |
| 5 | 0:45–0:58 | `41-trace-plan` | Trace, top half | "Here is that plan on a real run — five requirements over the Great Falls window. The first pass comes back thin, and the system knows it: zero of five." |
| 6 | 0:58–1:12 | `p2-coverage-rounds.png` | Diagram | "Every requirement carries its own success criterion, so coverage is measured one requirement at a time." |
| 7 | 1:12–1:26 | `41-trace-plan` (lower crop, vocabulary chips) | Push in on `iron-boat · ironboat · iron-frame · skelet · sward · sleet` | "So it widens the vocabulary for exactly those requirements — period spellings a journal keeper would have written — searches the same window again, and reaches four of five." |
| 8 | 1:26–1:38 | `45-trace-sql` then `01-system-topology.png` | The statement, then the topology | "Retrieval runs as read-only SQL through the official ClickHouse MCP server, with a separate admin path for ingestion and migrations." |
| 9 | 1:38–1:50 | `12-evidence-timeline` → `13-timeline-date-held` | The band, then one day held | "The board opens on the record itself: every day of the window, and how much of the brief the journals corroborate on it. Hold a day and the whole board follows it." |
| 10 | 1:50–2:02 | `21-requirement-panel` → `22-agreement-matrix` | One requirement open | "Open a requirement for the verbatim extracts — and for who wrote what, on which day." |
| 11 | 2:02–2:18 | `24-passage-span` | Push in on the highlight, then the span card | "Click a quotation for the stored passage, unedited, with the exact characters the observation cites: 1,344 to 1,548, matched to the letter." |
| 12 | 2:18–2:28 | `31-reference-rights` | The reference inspector | "Every archive reference arrives with its provider, its catalogue id, and its rights status." |
| 13 | 2:28–2:38 | `50-unmet-requirement` | The disabled tab, `no passage` | "Where these journals are silent, the board says so. The iron-frame boat is in the history books, not in these three diaries — and you know that in a minute instead of a week." |
| 14 | 2:38–2:48 | `60-plan-bitterroot` → `61-plan-lemhi` → `62-plan-columbia` | Three requirement rows in quick succession | "A different brief plans different work: people and places at Lemhi Pass, villages and rapids on the Columbia." |
| 15 | 2:48–2:56 | `02-landing-full` | Pull back, URL card | "SourceCut. Scene research from the journals, with the evidence attached." |

## Editing notes

- One move per still: a slow push in, or a hold. No crossfades between diagram
  boxes — cut, or the eye loses the box it was reading.
- Shots 5 and 7 are the same still at two crops. Cut, don't zoom continuously;
  the second crop should land on the vocabulary chips already framed.
- Hold every diagram for at least twelve seconds. They are dense, and a viewer
  who cannot finish reading one remembers nothing from it.
- Burn in captions. The rules accept English audio, but a muted autoplay on a
  judging page is the realistic viewing condition.
- Colour: the app stills are dark and the diagrams are light. Put a one-beat
  black frame at each switch rather than letting the flash land on a word.

## What the diagrams are for

`p1-planning` and `p2-coverage-rounds` carry the agentic story — a plan the
application validates, and a bounded second round driven by scored coverage.
`01-system-topology` carries the ClickHouse story in one frame: read-only MCP at
runtime, a separate admin path for writes, row policies on the tables. Three
diagrams is the limit for three minutes; `p4-guardrails` and `p6-vocabulary-
memory` belong in the written submission, not the cut.

All eight diagrams were re-checked against the code on 2026-09-06. `01` and `02`
were stale — route and migration counts, and the planning-failure paths — and
were redrawn.

## Ground rules for the cut

- Every frame comes from a real run. Re-capture a board and re-take its still,
  so the narration and the frame always describe the same session.
- Each line of narration is carried by the frame under it.
- Say what it does, once, and move on. The methodology has its own home in the
  README and the architecture page, and it reads better there than in a
  voice-over.

## Regenerating the stills

Commands in `docs/demo/README.md`. Two things to know: wake ClickHouse Cloud
first (the first connection after an idle period fails while the service
resumes), and the passage drill-down needs the API and MCP server up, since that
panel fetches the surrounding passage.

## Still open before submission

The repository is private and has no LICENSE, nothing is pushed, and there is no
hosted URL — Cloud Run is torn down. Shot 15 shows a URL card, so the deploy has
to happen before the final render.
