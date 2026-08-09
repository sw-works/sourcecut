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
```

Store the admin credentials in `.env.admin.local` and the read-only MCP credentials in
`.env.mcp.local`. Never put the initial `default` user or an administrative password in the MCP
environment.

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
