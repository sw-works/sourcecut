# Demo stills

Screenshots for the submission video, taken from the running application by
`shots.mjs`. Nothing here is a mockup: the live-session frames are a real brief
running against ClickHouse Cloud through the MCP server, photographed while it
worked.

Regenerate:

```bash
# one terminal each
uv run --no-project --env-file .env.mcp.local --with mcp-clickhouse --python 3.10 mcp-clickhouse
uv run --env-file .env.mcp.local --env-file .env.gemini.local --env-file .env.admin.local \
  python -m sourcecut_api.main
npm --prefix apps/web run build && (cd apps/web && node ./dist/server/entry.mjs)

node docs/demo/shots.mjs http://127.0.0.1:3000
```

The API needs `.env.admin.local` as well as the MCP environment: sessions and
timeline events are written with the runtime writer's credentials, and without
them every session fails on its first write.

| Still | What it shows |
|---|---|
| `01-landing-hero` | The landing page: the corpus named, Clark's track map, the brief box. |
| `02-landing-full` | The whole landing page, including the captured boards. |
| `03-board-top` | A captured board: the day-by-day evidence timeline over the plan's window. |
| `04-board-full` | The same board end to end — survey cards, requirement tabs, drill-down. |
| `05-requirement-tabs` | The requirement row, including the one the corpus could not defend (disabled, marked "no passage"). |
| `06-requirement-evidence` | One requirement opened: verbatim passages, the author agreement matrix, the reviewed archive references. |
| `07-trace-drawer` | The execution trace drawer, with the last statement that went through mcp-clickhouse. |
| `08-live-NN-*` | A live session mid-run. The trace holds the main column while there is no board. Each file name records how many steps had arrived. |
| `11-live-complete` | The same session once the board replaced the trace panel. |
| `12-live-complete-full` | That board end to end. |
| `13-phone-board` | A captured board at 390px. |

## Known issue in the live frames

The live-session stills show one or two steps, not the fifteen the run records.
Events reach ClickHouse while the run works — a separate reader watching the
table sees them arrive — but a held SSE connection receives almost nothing until
the run finishes, and while a session is building, plain `GET /api/research/{id}`
requests time out too. The API is starving its own event loop during a build.

Two changes in this pass narrowed it and neither closed it: the board build now
runs on its own loop in a worker thread, and the session repository hands each
thread its own ClickHouse client instead of serialising every caller through one
client behind a lock. Next step is to profile the build thread (py-spy dump
against the API while a session runs) for work that holds the GIL.

Until that is fixed, the live frames are honest but undersell the trace; the
drawer frame (`07`) shows the full event list from a captured run.
