# Deferred and gated work

This file records intentionally incomplete work and the condition that reopens it.

| Item | Current state | Unblocking trigger |
|---|---|---|
| Native ClickHouse full-text index | Token bloom indexes and semantic vectors are active; the native full-text index is deferred. | The deployed ClickHouse Cloud build exposes the production-ready full-text index syntax and measurements show it improves this corpus. |
| `vector_similarity` ANN index | Brute-force `cosineDistance` is deliberate at the current corpus size. | Passage/media vector count or measured p95 query time exceeds the runtime budget. |
| Live Veo acceptance | Generation remains disabled; brief/review/correction paths use fakes in default tests. | User reviews model availability, quota, current per-second price, generated brief, and explicitly approves the bounded live test cost. |
| Smithsonian + NPS full harvest | Rights-gated harvesters, fixtures, cache, and CLIs are implemented; no live provider rows were loaded. | `SMITHSONIAN_API_KEY` and `NPS_API_KEY` with sufficient quota are provided; run both smoke harvests, then the ≥500 combined harvest and embedding backfill. |
| Human evidence evaluation | The 71-item fixture is authentic and span-valid but provisional; precision/recall are intentionally unset. | A named reviewer completes every verdict and missed-observation field, then runs `sourcecut-eval import` and `sourcecut-eval run`. |
| Grafana dashboard acceptance | OTel instrumentation and ClickHouse stage rollups exist; integration was postponed. | Grafana OTLP credentials/credits are available and observability becomes a demo priority. |
| Explicit board export/share UI | Boards already persist in ClickHouse and `/api/research/{session_id}` is a durable permalink API. | Product decides authentication/privacy rules and desired export format before exposing a copy-link/download control. |

Native `JSON` conversion is not deferred: `media_assets.raw_metadata` was converted and verified
on ClickHouse Cloud 26.2 during Task 016.

## Agentic workflows (Task 027)

- **Specialist ADK pipeline is opt-in.** `sourcecut-research --pipeline` composes planner,
  researcher, and auditor. The single agent stays the default until the sequence has been
  exercised against the live MCP endpoint with a real credential; construction and tool
  isolation are covered by tests, end-to-end behaviour is not.
- **Self-consistency is not wired into the ingestion CLI.** `extract_with_self_consistency` and
  the eval harness's `--candidates` scoring exist; running an N-sample extraction over the
  corpus and comparing it to the single-shot baseline needs a Gemini credential and quota, and
  the resulting precision delta is unmeasured until the gold fixture has human verdicts.
- **Vocabulary memory is unproven at scale.** Discovered terms are recorded and reused, but no
  curation UI exists for reviewing or reverting them; `provenance='discovered'` and the loader's
  `provenance='curated'` are the only distinction. Revisit if discovered vocabulary grows past
  what a curator can read in one sitting.
