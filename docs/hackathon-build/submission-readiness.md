# Submission readiness

Rules read 2026-09-06 from https://agentic-cinema.devpost.com/rules and the
event page. **Deadline: 2026-09-09, 2:00pm PDT** — about three days out.

## What the rules require

| # | Requirement | Where it bites |
|---|---|---|
| 1 | A **hosted project URL** | Cloud Run is torn down |
| 2 | A **text description** — features, technologies, data sources, findings and learnings | Not written |
| 3 | A **public open-source repository** with the source and the runtime integration of Google Cloud and the partner service | Repo is private and **empty** |
| 4 | An **open-source license file detectable at the top of the repository page** | No LICENSE |
| 5 | A **demo video**, ≤3 minutes, publicly on YouTube or Vimeo, English or English subtitles, showing the project working | Planned, not shot |
| 6 | A **partner track** designation and the Devpost form | ClickHouse track |
| 7 | ClickHouse track: **actively use ClickHouse at runtime via the official ClickHouse MCP server** | Met by design |
| 8 | **Only Google Cloud AI tools**: "No other AI models, agent frameworks, or AI APIs are permitted, regardless of vendor" | See the open question below |

Judging is four equally weighted criteria: Technological Implementation, Design,
Potential Impact, Quality of Idea.

## Where the project stands

| Requirement | Status | Evidence |
|---|---|---|
| ClickHouse at runtime via official MCP | **Met** | `mcp-clickhouse` 0.4.1 runs as its own service; every board query goes through `run_query` on it, with row counts recorded per call in `research_events` |
| Google AI packages | **Met** | Runtime AI dependencies are `google-adk[mcp]` and `google-genai` and nothing else |
| Working product | **Met** | Five captured boards, 14,685 trusted observations, 2,366 passages |
| Repository content | **Met** | Source, runbooks, migrations, diagrams, evaluation |
| Repository published | **Blocked** | `agiledigits/sourcecut` exists, is private, and has never been pushed to — 104 local commits, remote is empty |
| LICENSE | **Blocked** | None |
| Hosted URL | **Blocked** | Cloud Run torn down after the last live run |
| Demo video | **Blocked** | Shot list ready in `demo-plan.md`, 32 stills captured |
| Text description | **Blocked** | Not written |

## Plan

### Saturday 2026-09-06 — publish and deploy

1. **Add a LICENSE.** Apache-2.0: the patent grant is worth having, and Devpost
   looks for a file at the top of the repository page. ~5 min.
2. **Publish the repository.** Nothing needs scrubbing first — `.env*` has been
   git-ignored from the start, no credential-shaped file was ever added, and a
   scan of every commit for key-shaped strings (`AIza…`, `sk-…`, PEM headers)
   found nothing. ~15 min.
   ```bash
   git push -u origin main
   git push -u origin feat/ui-redesign
   gh repo edit agiledigits/sourcecut --visibility public --accept-visibility-change-consequences
   ```
   Decide first whether `feat/ui-redesign` merges to `main` — a judge landing on
   an eight-month-old default branch sees the wrong project. Merging is the
   cleaner story.
3. **Redeploy Cloud Run.** This is a redeploy, not a rebuild: project
   `sourcecut-64338`, the three images, five secrets, the archive bucket and the
   IAM grants all survived the teardown. Follow `deploy/cloud-run/README.md`.
   ~45 min including a smoke test.
4. **Verify the hosted URL** as a visitor would: landing page, one captured
   board, one live brief end to end, and the passage drill-down (it calls the
   API). ~20 min.

### Sunday 2026-09-07 — video and description

5. **Record the video** from `demo-plan.md`: 17 shots, 2:50, cut from the
   committed stills and the four diagrams. Include the hosted URL on the closing
   card. Burn in captions. Upload unlisted first, watch it once end to end, then
   make it public. ~4 hours with narration and captions.
6. **Write the text description.** Four things the rules name — features,
   technologies, data sources, findings and learnings. The material exists:
   `README.md`, `docs/hackathon-build/decisions.md` (ADRs), the diagram README,
   and `deferred.md` for what was deliberately not built. ~2 hours.

### Monday 2026-09-08 — submit

7. Fill the Devpost form, select the ClickHouse track, attach the URL, repo and
   video. Submit Monday, not Tuesday: the deadline is 2:00pm PDT Tuesday and a
   day of margin costs nothing.
8. Leave the deployment up until judging closes. Judging runs **23 September to
   7 October 2026** (rules read 2026-09-07), so the URL has to stand for about
   four weeks after submission, not just to the deadline. This is the one case
   where the usual "tear it down after the run" rule does not apply — requirement
   1 is a live URL. All three services deploy at `--min 0`, which keeps Cloud Run
   inside its free monthly allowance for that traffic; ClickHouse Cloud storage
   is the only meaningful bill. Tear the services down after 7 October.

## The open question: the AI-tools clause

> "Projects may only use Google Cloud artificial intelligence tools… No other AI
> models, agent frameworks, or AI APIs are permitted, regardless of vendor —
> this includes but is not limited to AWS, Microsoft, OpenAI, and Anthropic AI
> tools."

**The product is clean.** Every model call at runtime is Gemini through
`google-genai`, and the agent framework is Google ADK. There is no other AI
dependency in the tree.

**The development process is the question.** This project was built with Claude
Code, and 48 of the 104 commits carry a `Co-Authored-By: Claude Opus 5` trailer
that will be visible the moment the repository is public.

Two readings. The clause governs what a *project* uses — it sits among rules
about models, APIs and frameworks, and the IBM track separately *requires* a
specific tool "as part of the development process", which shows the rules treat
development tooling as its own category. On that reading the trailers are
irrelevant. The other reading is that a judge scanning a public repo sees
"Anthropic" and does not stop to make the distinction.

**Ask the organizers.** One message through Devpost's discussion board, today,
so the answer arrives before Monday. Do not rewrite history to hide the
trailers: they are accurate attribution, and stripping them to pass a check is
the wrong move whichever way the rule falls.

## Worth considering, not required

- **Vertex AI instead of the Gemini API key.** "Technological Implementation" is
  scored on Google Cloud usage, and routing the deployed services through Vertex
  AI reads as more of Google Cloud than an API key does. The planner currently
  sets `vertexai=False` explicitly, so this is a code change plus IAM, not a
  flag. Only if the schedule above holds with room to spare.
- **Delete the `sourcecut-64338-previs` bucket.** Dead since previs was removed.
- **The live-trace defect.** The video does not depend on it, and the hosted URL
  still produces correct boards. Fix it only if Sunday runs short.
