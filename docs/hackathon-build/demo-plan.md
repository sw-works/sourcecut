# Demo video plan

Submission requirement: **three minutes or less**, publicly visible on YouTube or
Vimeo, English or English subtitles. Target run time **2:50**, so a late edit
cannot push it over.

Everything below is filmed from the running application. Numbers quoted in the
narration were checked against the database on 2026-09-06: 14,685 trusted
observations over 2,366 passages, three journal keepers (Lewis, Clark, Gass),
22 catalogued archive references.

## The one decision to make first

A live run currently looks worse on camera than it is: events reach ClickHouse
while the run works, but the browser's timeline receives almost nothing until
the run finishes (see `docs/demo/README.md`). Three ways to film around it, best
first:

1. **Fix it, then film.** Timebox it — `py-spy dump` against the API mid-run to
   find what holds the GIL. This is the highest-value fix left: it is the demo's
   central image and a real product defect.
2. **Split screen.** Browser on the left, a terminal on the right tailing the
   events table as they land. The trace still ticks on camera, and it puts
   ClickHouse on screen doing the work.
   ```sql
   SELECT occurred_at, event_type, stage, message
   FROM research_events WHERE session_id = '<id>' ORDER BY occurred_at
   ```
3. **Jump cut.** Cut the dead stretch with an on-screen `elapsed 00:38` label so
   the cut is visible. Nothing is faked — the run is real and its output is
   whatever it produced.

## Shot list

| # | Time | On screen | Narration |
|---|---|---|---|
| 1 | 0:00–0:12 | Landing page, Clark's 1814 track map | "A production designer needs to know what the Lewis and Clark expedition actually looked like on a given day. The journals say — but they are 2,300 passages across three diarists." |
| 2 | 0:12–0:28 | Type the brief, press Research | "You ask for a scene the way you'd ask an art department." Read the brief aloud as it types. |
| 3 | 0:28–0:50 | Trace panel in the main column; insert `p1-planning.png` | "The model plans: which stretch of the expedition, which requirements, and the period words to search for. It picks a curated window — it never invents a date range." |
| 4 | 0:50–1:15 | Trace rows with `run_query` and row counts; the SQL at the bottom of the drawer | "Retrieval runs as read-only SQL through the official ClickHouse MCP server." Then the row-policy proof (command below): "the research role cannot see an unvalidated row at all." |
| 5 | 1:15–1:40 | `coverage_evaluated` → `gap_replan` → `coverage_evaluated`; insert `p2-coverage-rounds.png` | "First pass leaves requirements unmet. It widens the vocabulary for exactly those, inside the same window, and goes again. Words that earn their keep are written back for later sessions." |
| 6 | 1:40–2:05 | Board arrives. Evidence timeline, then open one requirement | "Every day of the window, and how many of the requirements the journals corroborate on it." Click a passage: "verbatim, with the character offsets it came from, and which of the three wrote it." |
| 7 | 2:05–2:20 | Archive references column; open one | "Library of Congress references, with item-level rights checked before anything is shown." |
| 8 | 2:20–2:35 | The disabled `unmet` tab on Great Falls | "The iron-frame boat is in the history and not in this corpus's vocabulary. It says so and stops. That is the useful answer." |
| 9 | 2:35–2:48 | Cut across the four boards' requirement rows | "A different brief plans different work: people and places at Lemhi Pass, equipment and hauling at the Great Falls." |
| 10 | 2:48–2:56 | Landing page, URL card | "SourceCut. Scene research from the journals, with the evidence attached." |

## Row-policy proof (shot 4)

Run as the MCP user while the board is on screen. It returns nothing, because
the row policy hides unvalidated rows from that role — not because the query is
filtered.

```bash
uv run --env-file .env.mcp.local python -c "
from sourcecut_api.db.client import get_clickhouse_client
print(get_clickhouse_client().query(
  'SELECT count() FROM observations WHERE NOT trusted').result_rows)"
```

Keep it to five seconds. It is one line of proof, not a segment.

## Before filming

- **Wake ClickHouse Cloud first.** After an idle period the first connection
  fails for a minute or two while the service resumes. Run the preflight and
  wait for `OK` before you start recording anything.
- Start the three processes (commands in `docs/demo/README.md`). The API needs
  `.env.admin.local` alongside the MCP and Gemini environments or every session
  fails on its first write.
- Rehearse the brief once end to end; a warm run is faster than a cold one.
- Browser at 1512×950, no bookmark bar, no extensions, 2× display.
- Have `docs/demo/shots/` open as fallback: if a live run fails on camera, the
  stills carry shots 6–9 without any loss of truth.

## Rules for what goes in

- Nothing on screen that a real run did not produce. If a run fails while
  filming, run it again — do not cut in a board from a different session and
  narrate it as this one.
- No claim in the narration that the artefacts on screen do not support.
- State what it does; do not argue with an imagined sceptic. The methodology
  belongs in the README and the architecture page, not in the voice-over.

## Still open before submission

The video is one of several requirements. Also outstanding: the repository is
private and has no LICENSE, nothing is pushed, and there is no hosted URL —
Cloud Run is torn down. The video should show the hosted URL, so the deploy has
to come first.
