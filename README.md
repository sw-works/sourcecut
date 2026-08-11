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

## ClickHouse database users

Generate separate passwords for the admin and MCP users:

```bash
openssl rand -base64 32
openssl rand -base64 32
```

Open the ClickHouse Cloud SQL Console as the initial `default` user, replace both password
placeholders, and run:

```sql
CREATE DATABASE IF NOT EXISTS sourcecut;

CREATE ROLE IF NOT EXISTS sourcecut_admin_role;
GRANT SELECT, INSERT, ALTER, CREATE
ON sourcecut.*
TO sourcecut_admin_role;

CREATE USER IF NOT EXISTS sourcecut_admin
IDENTIFIED WITH sha256_password
BY 'REPLACE_WITH_ADMIN_PASSWORD';

GRANT sourcecut_admin_role TO sourcecut_admin;
ALTER USER sourcecut_admin DEFAULT ROLE sourcecut_admin_role;

CREATE ROLE IF NOT EXISTS sourcecut_mcp_role;
GRANT SELECT, SHOW DATABASES, SHOW TABLES
ON sourcecut.*
TO sourcecut_mcp_role;

ALTER ROLE sourcecut_mcp_role SETTINGS
    readonly = 1,
    max_execution_time = 30,
    max_memory_usage = 2000000000,
    max_rows_to_read = 100000000,
    max_bytes_to_read = 5000000000,
    max_threads = 4;

CREATE USER IF NOT EXISTS sourcecut_mcp
IDENTIFIED WITH sha256_password
BY 'REPLACE_WITH_MCP_PASSWORD';

GRANT sourcecut_mcp_role TO sourcecut_mcp;
ALTER USER sourcecut_mcp DEFAULT ROLE sourcecut_mcp_role;

CREATE ROW POLICY IF NOT EXISTS sourcecut_trusted_observations
ON sourcecut.observations FOR SELECT
USING trusted = true AND validation_status = 'valid'
TO sourcecut_mcp_role;

CREATE ROLE IF NOT EXISTS sourcecut_runtime_role;
GRANT SELECT, INSERT ON sourcecut.research_sessions TO sourcecut_runtime_role;
GRANT SELECT, INSERT ON sourcecut.research_events TO sourcecut_runtime_role;
GRANT SELECT, INSERT ON sourcecut.research_stage_stats TO sourcecut_runtime_role;

CREATE USER IF NOT EXISTS sourcecut_runtime
IDENTIFIED WITH sha256_password
BY 'REPLACE_WITH_RUNTIME_PASSWORD';

GRANT sourcecut_runtime_role TO sourcecut_runtime;
ALTER USER sourcecut_runtime DEFAULT ROLE sourcecut_runtime_role;
```

Store the admin credentials in `.env.admin.local` and the read-only MCP credentials in
`.env.mcp.local`. Never put the initial `default` user or an administrative password in the MCP
environment.

The row policy is the runtime evidence boundary: `sourcecut_mcp_role` can read only trusted,
span-validated observations. `sourcecut_runtime_role` can persist only operational session and
timeline data. The admin role remains unrestricted for ingestion and evaluation.

## ClickHouse MCP server

Start the official MCP server locally with the credentials and bearer token from
`.env.mcp.local`. `--no-project` keeps its Python 3.10 environment isolated from SourceCut's
Python 3.11+ application environment.

```bash
uv run \
  --no-project \
  --env-file .env.mcp.local \
  --with mcp-clickhouse \
  --python 3.10 \
  mcp-clickhouse
```

The MCP endpoint is `http://127.0.0.1:8000/mcp`. Verify ClickHouse connectivity from another
terminal:

```bash
curl http://127.0.0.1:8000/health
```

The expected response is `OK`. MCP clients must send `.env.mcp.local`'s
`CLICKHOUSE_MCP_AUTH_TOKEN` as an `Authorization: Bearer <token>` header. The health endpoint is
intentionally unauthenticated.

Register the running HTTP server with Codex once:

```bash
codex mcp add clickhouse \
  --url http://127.0.0.1:8000/mcp \
  --bearer-token-env-var CLICKHOUSE_MCP_AUTH_TOKEN
```

Set `CLICKHOUSE_MCP_AUTH_TOKEN` in the environment that launches Codex, then restart the Codex CLI,
IDE extension, or ChatGPT desktop app. Confirm the registration with `codex mcp get clickhouse` or
`/mcp`. Keep the token in `.env.mcp.local` or a secrets manager; do not add it directly to
`~/.codex/config.toml`.

## ADK runtime and MCP preflight

SourceCut's Google ADK research agent connects to the running server over authenticated Streamable
HTTP. The client defaults to `http://127.0.0.1:8000/mcp`; set `CLICKHOUSE_MCP_URL` to the HTTPS MCP
endpoint in hosted environments. `CLICKHOUSE_MCP_AUTH_TOKEN` is mandatory unless
`SOURCECUT_ALLOW_UNAUTHENTICATED_MCP=true` is explicitly set for a loopback-only development
server. The client timeout defaults to 60 seconds and can be changed with
`CLICKHOUSE_MCP_CLIENT_TIMEOUT`.

With the official server running, verify ADK tool discovery, live `list_tables` and `run_query`,
the read-only role, deterministic snow-passage lookup, and bearer-token rejection:

```bash
uv run --env-file .env.mcp.local sourcecut-mcp-preflight
```

Run the live integration test explicitly:

```bash
SOURCECUT_RUN_LIVE_MCP_TESTS=true \
  uv run --env-file .env.mcp.local \
  pytest -q tests/integration/test_clickhouse_mcp_live.py
```

After setting a real Gemini key in `.env.gemini.local`, run the visible ADK/MCP research trace:

```bash
uv run \
  --env-file .env.mcp.local \
  --env-file .env.gemini.local \
  sourcecut-research \
  "What production-relevant visual details are supported for the September 1805 Bitterroot crossing? Group cited evidence across authors."
```

The agent exposes only official MCP `list_databases`, `list_tables`, and `run_query` for analytical
retrieval. Its deterministic `get_passage(passage_id)` drill-down also uses a fixed, ID-validated
query through MCP, so direct repositories never receive model-generated SQL.

## Evidence-constrained previsualization

Each completed Research Board section can produce a typed Gemini shot brief and, when explicitly
enabled and approved, submit it to a configured Veo model. Generated clips are stored outside the
historical corpus and always display **AI-generated previsualization — not historical evidence**.

Safe defaults are in the ignored `.env.video.local` file. Brief creation may use the existing
Gemini key, but paid video generation remains blocked until all three changes are deliberate:

```dotenv
SOURCECUT_VIDEO_ENABLED=true
SOURCECUT_VIDEO_MODEL=replace-with-an-enabled-veo-model
SOURCECUT_VIDEO_ESTIMATED_COST_PER_SECOND_USD=replace-with-current-rate
```

Start the API with research and video configuration:

```bash
uv run \
  --env-file .env.mcp.local \
  --env-file .env.gemini.local \
  --env-file .env.video.local \
  python -m sourcecut_api.main
```

Creating a brief does not invoke Veo. The API requires the exact stored brief fingerprint and an
explicit approval before starting one paid job. Duplicate submissions return the same durable job,
and at most one user-approved corrected child clip is allowed. Local artifacts live under the
ignored `data/previs` directory; hosted deployments use a private Cloud Storage prefix.

The normal test suite uses fake providers and cannot spend video-generation credits. To run the
optional paid acceptance test, export a reviewed `ShotBrief` JSON first, confirm its displayed
estimate, and use the deliberately specific approval phrase:

```bash
SOURCECUT_RUN_LIVE_VIDEO_TESTS=true \
SOURCECUT_VIDEO_LIVE_COST_APPROVED=I_APPROVE_UP_TO_10_USD \
SOURCECUT_VIDEO_LIVE_BRIEF_PATH=/path/to/reviewed-shot-brief.json \
uv run \
  --env-file .env.gemini.local \
  --env-file .env.video.local \
  pytest -q -s tests/integration/test_veo_live.py
```

This test prints the estimated maximum charge before calling Veo. Do not run it until the configured
model, current per-second rate, quota, and brief have been reviewed.

## Grafana Cloud OpenTelemetry

Copy the OTLP environment variables from the Grafana Cloud **OpenTelemetry details** page into the
ignored `.env.grafana.local` file. Replace its endpoint and authorization placeholders, then set:

```dotenv
SOURCECUT_TELEMETRY_ENABLED=true
```

SourceCut exports traces and metrics over OTLP/HTTP only when that switch is enabled. SQL recorded
in spans has literal values redacted, and credentials are never added as span attributes.

Generate a direct-ingestion trace:

```bash
uv run \
  --env-file .env.admin.local \
  --env-file .env.grafana.local \
  sourcecut-load-gutenberg /path/to/pg8419.txt
```

Generate a separate MCP runtime trace:

```bash
uv run \
  --env-file .env.mcp.local \
  --env-file .env.gemini.local \
  --env-file .env.grafana.local \
  sourcecut-research \
  --session-id demo-bitterroot \
  "What visual details are supported for the September 1805 Bitterroot crossing?"
```

In Grafana Explore, filter SourceCut traces by `service.name=sourcecut`. The
`sourcecut.access.path` span attribute distinguishes `direct_ingestion`, `direct_admin`,
`mcp_runtime`, and `deterministic` work. MCP and ADK spans also include the tool name, duration,
returned row count, failure status, and research session ID. Relevant metrics use the
`sourcecut.*` namespace.

Agent-stage panels can query the ClickHouse rollup directly:

```sql
SELECT
    event_type,
    stage,
    countMerge(event_count) AS calls,
    avgMerge(average_duration) AS average_ms,
    quantilesMerge(0.5, 0.95)(duration_quantiles) AS p50_p95_ms
FROM sourcecut.research_stage_stats
GROUP BY event_type, stage
ORDER BY calls DESC;
```

## Gemini extraction

Create a Gemini API key in Google AI Studio and store it only in the ignored
`.env.gemini.local` file:

```dotenv
GEMINI_API_KEY=replace-with-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash
```

The model is configurable, while prompt and schema versions are recorded by the extraction result
and included with the passage hash in its deterministic idempotency key.

## Semantic retrieval

Embeddings are disabled by default. To backfill passage and media vectors through the offline admin
path, add these values to `.env.gemini.local` and run the command with both environments:

```dotenv
SOURCECUT_EMBEDDING_ENABLED=true
SOURCECUT_EMBEDDING_MODEL=gemini-embedding-2
SOURCECUT_EMBEDDING_DIMENSION=768
```

```bash
uv run --env-file .env.admin.local --env-file .env.gemini.local sourcecut-embed
```

The command is resumable and re-embeds stale rows after a model change. Runtime ranking sends float
arrays through official ClickHouse MCP `run_query`; a 768-dimension vector adds roughly 8–12 KB to
each query. Similarity only selects candidates—citations still come from exact stored passages.

## Gutenberg corpus load

After bootstrapping, load a cached copy of Project Gutenberg eBook #8419 through the offline admin
path:

```bash
uv run \
  --env-file .env.admin.local \
  sourcecut-load-gutenberg /path/to/pg8419.txt
```

The loader batches inserts and can be rerun safely. Deterministic IDs are resolved by
`ReplacingMergeTree`; readers use `FINAL` to expose one current version per logical row. Historical
dates are stored in ClickHouse as sortable `Int32` `YYYYMMDD` values because ClickHouse `Date` and
`Date32` do not cover 1804–1806.
