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

## Corpus acquisition (Task 028)

- **Stage 1 is built; stages 2–5 are not.** The repository registry exists —
  `source_repositories`, the committed `data/reference/*.json` files, `sourcecut-load-repositories`
  and `sourcecut-probe-repository`. Discovery, rights determination, staging, the fidelity report
  and promotion do not. `licenses`, `source_versions`, `raw_source_documents`, `corpus_releases`
  and `release_promotions` were designed for this shape, so what remains is pipeline, not storage.
- **Three repositories admitted, three refused, all six probed live on 2026-09-03.** In:
  Gutenberg, Internet Archive, English Wikisource. Out: Library of Congress (per-collection HTML
  prose, nothing matchable), HathiTrust and govinfo (below). Supply is now Gutenberg's catalogue,
  the reviewed slice of Internet Archive, and Wikisource's root works.
- **HathiTrust is blocked on search, not on rights.** Its Bib API reports `rightsCode` `pd` /
  `usRightsString` "Full view" cleanly, but there is no anonymous search — `cgi/ls` answers 403
  and the Data API needs member-institution credentials — so discovery cannot enumerate
  candidates. Rights also sit per volume inside an `items[]` array of objects, which needs a
  third match mode. Reopens if credentials are obtained.
- **US federal works need a policy decision, not code.** govinfo package summaries carry no
  rights, licence or copyright key at all (checked across USCOURTS and CHRG): federal works are
  public domain by statute, 17 USC 105, not by declaration. Admitting govinfo means accepting a
  categorical determination about a collection instead of reading a declared field, which changes
  how ADR-024 decides eligibility. The narrower risk is real — a Congressional Record or CFR
  package can reprint third-party copyrighted matter inside an otherwise federal document — so
  the decision is which collections, not whether govinfo as a whole.
- **Gutendex is intermittently unavailable.** Across the probe runs it returned 503 and timed
  out past three retries as often as it answered. Acquisition against Gutenberg needs to treat
  an unreachable catalogue as a retryable run rather than an empty result.
- **`possible-copyright-status` is thin outside scoped queries.** Internet Archive records it
  only on reviewed items: 8% presence on a loose title search, 100% scoped to a scanning partner's
  pre-1860 texts. Discovery must scope its searches or most candidates will be refused as status
  unknown, which is correct and useless.
- **Corpus breadth is the product's ceiling.** SourceCut answers only for periods whose sources
  are loaded, and loading a period currently means a developer naming an edition in
  `corpus-sources.md` and writing a parser for it. Until acquisition exists, "point it at your
  period" is not a claim the product can make.
- **OCR fidelity is the unmeasured risk.** Precisely valid character offsets into garbled OCR
  are wrong in a way neither the span validator nor any rights check detects. ADR-025 makes
  fidelity a promotion gate, but the baselines it compares against have not been computed from
  the loaded corpus.
- **Perspective-guided planning is not implemented.** The research planner still emits the six
  fixed `BASELINE_REQUIREMENTS` regardless of brief. ADR-023 records the STORM technique worth
  taking; applying it to `PlannedRequirement` (a costume designer and a location scout ask
  different things of one scene) is unscheduled.
