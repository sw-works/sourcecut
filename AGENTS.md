# SourceCut Engineering Instructions

Read these before implementation:
- docs/hackathon-build/product-plan.md
- docs/hackathon-build/technical-spec.md
- docs/hackathon-build/data-acquisition.md
- docs/hackathon-build/pipeline-spec.md
- docs/hackathon-build/demo-plan.md
- docs/hackathon-build/decisions.md

## Critical architecture decisions

- Competition track: ClickHouse.
- User-facing runtime research must access ClickHouse through the official `mcp-clickhouse` server.
- Use `clickhouse-connect` directly only for offline ingestion, migrations, bulk loading,
  evaluation setup, and administrative jobs.
- Gemini runs through Google ADK / Google GenAI tooling.
- The ADK research agent may generate analytical SQL only through the official MCP
  `run_query` tool, using the documented SourceCut schema/query patterns.
- Deploy MCP with a dedicated least-privilege read-only ClickHouse user restricted to the
  SourceCut database/tables. Never use a default or administrative user outside local development.
- Hosted MCP uses authenticated HTTP transport. Authentication may be disabled only for local
  development on a non-public endpoint.
- Deterministic application tools remain responsible for exact passage lookup, validation, and
  other operations that must not depend on model-generated SQL.
- Grafana is supporting observability, not the primary partner integration.
- Historical claims must trace to stored source passages.
- AI-derived observations must contain exact source spans validated against the passage.
- Raw historical text is immutable.
- Do not generate fake historical evidence for scale testing.
- External archives are harvested and cached before demo; live research must not depend on LOC/Smithsonian/NPS uptime.

## Engineering priorities

1. Correctness and provenance.
2. Demo reliability.
3. Simple, boring infrastructure.
4. Observable behavior.
5. UI polish after the core evidence pipeline works.

## Coding expectations

- Prefer typed Python and Pydantic v2 models.
- Keep ingestion/admin SQL in repository/service modules. Runtime analytical SQL may be generated
  by the ADK agent only through read-only `mcp-clickhouse`, guided by documented query patterns.
- Make ingestion idempotent and resumable.
- Preserve raw provider payloads for all harvested media records.
- Add tests for parsers, evidence-span validation, idempotent migrations, and research query behavior.
- Avoid adding frameworks or infrastructure that are not necessary for the current task.

## Before marking a task complete

- Run relevant tests.
- Run lint/type checks if configured.
- Verify no architecture decision above was violated.
- Summarize changed files, commands/tests run, assumptions, and remaining risks.
