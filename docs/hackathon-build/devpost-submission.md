# Devpost submission — SourceCut

Pulled from the Devpost MCP on 2026-09-07. Hackathon **30721**,
`agentic-cinema`, hosted by Google. Project slot **1378754** already exists,
attached to this hackathon, state `submission_pre_draft` — name "Untitled",
tagline, description and video all empty, created 2026-08-09.

## The clock

| | |
|---|---|
| Submissions close | **2026-09-09 21:00 UTC** — Wed 9 Sept, 2:00 PM PDT |
| Judging | 2026-09-10 19:00 UTC → **2026-10-08 19:00 UTC** |
| Winners announced | 2026-10-13 19:00 UTC |

The hosted URL has to stand from submission through **8 October**, four weeks
after the deadline, which is what `deploy/cloud-run/README.md` sizes the
instance floor for.

## Judging — four criteria, each scored out of 5

| Criterion | What it asks |
|---|---|
| Technological Implementation | How well is it built, and how effectively does it use Google Cloud and the Partner services? |
| Design | A complete, coherent product experience — not a technical proof of concept |
| Potential Impact | A credible, specific case for a real problem and a real audience, judged on what is demonstrated |
| Quality of the Idea | A creative, non-obvious use of Google Cloud and the Partner services, with genuine understanding of the problem space |

Scored **only against the other ClickHouse-track entries** — five tracks, three
identical prize buckets.

## The form — 17 fields

| id | Field | Required | Answer |
|---|---|---|---|
| 27952 | Submitter Type | ✅ | **needs you** — Individual / Team / Organization |
| 27953 | Organization name | ✅ | **needs you** — "N/A" if not representing one |
| 27954 | Government employee? | ✅ | **needs you** — Yes / No |
| 27955 | Country of residence | ✅ | **needs you** |
| 27956 | Canadian province | ✅ | `N/A` |
| 27958 | New or existing prior to 27 July 2026? | ✅ | **New** — first commit `2026-08-09 09:11 -0700`, 125 commits |
| 28213 | Partner track | ✅ | **Clickhouse** |
| 28048 | Team size | ✅ | **needs you** — 4 max |
| 27959 | Open-source repo URL | ✅ | `https://github.com/sw-works/sourcecut` — public, Apache-2.0 detected by GitHub |
| 27960 | Hosted project URL | ✅ | **blocked** — nothing deployed |
| 27961 | Google Cloud products | ✅ | **drafted below** |
| 27962 | Other tools | ✅ | **drafted below** |
| 27963 | First time using IBM tools? | ✅ | `N/A, I am not submitting for the IBM track.` |
| 28099 | First time using Grafana tools? | ✅ | `N/A, I'm not submitting for the Grafana track.` |
| 28100 | First time using Parallel tools? | ✅ | `N/A, I am not submitting to the Parallel track.` |
| 28102 | First time using Clickhouse tools? | ✅ | **needs you** — Yes / No |
| 28103 | First time using Replit tools? | ✅ | `N/A, I am not submitting to the Replit track.` |
| 28047 | Share contact details with IBM | — | leave unchecked |

These two answers can only be written as part of `submit_project` — the MCP
has no partial-save for custom fields, and a submit call refuses outright while
a required field is missing. They are drafted below, ready to send with the
submission.

A video URL is **required** by the form (`video_required: true`). A website and
a zip file are not.

## What the host asks for, verbatim

- a URL to the hosted Project;
- the 3-minute demo video — "showing your project/agent functioning as built —
  not a cinematic trailer", public on YouTube or Vimeo, English or English
  subtitles;
- a public repo on GitHub, GitLab or Bitbucket with all source, assets and
  instructions to run, demonstrating "actual runtime use of Google Cloud and
  your chosen Partner's service (imported and called in code, not just named in
  the README)";
- a complete open-source licence file, "detectable and visible at the top of the
  repository page (in the About section)";
- the partner track;
- the completed form.

The repo clause is the one to read twice: the ClickHouse integration has to be
callable from the source a judge clones, which it is — `mcp-clickhouse` 0.4.1 is
the official server, reached over HTTP by `ClickHouseMcpClient`, and every board
in the demo was produced through it.

## Gallery captions

Ten images, in order. Short: a caption is a label, not a sentence about the
label. The MCP cannot edit a caption once uploaded — that is done on the Devpost
gallery page — so these are the replacements to paste.

| # | Image | Caption |
|---|---|---|
| 1 | `01-landing-hero` | Describe a scene; get a research board. |
| 2 | `13-timeline-date-held` | Every day of the window, and what the journals back up. |
| 3 | `21-requirement-panel` | Verbatim extracts, and who wrote what, on which day. |
| 4 | `24-passage-span` | Every quote checked against the stored passage. |
| 5 | `17-archive-grid` | Period maps, labelled by how much each proves. |
| 6 | `41-trace-plan` | Every step of a run is a row in ClickHouse. |
| 7 | `06-project-odyssey` | The same five stages on a poem: by book and line. |
| 8 | `01-system-topology` | Read-only MCP at runtime; writes on a separate path. |
| 9 | `p3-specialist-agents` | Planner, researcher, auditor. Only one holds the tools. |
| 10 | `03-corpus-acquisition` | Acquire, parse, segment, extract, reference. |

## Field 27961 — What Google Cloud products did you use in this project?

**Vertex AI** — Gemini 2.5 Flash for research planning, requirement extraction
and visual inspection of archive images, and `gemini-embedding-2` for the
passage embeddings behind vector search. The deployed services authenticate as
their own service account, so no model API key ships with them.

**Agent Development Kit (`google-adk`)** — the planner / researcher / auditor
sequential agent. The ClickHouse MCP toolset is bound to the researcher alone,
and a `before_tool_callback` guardrail validates every query before it leaves
the process.

**Google Gen AI SDK (`google-genai`)** — the client for both of the above.

**Cloud Run** — three services: the official ClickHouse MCP server, the FastAPI
research API, and the Astro web application.

**Secret Manager** — the ClickHouse credentials and the MCP bearer token,
mounted into Cloud Run rather than baked into images.

**Cloud Storage** — the archive image cache, mounted into the API at the exact
path recorded in ClickHouse.

**Artifact Registry** and **Cloud Build** — container images for the three
services.

**IAM** — a dedicated runtime service account holding Secret Manager Secret
Accessor, Storage Object Viewer and Vertex AI User, and nothing else.

## Field 27962 — Please list all other tools or products you used

**ClickHouse Cloud** — the evidence store. Passages, trusted observations,
archive metadata, vocabulary memory, and a row for every step of every run. 133
migrations, a dedicated read-only research role with row policies, parametrized
views for date windows, and `cosineDistance` for vector ranking.

**ClickHouse MCP server** — the official `mcp-clickhouse` 0.4.1, the only
runtime path from the agent to the data. Every retrieval is read-only SQL sent
over MCP.

**Model Context Protocol** — the transport, over the Python MCP SDK's streamable
HTTP client.

**Python 3.13, FastAPI, Pydantic v2, uv, pytest** — the API and the extraction
pipelines; 279 tests.

**Astro 5, React 19, TypeScript** — the web surface, prerendered from committed
example boards.

**Playwright** — capture of the committed demo stills. **ffmpeg** — the demo
video render.

**Grafana Cloud** — OpenTelemetry traces and metrics from the API and the
pipelines.

**Sources**: Project Gutenberg (the Lewis and Clark journals), archive.org
(Gass, 1904 OCR), Perseus Digital Library (the Odyssey in Greek and two
translations), the Library of Congress (archive maps and photographs), and
National Park Service trail references (route waypoints).

## Still blocked

1. **Repo** — private, empty, no LICENSE. Everything is on `feat/ui-redesign`;
   `main` is 45 commits behind at the same tree the branch was cut from.
2. **Hosted URL** — no Cloud Run services exist in `sourcecut-64338`.
3. **Video** — rendered at 2:56, not uploaded; the closing card needs the hosted
   URL first (`node docs/demo/video.mjs --url …`).
4. **Name, tagline, description** — the project record is still "Untitled".
