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
| 2 | 0:10–0:18 | `03-landing-brief-typed` | The brief in the box, held | "Ask the way you'd brief an art department: the Great Falls portage, the gear they built, the ground they hauled across." |
| 3 | 0:18–0:26 | `10-board-top` | The finished board | "A minute later, a research board — every detail carrying the journal passage behind it." |
| 4 | 0:26–0:39 | `p1-planning.png` | Diagram | "The model plans the research: which stretch of the expedition, which requirements, and the period words to search for. The date window comes from a curated file of expedition segments." |
| 5 | 0:39–0:50 | `41-trace-plan` | Trace, top half; hold on the row counts | "Here is that plan on a real run — five requirements over the Great Falls window. Two hundred rows back, and zero of five requirements met. Every step of the run is itself a row in ClickHouse, which is what this trace is reading back." |
| 6 | 0:50–1:02 | `p2-coverage-rounds.png` | Diagram | "Every requirement carries its own success criterion, so coverage is measured one requirement at a time." |
| 7 | 1:02–1:14 | `41-trace-plan` (lower crop, vocabulary chips) | Push in on `iron-boat · ironboat · iron-frame · skelet · sward · sleet` | "So it widens the vocabulary for exactly those requirements — period spellings a journal keeper would have written — searches the same window again, and reaches four of five." |
| 8 | 1:14–1:26 | `p3-specialist-agents.png` | Diagram | "The agent runtime is Google's ADK: a planner, a researcher and an auditor in sequence, separated by what each one can touch. Only the researcher holds the ClickHouse tools, and every query it sends passes the guardrail on its way out." |
| 9 | 1:26–1:38 | `45-trace-sql` | The statement, framed | "Retrieval is read-only SQL through the official ClickHouse MCP server — parametrized views for the date window, vector search over the passage embeddings, and row policies deciding what the research role can see." |
| 10 | 1:38–1:50 | `01-system-topology.png` | Diagram | "One read path at runtime, one write path for ingestion and migrations, and 133 migrations behind the schema they share." |
| 11 | 1:50–1:59 | `12-evidence-timeline` → `13-timeline-date-held` | The band, then one day held | "The board opens on the record itself: every day of the window, and how much of the brief the journals corroborate on it. Hold a day and the whole board follows it." |
| 12 | 1:59–2:10 | `21-requirement-panel` → `22-agreement-matrix` | One requirement open | "Open a requirement for the verbatim extracts — and for who wrote what, on which day." |
| 13 | 2:10–2:22 | `24-passage-span` | Push in on the highlight, then the span card | "Click a quotation for the stored passage, unedited, with the exact characters the observation cites: 1,344 to 1,548, matched to the letter." |
| 14 | 2:22–2:30 | `31-reference-rights` | The reference inspector | "Every archive reference arrives with its provider, its catalogue id, and its rights status." |
| 15 | 2:30–2:39 | `50-unmet-requirement` | The disabled tab, `no passage` | "Where these journals are silent, the board says so. The iron-frame boat is in the history books, not in these three diaries — and you know that in a minute instead of a week." |
| 16 | 2:39–2:45 | `60-plan-bitterroot` → `61-plan-lemhi` → `62-plan-columbia` | Three requirement rows in quick succession | "A different brief plans different work: people and places at Lemhi Pass, villages and rapids on the Columbia." |
| 17 | 2:45–2:50 | `02-landing-full` | Pull back, URL card | "SourceCut. Scene research from the journals, with the evidence attached." |

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
