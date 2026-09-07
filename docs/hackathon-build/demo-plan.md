# Demo video plan

Submission requirement: **three minutes or less**, publicly visible on YouTube or
Vimeo, English or English subtitles. Rendered at **2:53**; the script refuses to
write a cut over 2:55, so a late edit cannot push it past the limit.

**Cut from stills, not from a live screen recording.** Every frame is a real run
that was captured and committed, plus the architecture diagrams. Nothing is
staged and nothing waits on a service being up while the camera rolls. The
stills are 2x (3024x1900), so a dense one can be cropped to the region a line is
about and still arrive sharp at 1080p.

**Name the sources, not one kind of source.** The opening says what people
wrote at the time — diaries, letters, poems — because the shot two beats later
claims the pipeline takes any of them. An opening that says only "diaries"
un-says that claim before it is made.

**Plain words, no film vocabulary.** The audience is a judging panel, not an art
department, so the narration says diaries, quotes and dates rather than period
accuracy, briefs and provenance. A viewer who leaves after twenty seconds should
still be able to say what the problem is and what the tool does about it.

**The pipeline is the claim, not the corpus.** Shot 2 says the five steps take
any collection of primary sources; shot 16 is that claim being kept, on a poem
with no dates. Keep the pair — one asserts and the other demonstrates, and
neither works alone. What is shared is the five stages, the retrieval path and
the evidence rules; a corpus can still bring its own surfaces on top, so do not
say a new corpus is only a config entry.

**Narrated, and captioned.** The voice is Gemini TTS on Vertex AI, rendered by
`docs/demo/video.mjs` from the `vo` line of each shot; the captions stay burned
in, because a judging page often plays muted. They sit above the still, not
over it. Each shot is held for at least as
long as its line takes to speak, plus a beat at each end.

**One spotlight per shot.** Where a line points at something specific, the
frame dims and that rectangle stays lit inside a gold rule, so the narration and
the eye land on the same pixels. Rectangles are normalized to the source image
and live next to the shot in the script.

Numbers on screen, checked 2026-09-06: **14,685 trusted observations over 2,366
passages**, three journal keepers (Lewis, Clark, Gass), 22 catalogued archive
references, five curated windows.

Assets: `docs/demo/shots/*.png` (36 stills, table in `docs/demo/README.md`) and
`docs/diagrams/*.png`.

## The cut

| # | Time | Asset | On screen | Narration |
|---|---|---|---|---|
| 1 | 0:00-0:16 | `01-landing-hero` | Landing hero; headline, lede and capability chips lit | "Getting the past right means small things: the food, the tools, the weather that day. The answers sit in what people wrote at the time — diaries, letters, poems. SourceCut finds them, and shows the lines." |
| 2 | 0:16-0:29 | `03-corpus-cards` | Both corpus cards; the figure rows lit | "The pipeline is not built around diaries. Any collection of primary sources runs the same five steps, and the two loaded here were picked because they are nothing alike." |
| 3 | 0:29-0:39 | `05-brief-typed` | Dashboard cropped to the brief; the typed brief lit | "Type what your scene needs, in ordinary words. The answer is built only from what the diaries say." |
| 4 | 0:39-0:50 | `p1-planning.png` | Diagram | "Gemini turns that into a plan: which dates to search, and which old spellings to try." |
| 5 | 0:50-0:59 | `41-trace-plan` | Trace cropped to rows 01-03; the coverage row lit | "A real run: five things to find, over six weeks in 1805. The first search finds none." |
| 6 | 0:59-1:09 | `p2-coverage-rounds.png` | Diagram | "Each item has its own test for being found, so the tool knows which ones are still missing." |
| 7 | 1:09-1:19 | `43-trace-gap-replan` | Same trace, cropped to the gap replan; the vocabulary chips lit | "So it tries the words people wrote in 1805 — ironboat, sward, vapour — and finds four of the five." |
| 8 | 1:19-1:31 | `p3-specialist-agents.png` | Diagram | "Three agents on Google's Agent Development Kit: one plans, one searches, one checks. Only the searcher touches the database." |
| 9 | 1:31-1:42 | `45-trace-sql` | The statement, full width | "Every search is read-only SQL through ClickHouse's own MCP server. The agent can read the texts and nothing else." |
| 10 | 1:42-1:53 | `01-system-topology.png` | Diagram | "The texts, the search index and a log of every step all live in ClickHouse." |
| 11 | 1:53-2:01 | `13-timeline-date-held` | Board cropped to the timeline; the two-band strip lit | "The result opens on a calendar: every day, and how much of your scene the diaries back up." |
| 12 | 2:01-2:10 | `21-requirement-panel` | Extracts and matrix; the author-by-day matrix lit | "Open an item to read the quotes, and see which of the three men wrote it, on which day." |
| 13 | 2:10-2:18 | `24-passage-span` | The stored passage; the highlighted span and the SPAN card lit | "Click a quote for the whole diary entry, with the quoted words marked. Nothing is paraphrased." |
| 14 | 2:18-2:25 | `31-reference-rights` | The reference drawer; catalogue number and rights lit | "Old pictures come with their source, their catalogue number, and whether you can use them." |
| 15 | 2:25-2:34 | `50-unmet-requirement` | The disabled tab, `no passage` | "When the diaries say nothing, it says so. The iron boat is in the history books, not in these three diaries." |
| 16 | 2:34-2:47 | `06-project-odyssey` | Odyssey dashboard; the five-stage strip and heading lit | "Here is that on a poem. The Odyssey has no dates, so it is searched by book and line instead — same five steps, same evidence rules." |
| 17 | 2:47-2:53 | `02-landing-full` | The shelf, then the URL card | "SourceCut. Scene research from the original sources, with the proof attached." |

Rendered length 2:53. The table is the plan; `docs/demo/video.mjs` is the
same cut as something that runs, and it is the copy to trust on timing.

## Editing notes

- One move per still: a hold. These frames are a trace, a matrix, a diagram --
  a moving frame is a frame nobody finishes reading.
- Crop to the region the line is about rather than showing the whole page small.
  Shots 5 and 7 are the same still at two crops; they cut, they do not zoom.
- Hold every diagram long enough to finish reading it. They are dense, and a
  viewer who cannot finish one remembers nothing from it.
- The caption sits at the top and the still takes the rest of the frame: the
  line is read first, then the eye drops into the picture it describes. The band
  is measured from the tallest caption in the cut and applied to all of them, so
  the still never shifts position between shots.
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

The model's pace wanders between takes — the same line has come back at 1.8 and
at 4.7 words a second. Slow eats the three-minute budget; fast sounds hurried
over a frame someone is still reading. Each line is trimmed of its own leading
and trailing silence and then spoken until a take lands between 2.1 and 3.1
words a second, keeping whichever take is closest to 2.5. The rendered table
prints the pace of every line.

Pass `--url` once the hosted deployment exists: the closing card's subtitle is
that address, and it renders empty without it.
