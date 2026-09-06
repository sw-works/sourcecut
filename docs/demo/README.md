# Demo stills

Screenshots for the submission video, taken from the running application by
`shots.mjs`. Nothing here is a mockup: every frame is a board produced by a real
run, captured and committed.

The video is cut from these rather than from a screen recording of a live
session, so the set has to carry every beat on its own. Shot list and narration:
`docs/hackathon-build/demo-plan.md`.

## Regenerating

The web app alone covers most of the set. Two frames — `23-passage-inspector`
and `24-passage-span` — fetch the surrounding passage, so they need the API and
the MCP server up as well.

```bash
# wake ClickHouse Cloud first: the first connection after an idle period fails
# while the service resumes
uv run --no-project --env-file .env.mcp.local --with mcp-clickhouse --python 3.10 mcp-clickhouse
uv run --env-file .env.mcp.local --env-file .env.admin.local python -m sourcecut_api.main

npm --prefix apps/web run build && (cd apps/web && node ./dist/server/entry.mjs)
node docs/demo/shots.mjs http://127.0.0.1:3000
```

The API needs `.env.admin.local` alongside the MCP environment: sessions and
events are written with the runtime writer's credentials.

## The set

| Still | What it shows |
|---|---|
| `01-landing-hero` | The landing page: the corpus named, Clark's 1814 track map. |
| `02-landing-full` | The whole landing page, captured boards included. |
| `03-landing-brief-typed` | A brief in the box, before it is run. |
| `10-board-top` · `11-board-full` | A captured board, first screen and end to end. |
| `12-evidence-timeline` | The day-by-day record over the plan's window. |
| `13-timeline-date-held` | One day held; the rest of the board follows it. |
| `14-survey-cards` | Brief, route reference, archive review. |
| `15-requirement-tabs` | The requirement row, met and unmet together. |
| `20-requirement-open` · `21-requirement-panel` | One requirement opened. |
| `22-agreement-matrix` | Which author wrote on which day. |
| `23-passage-inspector` | The stored passage behind one quotation, in the workspace. |
| `24-passage-span` | The same panel framed: highlight, character span, span-verified. |
| `30-archive-references` | The reviewed archive references for a requirement. |
| `31-reference-rights` | One reference: provider, catalogue id, rights status. |
| `40-trace-drawer` | The execution trace. |
| `41-trace-plan` | Plan, first MCP calls, coverage 0 of 5, the widened vocabulary, coverage 4 of 5 — the whole agentic loop in one frame. |
| `42-trace-mcp-calls` · `43-trace-gap-replan` · `44-trace-coverage` | The same trace framed on each step. |
| `45-trace-sql` | The last statement that went through mcp-clickhouse. |
| `50-unmet-requirement` | The requirement the corpus could not defend, disabled and marked. |
| `60/61/62-plan-*` | Requirement rows from three other boards: a different brief plans different work. |
| `60/61/62-plan-*-board` | Those boards in full. |
| `70-board-rail` | The captured boards, with coverage and citation counts. |
| `80/81-phone-board` | A board at 390px. |

## Not in the set: a live run

A live session is not filmed. Events reach ClickHouse while a run works, but a
held SSE connection receives almost nothing until the run finishes, and plain
`GET /api/research/{id}` requests time out during a build — the API starves its
own event loop. Two changes narrowed it without closing it: the board build now
runs on its own loop in a worker thread, and the session repository hands each
thread its own ClickHouse client rather than serialising every caller through
one client behind a lock. Next step is `py-spy dump` against the API mid-run to
find what holds the GIL.
