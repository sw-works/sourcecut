# Task 009 — Grafana / OpenTelemetry Observability

## Goal

Trace ingestion and research behavior end-to-end.

## Instrument

- extraction run;
- Gemini call;
- Pydantic validation;
- source-span validation;
- ClickHouse query/insert;
- ClickHouse MCP tool call and generated analytical query;
- ADK tool call;
- research session.

## Metrics

- passages processed;
- extraction success/failure;
- observations created;
- invalid spans;
- duplicate observations;
- extraction latency;
- ClickHouse query latency;
- MCP query latency, row count, failures, and authentication failures;
- separate direct ingestion/admin queries from MCP runtime queries.

## Acceptance criteria

One direct ingestion run and one MCP-backed evidence-research run are visible end-to-end in
Grafana, with their ClickHouse access paths distinguishable.
