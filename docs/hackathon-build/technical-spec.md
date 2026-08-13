# Technical Specification

Evidence precision, recall, and span validity are measured by `sourcecut-eval` following
`evaluation-runbook.md`; model output is never used as its own gold standard.

## High-level architecture

```text
Browser
  ↓
Astro SourceCut Web App
  ├── prerendered public corpus routes
  └── React islands for research tools
  ↓
FastAPI Research API
  ↓
Gemini / Google ADK Research Orchestrator
  ↓
ClickHouse MCP client/tool adapter
  ↓
official mcp-clickhouse server (authenticated HTTP, read-only)
  ↓
ClickHouse HTTP interface
  ↓
ClickHouse Cloud

Offline ingestion / migrations / evaluation setup
  ↓
Python services / repositories
  ↓
clickhouse-connect
  ↓
ClickHouse Cloud

ADK + MCP + ingestion pipelines
  ↓
OpenTelemetry
  ↓
Grafana Cloud
```

## Agent architecture

Use one primary Research Orchestrator with explicit tools. Avoid unnecessary multi-agent complexity.

The user-facing research path must exercise the official `mcp-clickhouse` server. Give the ADK
agent the MCP tools `list_databases`, `list_tables`, and `run_query`, plus a concise SourceCut schema
and approved analytical query-pattern guide. `run_query` remains read-only at both the MCP server
and ClickHouse-user layers.

Runtime ClickHouse MCP tools:

- `list_databases()`
- `list_tables(database)`
- `run_query(query)`

Application-owned tools that remain deterministic:

- `get_passage(passage_id)`
- `build_asset_requirements(evidence_summary)`
- `inspect_media_asset(asset_id)`
- `verify_asset(asset_id, evidence_ids)`
- `assemble_board(session_id)`

The agent may generate analytical SQL only for `mcp-clickhouse.run_query`. Direct
`clickhouse-connect` repositories never accept model-generated SQL.

## ClickHouse MCP deployment

- Use the official `mcp-clickhouse` package/server.
- Connect to ClickHouse Cloud over its secure HTTP interface, normally port `8443`.
- Use a dedicated read-only ClickHouse user restricted to the SourceCut database/tables.
- Keep `CLICKHOUSE_ALLOW_WRITE_ACCESS=false` and do not enable destructive operations.
- Use HTTP transport with bearer-token or FastMCP identity-provider authentication when hosted.
- Terminate TLS before the hosted MCP endpoint or keep it on a private authenticated network.
- `CLICKHOUSE_MCP_AUTH_DISABLED=true` is allowed only for non-public local development.
- Record MCP tool name, query duration, row count, failure status, and research-session correlation
  in telemetry without recording credentials.

## Core API

### POST `/api/research`

Request:
```json
{
  "query": "Build a research board for the Bitterroot crossing in September 1805",
  "public_domain_only": true
}
```

Response:
```json
{
  "session_id": "uuid",
  "status": "started"
}
```

### GET `/api/research/{session_id}/events`

Server-Sent Events stream of agent/research progress.

### GET `/api/research/{session_id}`

Returns plan, evidence synthesis, board, status.

### GET `/api/passages/{passage_id}`

Deterministic source lookup; no Gemini call.

### GET `/api/assets/{asset_id}`

Returns normalized stored metadata and rights through a deterministic fixed ClickHouse MCP query;
unknown IDs return 404. `thumbnail_url`, when present, is served only from the confined archive
cache. Board-specific annotations, evidence links, and verification remain on
`/api/research/{session_id}/assets/{asset_id}` because the same asset can receive different
production assessments in different research sessions.

## Research board schema

```json
{
  "title": "Crossing the Bitterroots — September 1805",
  "summary": "...",
  "evidence_matrix": [],
  "sections": [
    {
      "title": "Environment",
      "assets": [
        {
          "asset_id": "...",
          "production_use": "...",
          "confidence": "HIGH",
          "why_selected": "...",
          "evidence_ids": ["..."]
        }
      ]
    }
  ],
  "warnings": [],
  "sources_used": []
}
```

## Repo structure

```text
sourcecut/
├── AGENTS.md
├── README.md
├── apps/
│   ├── web/
│   └── api/
│       └── sourcecut_api/
│           ├── main.py          # FastAPI routes and lifecycle
│           ├── agents/
│           ├── db/              # admin loaders and migrations
│           ├── integrations/    # ClickHouse MCP and Google video
│           ├── services/
│           ├── repositories/
│           ├── models/
│           ├── storage/
│           └── telemetry/
├── pipelines/
│   ├── embeddings/
│   ├── extraction/
│   ├── journals/
│   └── media/
├── sql/clickhouse/
├── fixtures/
├── deploy/
├── docs/
├── tasks/
└── tests/
```

- exact evidence-span validity: 100% for trusted observations;
- observation precision: target >=95% on reviewed sample;
- important-detail recall for demo concepts: target >=90%;
- parser correctness on sampled demo range: 100%;
- end-to-end demo run success: target >95%.
