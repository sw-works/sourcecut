# Task 009 — Grafana / OpenTelemetry Observability

## Goal

Trace ingestion and research behavior end-to-end.

## Instrument

- extraction run;
- Gemini call;
- Pydantic validation;
- source-span validation;
- ClickHouse query/insert;
- ADK tool call;
- research session.

## Metrics

- passages processed;
- extraction success/failure;
- observations created;
- invalid spans;
- duplicate observations;
- extraction latency;
- ClickHouse query latency.

## Acceptance criteria

One ingestion run and one evidence-research run are visible end-to-end in Grafana.
