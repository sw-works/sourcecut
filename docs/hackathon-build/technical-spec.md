# Technical Specification

## High-level architecture

```text
Browser
  ↓
Next.js SourceCut Web App
  ↓
FastAPI Research API
  ↓
Gemini / Google ADK Research Orchestrator
  ↓
Typed Python tools
  ↓
Services / repositories
  ↓
clickhouse-connect
  ↓
ClickHouse Cloud

Backend + pipelines
  ↓
OpenTelemetry
  ↓
Grafana Cloud
```

## Agent architecture

Use one primary Research Orchestrator with explicit tools. Avoid unnecessary multi-agent complexity.

Suggested tool contracts:

- `search_historical_evidence(start_date, end_date, terms, categories)`
- `compare_primary_sources(start_date, end_date, terms)`
- `get_passage(passage_id)`
- `build_asset_requirements(evidence_summary)`
- `search_media_assets(requirements)`
- `inspect_media_asset(asset_id)`
- `verify_asset(asset_id, evidence_ids)`
- `assemble_board(session_id)`

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

Returns normalized metadata, rights, annotations, evidence links, and verification result.

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
│       ├── main.py
│       ├── routes/
│       ├── agents/
│       ├── tools/
│       ├── services/
│       ├── repositories/
│       ├── models/
│       └── telemetry/
├── pipelines/
│   ├── journals/
│   └── media/
├── schemas/
├── sql/
├── evals/
├── fixtures/
├── demo/
└── docs/
```

## Evaluation goals

- exact evidence-span validity: 100% for trusted observations;
- observation precision: target >=95% on reviewed sample;
- important-detail recall for demo concepts: target >=90%;
- parser correctness on sampled demo range: 100%;
- end-to-end demo run success: target >95%.
