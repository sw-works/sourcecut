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
| 27959 | Open-source repo URL | ✅ | `https://github.com/agiledigits/sourcecut` — **blocked**: private and empty, no LICENSE |
| 27960 | Hosted project URL | ✅ | **blocked** — nothing deployed |
| 27961 | Google Cloud products | ✅ | Vertex AI (Gemini 2.5 Flash, `google-genai`), Agent Development Kit, Cloud Run, Secret Manager, Cloud Storage, Artifact Registry, Cloud Build |
| 27962 | Other tools | ✅ | ClickHouse Cloud, the official `mcp-clickhouse` MCP server 0.4.1, FastAPI, Astro + React, Playwright, Grafana Cloud (OpenTelemetry) |
| 27963 | First time using IBM tools? | ✅ | `N/A, I am not submitting for the IBM track.` |
| 28099 | First time using Grafana tools? | ✅ | `N/A, I'm not submitting for the Grafana track.` |
| 28100 | First time using Parallel tools? | ✅ | `N/A, I am not submitting to the Parallel track.` |
| 28102 | First time using Clickhouse tools? | ✅ | **needs you** — Yes / No |
| 28103 | First time using Replit tools? | ✅ | `N/A, I am not submitting to the Replit track.` |
| 28047 | Share contact details with IBM | — | leave unchecked |

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

## Still blocked

1. **Repo** — private, empty, no LICENSE. Everything is on `feat/ui-redesign`;
   `main` is 45 commits behind at the same tree the branch was cut from.
2. **Hosted URL** — no Cloud Run services exist in `sourcecut-64338`.
3. **Video** — rendered at 2:56, not uploaded; the closing card needs the hosted
   URL first (`node docs/demo/video.mjs --url …`).
4. **Name, tagline, description** — the project record is still "Untitled".
