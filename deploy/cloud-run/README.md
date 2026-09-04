# Cloud Run deployment

This deploys three services: the official ClickHouse MCP server, the FastAPI research API, and the
Astro web surface. The MCP service is publicly routable because Cloud Run IAM and MCP both use
the `Authorization` header, but the official server rejects requests without SourceCut's static
bearer token. ClickHouse access remains read-only at both the server and database-user layers.

## Prerequisites

- a GCP project with billing enabled and the `gcloud` CLI authenticated;
- Artifact Registry, Cloud Build, Cloud Run, Secret Manager, and Cloud Storage APIs enabled;
- the dedicated `sourcecut_mcp` ClickHouse user from the root README;
- five Secret Manager secrets: `sourcecut-clickhouse-password`,
  `sourcecut-runtime-clickhouse-password`, `sourcecut-mcp-token`, `sourcecut-gemini-key`, and
  `sourcecut-clickhouse-host`;
- a Cloud Storage bucket containing the local `data/archive-cache/loc` directory;
- a separate private Cloud Storage bucket for generated previs manifests and clips when Task 013
  is enabled.

The service account used by Cloud Run needs Secret Manager Secret Accessor on those secrets and
Storage Object Viewer on the archive bucket. Do not store the ClickHouse admin password in GCP for
these runtime services. Task 013 additionally needs Storage Object Admin on only the private previs
bucket so it can persist immutable briefs, provider operations, reviews, and generated clips, plus
Vertex AI User on the project for Gemini shot briefs, Veo generation, and clip review.

Set deployment coordinates in the shell:

```bash
export SOURCECUT_PROJECT="replace-with-gcp-project"
export SOURCECUT_REGION="us-west1"
export SOURCECUT_REPOSITORY="sourcecut"
export SOURCECUT_ARCHIVE_BUCKET="replace-with-private-bucket"
export SOURCECUT_PREVIS_BUCKET="replace-with-private-previs-bucket"
export SOURCECUT_VIDEO_MODEL="replace-with-enabled-veo-model"
export SOURCECUT_VIDEO_RATE="replace-with-current-usd-per-second-rate"
gcloud config set project "$SOURCECUT_PROJECT"
gcloud artifacts repositories create "$SOURCECUT_REPOSITORY" \
  --location "$SOURCECUT_REGION" --repository-format docker
```

Upload the immutable archive cache before deployment:

```bash
gcloud storage rsync --recursive data/archive-cache/loc \
  "gs://$SOURCECUT_ARCHIVE_BUCKET/loc"
```

## 1. Official ClickHouse MCP

Build and deploy the pinned official server image. Cloud Run terminates TLS; the container listens
on HTTP port 8080. The server connects onward to ClickHouse Cloud over verified HTTPS port 8443.

```bash
export SOURCECUT_REGISTRY="$SOURCECUT_REGION-docker.pkg.dev/$SOURCECUT_PROJECT/$SOURCECUT_REPOSITORY"
export SOURCECUT_MCP_IMAGE="$SOURCECUT_REGISTRY/mcp-clickhouse:0.4.1"
gcloud builds submit --config deploy/cloud-run/build-mcp.yaml \
  --substitutions "_IMAGE=$SOURCECUT_MCP_IMAGE" .
gcloud run deploy sourcecut-mcp --image "$SOURCECUT_MCP_IMAGE" \
  --region "$SOURCECUT_REGION" --allow-unauthenticated \
  --min 1 --max 1 --concurrency 20 --timeout 300 \
  --set-env-vars 'CLICKHOUSE_PORT=8443,CLICKHOUSE_SECURE=true,CLICKHOUSE_VERIFY=true,CLICKHOUSE_DATABASE=sourcecut,CLICKHOUSE_USER=sourcecut_mcp,CLICKHOUSE_ALLOW_WRITE_ACCESS=false,CLICKHOUSE_ALLOW_DROP=false' \
  --set-secrets 'CLICKHOUSE_HOST=sourcecut-clickhouse-host:latest,CLICKHOUSE_PASSWORD=sourcecut-clickhouse-password:latest,CLICKHOUSE_MCP_AUTH_TOKEN=sourcecut-mcp-token:latest'
export SOURCECUT_MCP_URL="$(gcloud run services describe sourcecut-mcp --region "$SOURCECUT_REGION" --format 'value(status.url)')/mcp"
```

Verify that the public MCP path rejects an unauthenticated JSON-RPC request with HTTP 401. The
`/health` endpoint is intentionally public and should return `OK`.

```bash
curl "${SOURCECUT_MCP_URL%/mcp}/health"
curl -i -X POST "$SOURCECUT_MCP_URL" \
  -H 'content-type: application/json' \
  --data '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## 2. FastAPI research service

The API mounts the private archive bucket at the exact path stored in ClickHouse. Research sessions
and agent events are durable in ClickHouse, so instances do not need session affinity.

```bash
export SOURCECUT_API_IMAGE="$SOURCECUT_REGISTRY/api:latest"
gcloud builds submit --config deploy/cloud-run/build-api.yaml \
  --substitutions "_IMAGE=$SOURCECUT_API_IMAGE" .
gcloud run deploy sourcecut-api --image "$SOURCECUT_API_IMAGE" \
  --region "$SOURCECUT_REGION" --allow-unauthenticated \
  --min 1 --max 3 --concurrency 20 --timeout 300 \
  --set-env-vars "CLICKHOUSE_MCP_URL=$SOURCECUT_MCP_URL,CLICKHOUSE_PORT=8443,CLICKHOUSE_SECURE=true,CLICKHOUSE_DATABASE=sourcecut,CLICKHOUSE_USERNAME=sourcecut_runtime,SOURCECUT_VIDEO_ENABLED=true,SOURCECUT_VIDEO_MODEL=$SOURCECUT_VIDEO_MODEL,SOURCECUT_VIDEO_STORAGE_URI=gs://$SOURCECUT_PREVIS_BUCKET/previs,SOURCECUT_VIDEO_ESTIMATED_COST_PER_SECOND_USD=$SOURCECUT_VIDEO_RATE,SOURCECUT_VIDEO_MAX_DURATION_SECONDS=8,SOURCECUT_VIDEO_MAX_GENERATIONS_PER_BRIEF=2,SOURCECUT_VIDEO_MAX_ESTIMATED_COST_USD=10,GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=$SOURCECUT_PROJECT,GOOGLE_CLOUD_LOCATION=global" \
  --set-secrets 'CLICKHOUSE_HOST=sourcecut-clickhouse-host:latest,CLICKHOUSE_PASSWORD=sourcecut-runtime-clickhouse-password:latest,CLICKHOUSE_MCP_AUTH_TOKEN=sourcecut-mcp-token:latest,GEMINI_API_KEY=sourcecut-gemini-key:latest' \
  --add-volume "name=archive,type=cloud-storage,bucket=$SOURCECUT_ARCHIVE_BUCKET" \
  --add-volume-mount 'volume=archive,mount-path=/app/data/archive-cache/loc'
export SOURCECUT_API_URL="$(gcloud run services describe sourcecut-api --region "$SOURCECUT_REGION" --format 'value(status.url)')"
curl "$SOURCECUT_API_URL/healthz"
```

## 3. Astro demo

The browser talks to a same-origin Astro endpoint, which streams the API response without exposing
an internal build-time address. `SOURCECUT_API_URL` is read by the server at runtime.

```bash
export SOURCECUT_WEB_IMAGE="$SOURCECUT_REGISTRY/web:latest"
gcloud builds submit --tag "$SOURCECUT_WEB_IMAGE" apps/web
gcloud run deploy sourcecut-web --image "$SOURCECUT_WEB_IMAGE" \
  --region "$SOURCECUT_REGION" --allow-unauthenticated \
  --min 1 --max 2 --concurrency 40 --timeout 300 \
  --set-env-vars "SOURCECUT_API_URL=$SOURCECUT_API_URL"
export SOURCECUT_WEB_URL="$(gcloud run services describe sourcecut-web --region "$SOURCECUT_REGION" --format 'value(status.url)')"
```

Open `$SOURCECUT_WEB_URL` and run the canonical Bitterroot prompt from
`tasks/012-web-demo.md`.
Repeat it at least twice before recording. Confirm the timeline names ClickHouse MCP, all six
evidence requirements expand to exact source excerpts, all 18 assets load, and an asset drill-down
shows rights, confidence, historical relationship, passage IDs, and source quotes.

The API runtime also needs a dedicated ClickHouse operational writer restricted to `INSERT` and
`SELECT` on `research_sessions`, `research_events`, `research_stage_stats`, and
`term_expansions`, plus `SELECT` on `research_stage_stats_mv`; provide those credentials through
the standard `CLICKHOUSE_*` environment variables. The MCP credential remains read-only and
separate.

`term_expansions` is on that list because vocabulary memory (ADR-021) writes back the search
terms a coverage round proved productive. It is curated reference data and never evidence, so the
runtime writer still touches no evidence table. Omitting the grant does not fail a board — the
write is an optimization and is caught — but every gap round then reports `memory_write_failed`. A static bearer token is suitable for this internal hackathon service; the
official server recommends an OIDC provider for broader production exposure.
