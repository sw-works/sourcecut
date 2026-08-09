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
- ClickHouse is accessed through Python using `clickhouse-connect` / HTTP-native APIs.
- Do NOT introduce ClickHouse MCP.
- Gemini runs through Google ADK / Google GenAI tooling.
- The ADK agent never generates or executes arbitrary SQL.
- Agent tools call deterministic Python service/repository functions.
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
- Keep SQL in repository/service modules, not prompts or agent code.
- Make ingestion idempotent and resumable.
- Preserve raw provider payloads for all harvested media records.
- Add tests for parsers, evidence-span validation, idempotent migrations, and research query behavior.
- Avoid adding frameworks or infrastructure that are not necessary for the current task.

## Before marking a task complete

- Run relevant tests.
- Run lint/type checks if configured.
- Verify no architecture decision above was violated.
- Summarize changed files, commands/tests run, assumptions, and remaining risks.
