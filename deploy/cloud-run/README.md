# Cloud Run deployment

This deploys three services: the official ClickHouse MCP server, the FastAPI research API, and the
Astro web surface. The MCP service is publicly routable because Cloud Run IAM and MCP both use
the `Authorization` header, but the official server rejects requests without SourceCut's static
bearer token. ClickHouse access remains read-only at both the server and database-user layers.

## Prerequisites

- a GCP project with billing enabled and the `gcloud` CLI authenticated;
- Artifact Registry, Cloud Build, Cloud Run, Secret Manager, and Cloud Storage APIs enabled;
- the dedicated `sourcecut_mcp` ClickHouse user from the root README;
- four Secret Manager secrets: `sourcecut-clickhouse-password`,
  `sourcecut-runtime-clickhouse-password`, `sourcecut-mcp-token`, and
  `sourcecut-clickhouse-host`;
- the Vertex AI API enabled on the project (`gcloud services enable aiplatform.googleapis.com`);
- a Cloud Storage bucket containing the local `data/archive-cache/loc` directory.

The service account used by Cloud Run needs Secret Manager Secret Accessor on those secrets,
Storage Object Viewer on the archive bucket, and Vertex AI User. Gemini is reached through Vertex
AI with the service account's own credentials, so the deployed services carry no model API key at
all — `sourcecut-gemini-key` is only for a laptop or a CI job, where a key is easier than
application default credentials. Do not store the ClickHouse admin password in GCP for
these runtime services.

Set deployment coordinates in the shell:

```bash
export SOURCECUT_PROJECT="replace-with-gcp-project"
export SOURCECUT_REGION="us-west1"
export SOURCECUT_REPOSITORY="sourcecut"
export SOURCECUT_ARCHIVE_BUCKET="replace-with-private-bucket"
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
  --min 0 --max 1 --concurrency 20 --timeout 300 \
  --set-env-vars 'CLICKHOUSE_PORT=8443,CLICKHOUSE_SECURE=true,CLICKHOUSE_VERIFY=true,CLICKHOUSE_DATABASE=sourcecut,CLICKHOUSE_USER=sourcecut_mcp,CLICKHOUSE_ALLOW_WRITE_ACCESS=false,CLICKHOUSE_ALLOW_DROP=false,CLICKHOUSE_MCP_QUERY_TIMEOUT=55,CLICKHOUSE_SEND_RECEIVE_TIMEOUT=55,CLICKHOUSE_CONNECT_TIMEOUT=20' \
  --set-secrets 'CLICKHOUSE_HOST=sourcecut-clickhouse-host:latest,CLICKHOUSE_PASSWORD=sourcecut-clickhouse-password:latest,CLICKHOUSE_MCP_AUTH_TOKEN=sourcecut-mcp-token:latest'
export SOURCECUT_MCP_URL="$(gcloud run services describe sourcecut-mcp --region "$SOURCECUT_REGION" --format 'value(status.url)')/mcp"
```

The query timeout is set explicitly because the server defaults to 30 seconds, which is not
enough for a cold start against the full corpus: capturing the Lemhi board failed with
`Query timed out after 30 seconds` once the corpus reached ~14,600 observations. 55 seconds
sits under the API's own `CLICKHOUSE_MCP_CLIENT_TIMEOUT` ceiling of 60.

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
  --min 0 --max 3 --concurrency 20 --timeout 300 \
  --set-env-vars "CLICKHOUSE_MCP_URL=$SOURCECUT_MCP_URL,CLICKHOUSE_PORT=8443,CLICKHOUSE_SECURE=true,CLICKHOUSE_DATABASE=sourcecut,CLICKHOUSE_USERNAME=sourcecut_runtime,GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=$SOURCECUT_PROJECT,GOOGLE_CLOUD_LOCATION=$SOURCECUT_REGION" \
  --set-secrets 'CLICKHOUSE_HOST=sourcecut-clickhouse-host:latest,CLICKHOUSE_PASSWORD=sourcecut-runtime-clickhouse-password:latest,CLICKHOUSE_MCP_AUTH_TOKEN=sourcecut-mcp-token:latest' \
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
  --min 0 --max 2 --concurrency 40 --timeout 300 \
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

## Keeping it up for judging, cheaply

The hackathon asks for "a URL to the hosted Project for judging and testing", and
judging runs **10 September to 8 October 2026**, with winners announced on
13 October — about four weeks after the 9 September deadline (dates from the
Devpost API, 2026-09-07). The deployment stays up across that window, which is the one
case where the usual "stand it up for a run, then tear it down" rule does not apply.

All three services deploy with **`--min 0`**. That is the whole cost decision: an
instance floor of one bills continuously for four weeks whether or not anyone
visits, while a floor of zero bills per request and sits inside Cloud Run's
always-free monthly allowance for the traffic a judging window produces. The cost
is a cold start of a few seconds on the first request after an idle period, which
is the right trade for a page opened a handful of times over two weeks.

What still bills while nothing is happening: ClickHouse Cloud (idle or not, the
stored data is charged), the container images in Artifact Registry, and the
archive bucket. Cloud Run itself is not the line item.

**The site does not need the backend to be readable.** Every page is prerendered
from the committed examples — the landing shelf, both project dashboards, all five
captured boards and the Odyssey surfaces — so a visitor can read the boards, the
timeline, the requirements, the extracts and the rights panel with the API scaled
to zero and ClickHouse asleep. Three things do need it live: starting a new run,
the passage drill-down, and the execution-trace fetch.

ClickHouse Cloud suspends after a period of inactivity, and the first connection
after that is refused rather than held while the service resumes. Both clients
wait it out: a refusal whose text matches a suspended or resuming service is
retried three times, 1.5s then 3s then 6s, so a visitor opening the first
drill-down of the day gets a pause instead of an error. A real answer — a syntax
error, a permission denial, a row-limit breach — is raised at once, because
another attempt would only repeat it more slowly. `CLICKHOUSE_WAKE_RETRIES` and
`CLICKHOUSE_WAKE_BACKOFF_SECONDS` tune it; zero retries turns it off.

## Tearing it down

After judging closes, delete the three services. The images, secrets, bucket and
IAM grants survive, so bringing it back is a redeploy rather than a rebuild.

```bash
for service in sourcecut-web sourcecut-api sourcecut-mcp; do
  gcloud run services delete "$service" --region "$SOURCECUT_REGION" --quiet
done
```
