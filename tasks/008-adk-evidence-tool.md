# Task 008 — ClickHouse MCP Runtime + ADK Historical Evidence

## Goal

Make the official `mcp-clickhouse` server the runtime evidence path for Gemini/ADK.

## MCP milestone — must pass first

- deploy/configure the official `mcp-clickhouse` server against the SourceCut ClickHouse cluster;
- use a dedicated least-privilege read-only ClickHouse user restricted to SourceCut tables;
- keep `CLICKHOUSE_ALLOW_WRITE_ACCESS=false`;
- connect the ADK runtime through an MCP client/tool adapter;
- use authenticated HTTP transport for hosted environments;
- configure the official server with `CLICKHOUSE_USER` (not the offline bootstrap's
  `CLICKHOUSE_USERNAME`), `CLICKHOUSE_SECURE=true`, and the Cloud HTTP endpoint/port;
- allow unauthenticated transport only for non-public local development;
- prove `list_tables` and `run_query` reach the actual SourceCut cluster.

## Required runtime tools

- `list_databases`
- `list_tables`
- `run_query`
- deterministic application `get_passage(passage_id)` for exact source drill-down

The agent may generate analytical SQL only through MCP `run_query`. Supply a concise SourceCut
schema and approved patterns for date/category/term filtering, passage joins, and cross-author
aggregation. Direct repositories must never execute model-generated SQL.

## Desired behavior

For a historical production question, the agent chooses ClickHouse MCP instead of answering from
model memory. Every historical claim still resolves to stored observations and passages.

## Acceptance tests

1. An integration test calls MCP `list_tables` and `run_query` against the actual SourceCut
   ClickHouse cluster and proves the runtime is read-only.
2. Ask for production-relevant visual details during the September 1805 Bitterroot crossing;
   observe an MCP `run_query` call and return cited evidence grouped across authors.
3. Ask whether wagons should be depicted; if no retrieved support exists, say the corpus does not
   support the claim.
4. Ask for the source behind a snow claim; resolve to deterministic passage lookup without another
   Gemini call.
5. Hosted MCP requests without valid authentication are rejected.

## Milestone gate

Do not consider the ADK research agent complete or start serious media ingestion until the MCP
milestone and agent tests pass reliably.
