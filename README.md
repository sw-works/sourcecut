# SourceCut

SourceCut is an agentic research producer for historically grounded film and documentary production.

The initial demo corpus is the Lewis & Clark Expedition (1804–1806). A filmmaker asks for a historically grounded visual research board; SourceCut investigates primary sources, derives evidence-backed production requirements, finds candidate media assets, verifies them, and produces a board where recommendations trace back to evidence.

## Hackathon architecture

- **Gemini + Google ADK**: research planning, interpretation, multimodal inspection, verification.
- **ClickHouse + official `mcp-clickhouse`**: primary-source evidence store and the mandatory
  runtime path for agent-led analytical retrieval and cross-author comparison.
- **Grafana + OpenTelemetry**: ingestion and agent observability.
- **FastAPI**: backend API.
- **Next.js + TypeScript**: frontend.
- **Google Cloud Run**: backend deployment target.

## Core invariant

Historical claims shown to users must be grounded in stored source passages. Gemini may guide search, but model memory is never treated as evidence.

## Start here

1. Read `AGENTS.md`.
2. Read `docs/hackathon-build/decisions.md`.
3. Implement tasks in numeric order from `tasks/`.
4. Do not begin serious media ingestion until Task 008 acceptance criteria pass.

Runtime research uses authenticated, read-only official `mcp-clickhouse`. Direct
`clickhouse-connect` access is reserved for ingestion, migrations, bulk loading, evaluation setup,
and administrative jobs.

## ClickHouse bootstrap

Install the locked project dependencies, configure the connection, and apply the schema:

```bash
uv sync
export CLICKHOUSE_HOST="localhost"
export CLICKHOUSE_PORT="8123"
export CLICKHOUSE_USERNAME="default"
export CLICKHOUSE_PASSWORD=""
export CLICKHOUSE_DATABASE="default"
export CLICKHOUSE_SECURE="false"
uv run sourcecut-db-bootstrap
```

For ClickHouse Cloud, set `CLICKHOUSE_SECURE=true`; when `CLICKHOUSE_PORT` is omitted,
secure connections default to port `8443`. The bootstrap command is idempotent and can be
run repeatedly. Applied migrations are recorded in `sourcecut_schema_migrations`, and the
command stops if an already-applied migration file has changed.
