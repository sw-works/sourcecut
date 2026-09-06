# Task 013 — Evidence-Constrained Previsualization

> **Withdrawn, 2026-09-05.** The feature was built and then removed in full:
> models, service, storage, API routes, the Veo and Gemini video integration,
> the web drawer, and its tests. Nothing in the hackathon rules asks for
> generated video, the ClickHouse track only requires runtime use of the
> official MCP server, and `product-plan.md` lists "generated historical
> reenactment imagery" among the things not to build. The spec is kept because
> it records why the evidence boundary was drawn where it was — the code is in
> the history, not the tree.

## Goal

Turn one verified Research Board section into a short AI-generated previsualization clip without
presenting generated imagery as historical evidence.

```text
ClickHouse MCP research → verified Research Board → Gemini Shot Brief → human approval
    → Veo generation → Gemini consistency review → optional corrected regeneration
```

SourceCut researches history first and only then imagines the shot. Generated media always remains
on the creative side of the evidence boundary.

## Prerequisites

- Task 011 produces a verified Research Board with exact passage citations and rights-filtered
  archive assets.
- Task 012 provides the web/API surface and a deployed authenticated ClickHouse MCP research path.
- A paid Google project or Gemini API account has access to a configured Veo model.
- The configured generated-media store is writable. Use an ignored local directory during
  development and a private Cloud Storage bucket when hosted.

## Architecture boundaries

- Keep all historical research on the existing `Google ADK → official mcp-clickhouse →
  ClickHouse Cloud` runtime path.
- Build the shot brief only from the completed board supplied by the application. Do not let the
  video workflow perform uncited historical research or silently add claims.
- Use the Google Gen AI SDK directly for Gemini structured output, Veo generation, operation
  polling, and Gemini video review. Veo is not a ClickHouse operation and does not go through MCP.
- Do not write generated clips, job state, or shot briefs into the historical-evidence tables.
- Persist generation artifacts separately and immutably. A regeneration creates a child job; it
  never overwrites its parent.
- Never describe a generated clip as evidence, archival footage, a reconstruction, or historically
  accurate. The required label is **AI-generated previsualization — not historical evidence**.

## Agent workflow

Use a prompt chain with an explicit human checkpoint and a producer–critic split:

1. **Shot-brief producer:** Gemini converts one board section into typed `ShotBrief` JSON.
2. **Deterministic guardrail:** application code validates citations, rights, strictness, limits,
   and unsupported additions before any paid request.
3. **Human approval:** the user reviews the brief, interpretive additions, reference images,
   estimated cost, duration, and model before selecting **Generate clip**.
4. **Video producer:** Veo receives only the approved brief and approved reference image inputs.
5. **Video critic:** a separate Gemini instruction/model context inspects the finished clip against
   the immutable approved brief and its evidence.
6. **Correction:** the user may request one corrected regeneration derived from the critic report.
   Never regenerate automatically.

The producer and critic must not share hidden reasoning or mutable prompt state. Their only shared
inputs are the stored shot brief, evidence references, generated clip, and explicit user controls.

## User experience

Add **Create Previs** to each populated Research Board section.

The setup panel includes:

- shot type: `Establishing shot`, `Travel shot`, `Camp scene`, or `Landscape plate`;
- evidence strictness: `Strict` or `Interpretive`, defaulting to `Strict`;
- duration and aspect ratio constrained to the configured model capabilities;
- selected public-domain visual references;
- supported visual details with passage and observation citations;
- excluded or unsupported details;
- interpretive additions, shown only when `Interpretive` is selected;
- current model, estimated maximum charge, and an explicit paid-generation confirmation.

After submission, show durable states: `queued`, `generating`, `reviewing`, `complete`, `failed`, or
`blocked`. The completed view contains the generated-content label, video player, approved shot
brief, evidence citations, model metadata, and historical-consistency report.

## Typed contracts

Define Pydantic v2 models for at least:

### `ShotBrief`

- `shot_brief_id`, `research_session_id`, `board_section_id`, and `board_fingerprint`;
- `shot_type`, `purpose`, `setting`, `action`, `composition`, `camera_motion`, and `ambience`;
- `strictness`, `duration_seconds`, `aspect_ratio`, and `generate_audio`;
- `supported_details`, where each detail has one or more `observation_ids` and `passage_ids`;
- `reference_asset_ids`, restricted to approved public-domain board assets;
- `interpretive_additions` and `excluded_details`;
- provider-ready positive and negative prompt fields;
- `producer_model`, `prompt_version`, and creation timestamp.

### `PrevisJob`

- `job_id`, `shot_brief_id`, `status`, and `parent_job_id` for correction runs;
- provider, model, provider-operation name, and immutable request fingerprint;
- estimated cost, generation count, timestamps, output URI, and safe error information;
- no API keys, bearer tokens, signed URLs, or provider credential material.

### `ConsistencyReport`

- overall result: `consistent`, `needs_review`, or `unsupported`;
- findings labeled `supported`, `interpretive`, or `unsupported`;
- each finding's visible detail, approximate time range, severity, rationale, and related evidence
  IDs;
- correction instructions that contain only observed problems and approved shot-brief details;
- critic model, prompt version, and review timestamp.

## Deterministic guardrails

- In `Strict` mode, reject any non-empty `interpretive_additions` list.
- Every positive historical detail must cite an observation and passage already present in the
  selected board section.
- Do not accept evidence text, asset metadata, or IDs supplied only by the browser; resolve them
  from the stored Research Board before approval and generation.
- Every reference image must have `rights_status=PUBLIC_DOMAIN` and an approved cached file.
- Treat maps and documents as references, not literal depictions of people, clothing, or terrain.
- Add unsupported details to the provider's negative-prompt field using its documented noun-phrase
  syntax rather than instructions such as “do not.”
- Reject modern objects, wagons, buildings, roads, clothing, weapons, or other specifics unless the
  selected board evidence supports them.
- Default to silent output for the first slice. Generated speech, narration, and historically
  specific sound are out of scope unless separately evidenced and approved.
- Enforce configurable duration, generation-count, and estimated-cost ceilings server-side.
- Require a fresh approval if the brief, model, duration, references, or estimated cost changes.
- Safety-filtered or failed generations consume no automatic retry. Show the safe provider error
  and let the user decide whether to revise the brief.

## Asynchronous execution and storage

- `POST /api/research/{session_id}/previs/briefs` creates and validates a draft brief without
  invoking Veo.
- `POST /api/previs/{shot_brief_id}/generate` requires the accepted brief fingerprint and explicit
  approval, starts the long-running Veo operation, persists its operation name, and returns `202`.
- `GET /api/previs/jobs/{job_id}` refreshes the provider operation, materializes a completed output,
  and returns current state. The web client polls this endpoint with bounded backoff.
- `POST /api/previs/jobs/{job_id}/review` starts or retrieves the Gemini consistency review.
- `POST /api/previs/jobs/{job_id}/correct` creates at most one approved child generation from the
  stored report.
- Store a manifest, approved brief, provider request metadata, output clip, and consistency report
  under an immutable per-job prefix such as `previs/{job_id}/`.
- The provider operation and persisted manifest are the source of truth; generation must continue
  safely if the browser disconnects or the API instance restarts.
- Use a filesystem storage adapter for local tests and development. Use Cloud Storage for hosted
  execution; do not rely on a Cloud Run container filesystem.

## Configuration

Add ignored local placeholders and hosted secrets/configuration for:

```dotenv
SOURCECUT_VIDEO_ENABLED=false
SOURCECUT_VIDEO_MODEL=replace-with-enabled-veo-model
SOURCECUT_VIDEO_REVIEW_MODEL=gemini-2.5-flash
SOURCECUT_VIDEO_STORAGE_URI=data/previs
SOURCECUT_VIDEO_MAX_DURATION_SECONDS=8
SOURCECUT_VIDEO_MAX_GENERATIONS_PER_BRIEF=2
SOURCECUT_VIDEO_MAX_ESTIMATED_COST_USD=10
SOURCECUT_VIDEO_ESTIMATED_COST_PER_SECOND_USD=replace-with-current-rate
```

Use the existing Gemini credential for local Gemini API access only when that credential has paid
Veo access. Hosted Vertex AI deployments should use workload identity and the existing
`GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, and `GOOGLE_GENAI_USE_VERTEXAI` conventions rather
than storing a service-account key.

Keep model names and cost rates configurable because availability and pricing change. Never submit
a paid generation when `SOURCECUT_VIDEO_ENABLED` is false or a placeholder remains configured.

## Observability

Instrument, without requiring Grafana to be enabled:

- shot-brief creation and deterministic validation;
- approval, provider submission, polling duration, completion, and failure;
- model, duration, generation count, estimated cost, and provider operation latency;
- Gemini review duration and finding counts by support label;
- correction requests and parent/child job correlation.

Do not record full prompts, source quotes, video bytes, credentials, or signed media URLs in spans.

## Tests

- structured shot-brief parsing and validation;
- strict-mode rejection of interpretive additions and uncited details;
- rejection of browser-invented evidence IDs and non-public-domain references;
- stable brief/request fingerprints and immutable correction lineage;
- cost, duration, and generation-count ceilings;
- disabled-by-default behavior that cannot call a provider;
- fake Veo client covering submit, pending, completion, safety block, and failure;
- filesystem and fake Cloud Storage persistence across API-app recreation;
- Gemini critic parsing and deterministic classification summaries;
- API approval/fingerprint checks, `202` generation flow, polling, and correction limit;
- responsive UI states and accessible generated-content disclosure;
- an opt-in live Veo test that is excluded from the default suite and displays its estimated charge
  before execution.

Normal unit and acceptance tests must never incur a paid video-generation call.

## Acceptance criteria

From the canonical Bitterroot Research Board, a user can select one section and:

1. create a valid strict eight-second-or-shorter shot brief whose historical details all resolve to
   stored board evidence;
2. review the references, exclusions, disclosure, model, and estimated maximum charge before an
   explicit paid-generation action;
3. submit one Veo job, leave or refresh the page, and later recover the same durable job state;
4. play the finished clip under the required **AI-generated previsualization — not historical
   evidence** label;
5. view a separate Gemini consistency report that maps visible details back to evidence and marks
   unsupported or interpretive content;
6. create no more than one user-approved corrected child clip from that report.

The demo must prove the guardrail with a deterministic critic fixture containing an unsupported
wagon and show it labeled `unsupported`. A live paid Veo run is required only when credentials,
quota, and a user-approved cost budget are available; otherwise Task 013 remains implemented but
blocked on live-generation acceptance.

## Out of scope

- final production footage or claims of historical accuracy;
- unrestricted text-to-video prompting;
- automatic multi-shot editing, continuity, dialogue, narration, music, or sound design;
- training or fine-tuning a video model;
- publishing generated clips publicly;
- more than one automatic or user-approved correction generation;
- using generated frames as evidence or adding them to the archival media corpus.
