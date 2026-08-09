# Demo Plan

## Canonical prompt

> Build a historically grounded visual research board for the Corps of Discovery crossing the Bitterroot Mountains in September 1805. Focus on terrain, weather, transportation, food, clothing/equipment, and route geography.

## Three-minute flow

### 0:00–0:20 — Problem

Historical filmmakers can find many images; the difficult part is knowing which visual references are historically defensible.

### 0:20–0:40 — Request

Enter canonical prompt.

Show live progress steps rather than a spinner.

### 0:40–1:15 — Evidence investigation

Show Gemini/ADK invoking official ClickHouse MCP tools, including a visible analytical `run_query`
call that compares observations across Lewis and Clark, and ClickHouse returning multiple journal
passages/observations.

Display Evidence Matrix.

### 1:15–1:50 — Asset research

Show evidence-derived visual requirements, then candidate archival assets.

### 1:50–2:15 — Verification moment

Highlight one visually attractive but unsupported/interpretive asset and have SourceCut reject or downgrade it based on the evidence.

### 2:15–2:40 — Final board

Show polished sections and click an asset to trace:

`asset → recommendation → observation → journal passage → source`

### 2:40–2:50 — Grafana

Briefly show the research session as an OpenTelemetry trace/dashboard, with MCP calls distinguished
from direct ingestion queries.

### 2:50–3:00 — Close

> SourceCut turns historical evidence into creative decisions you can defend.

## Demo reliability rules

- Cache thumbnails and archive metadata.
- No critical dependency on external archive APIs during demo.
- Keep a known-good Bitterroot corpus.
- Preflight authenticated MCP connectivity and a read-only `list_tables`/`run_query` smoke test.
- Rehearse repeated runs.
- Store completed board results for debugging, but do not fake the live research flow.
