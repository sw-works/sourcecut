# SourceCut Odyssey Dashboard — Full Product and Technical Specification

Status: Proposed

Scope: Complete product feature set, with phased implementation

Repository decision: Adapt the existing SourceCut repository as a second corpus

Primary work: Homer's *Odyssey*

Canonical work URN: `urn:cts:greekLit:tlg0012.tlg002`

## 1. Decision summary

Build the Odyssey dashboard inside the current SourceCut repository. Preserve the Lewis and Clark
experience and its tables while introducing a corpus adapter boundary for classical texts. Shared
platform capabilities remain responsible for research sessions, agent orchestration, ClickHouse MCP,
evidence validation, media assets, board assembly, telemetry, and exports. Odyssey-owned components
handle CTS/TEI ingestion, editions and translations, book-and-line citations, linguistic enrichment,
narrative chronology, geographic hypotheses, and classical reception.

The finished product is an evidence-backed research environment, not a single route map or an
illustrated reader. It must let a user move among six synchronized representations of the poem:

1. the Greek text and licensed translations;
2. exact citations and claims;
3. reading order and story chronology;
4. the voyage as a narrative graph;
5. real ancient geography and competing geographic hypotheses;
6. ancient objects and later visual reception.

The map is a first-class analytical surface. The narrative sequence is authoritative; modern
coordinates are not. The UI must never collapse textual sequence, traditional identification, and
scholarly hypothesis into one apparently factual route.

## 2. Product definition

### 2.1 Product statement

SourceCut Odyssey is an agentic research dashboard for scholars, educators, students, writers,
designers, and screen-production researchers who need claims about the *Odyssey* to remain traceable
to editions, book-and-line passages, geographic authorities, and visual objects.

### 2.2 Core promise

**Every displayed conclusion distinguishes what the poem says, what a translation chooses, what a
scholar interprets, and what a geographic tradition proposes.**

### 2.3 Product principles

- Primary text before synthesis.
- Stable citation before generated prose.
- Narrative sequence before geographic placement.
- Multiple interpretations before false certainty.
- Edition and translation identity remain visible.
- Later art is reception evidence, not evidence for Homeric material culture.
- AI can retrieve, compare, and synthesize; it cannot become its own source.
- Raw source files are immutable and every derived layer is regenerable.
- Runtime research remains read-only through the official `mcp-clickhouse` server.
- External archives are harvested before use; core research never depends on their live availability.

### 2.4 Success criteria

The complete product must support all of the following:

- Browse all 24 books in Greek and at least two licensed English translations.
- Resolve and share a stable book-and-line citation.
- Compare aligned translation passages without treating translations as independent witnesses.
- Search by Greek form, lemma, English term, character, place, object, theme, and citation.
- Display morphology and definitions with provenance and confidence.
- Separate narrator, embedded narrator, speaker, addressee, and narrative level.
- Compare reading order with chronological story order.
- Explore every major voyage event in an authoritative narrative graph.
- Show securely identified places, regions, traditional identifications, competing hypotheses, and
  mythic or unlocated places without inventing coordinates.
- Build claim-level research boards with exact evidence spans.
- Relate ancient objects and later artworks to passages using explicit relationship labels.
- Export boards, citations, data, and map views with complete attribution.
- Allow curators to review derived annotations and geographic hypotheses without rewriting raw text.
- Preserve existing SourceCut historical research behavior.

### 2.5 Non-goals

The product will not:

- declare a single historically correct route for Odysseus;
- provide an unlicensed modern translation;
- present model-generated translation as a primary translation;
- produce a new critical edition of the Greek text;
- infer manuscript variants that are absent from the ingested sources;
- identify archaeological sites from poetic descriptions without cited scholarship;
- treat artistic representations as direct evidence for Bronze Age or Homeric-period reality;
- replace current scholarly editions, commentaries, or classroom instruction;
- support real-time multi-user editing in the initial complete product;
- generate screenplay scenes or synthetic reenactment imagery;
- depend on live Perseus, Pleiades, or museum APIs during research;
- become a general-purpose classics corpus platform before the Odyssey feature is complete.

## 3. Users and end-to-end workflows

### 3.1 Primary users

- **Researcher or classicist:** verifies language, passages, narrative structure, and geographic claims.
- **Educator:** assembles a cited lesson or guided exploration.
- **Student:** searches passages and compares translations without losing the Greek reference.
- **Writer or documentary producer:** turns textual evidence into defensible creative requirements.
- **Production designer:** separates Homeric details, later iconography, and modern references.
- **Curator or editor:** reviews entities, events, alignments, claims, places, and rights metadata.
- **General reader:** explores the poem through text, chronology, and map without specialist tooling.

### 3.2 Guided exploration workflow

1. User opens the Odyssey landing page.
2. User chooses a starting lens: Read, Voyage, Characters, Themes, Visual Culture, or Ask SourceCut.
3. Selecting a book, passage, event, place, or object updates the shared context rail.
4. Text, timeline, map, claims, and assets remain synchronized to that context.
5. User opens exact evidence in the passage drawer.
6. User saves selected claims and assets to a research board.
7. User exports or shares the board with citations and attribution.

### 3.3 Agentic research-board workflow

1. User submits a natural-language research question and optional scope.
2. The orchestrator identifies relevant books, entities, themes, and analytical dimensions.
3. The agent queries governed ClickHouse views through official MCP tools.
4. Deterministic tools resolve exact CTS spans and validate proposed claims.
5. The agent compares translations, narrative contexts, and geographic classifications.
6. Media requirements are derived only after textual claims exist.
7. Candidate objects and artworks are retrieved from the cached corpus.
8. Each asset receives a relationship, rights status, relevance explanation, and evidence links.
9. The board displays conflicts, unknowns, and unsupported requests rather than filling gaps.
10. The session, tool trace, evidence set, and board snapshot are persisted.

### 3.4 Textual research workflow

1. Enter a citation, Greek form, lemma, English phrase, or concept.
2. Filter by book, edition, translation, speaker, entity, theme, or narrative level.
3. Inspect matching lines with surrounding context.
4. Compare editions or translations where available.
5. Add a passage to a board or create a claim from selected lines.
6. Copy a human citation, CTS URN, or machine-readable JSON reference.

### 3.5 Map research workflow

1. Open the narrative voyage graph, which works without geographic coordinates.
2. Switch on the geographic layer.
3. Filter places by identification class and confidence.
4. Toggle one or more named route hypotheses.
5. Select a node or route edge to see textual passages and scholarly attribution.
6. Compare hypotheses side by side or as distinct overlays.
7. Export a cited map image or GeoJSON containing only licensed public fields.

### 3.6 Visual-culture workflow

1. Select an episode, character, object, motif, or passage.
2. Browse related ancient objects and later representations.
3. Filter by period, medium, institution, relationship, and rights.
4. Inspect the museum record and why it is connected to the text.
5. Add the item to a board with a required reception label.
6. Export only when the item and image rights permit it.

## 4. Product epics and requirements

### 4.1 Epic E1 — Corpus, editions, and provenance

- `E1-F01`: Register the *Odyssey* as a first-class corpus and work.
- `E1-F02`: Support multiple Greek editions and translations as distinct version records.
- `E1-F03`: Preserve source URLs, bibliographic descriptions, licenses, attribution text, fetch time,
  upstream revision, content hashes, and raw TEI payloads.
- `E1-F04`: Pin reproducible ingestion manifests to upstream commits or release artifacts.
- `E1-F05`: Expose corpus, work, edition, and translation metadata in the UI and API.
- `E1-F06`: Prevent a translated passage from being presented without its translation identity.
- `E1-F07`: Support corpus-scoped feature flags and display policies.

### 4.2 Epic E2 — Canonical text reader and citations

- `E2-F01`: Browse books and line-numbered Greek text.
- `E2-F02`: Display one or more synchronized English translations.
- `E2-F03`: Navigate directly to a CTS URN or conventional citation.
- `E2-F04`: Select a contiguous line range and open a citation drawer.
- `E2-F05`: Copy short citation, full bibliographic citation, CTS URN, and share URL.
- `E2-F06`: Preserve surrounding context without altering the cited span.
- `E2-F07`: Highlight claims, entities, speeches, events, and places over the text.
- `E2-F08`: Provide reading-mode controls for Greek only, translation only, parallel, and interlinear.
- `E2-F09`: Support keyboard line navigation and accessible screen-reader labels.
- `E2-F10`: Display license and attribution notices for the active version.

### 4.3 Epic E3 — Search and linguistic analysis

- `E3-F01`: Search exact Greek Unicode text with normalized-diacritic options.
- `E3-F02`: Search English translations separately or together.
- `E3-F03`: Search Greek lemmas and inflected forms.
- `E3-F04`: Filter results by morphology, book, speaker, entity, narrative level, and version.
- `E3-F05`: Display token morphology, lemma, gloss source, and annotation status.
- `E3-F06`: Show frequency by book, speaker, scene, or narrative level.
- `E3-F07`: Compare recurring formulae and epithets using exact occurrences.
- `E3-F08`: Search co-occurrences within a configurable line window.
- `E3-F09`: Save searches and add result sets to boards.
- `E3-F10`: Label algorithmic morphology and embeddings as derived annotations.
- `E3-F11`: Never use lexical similarity as evidence without a resolved text span.

### 4.4 Epic E4 — Claims and evidence matrix

- `E4-F01`: Create claims from exact text spans or curated scholarly references.
- `E4-F02`: Classify every support link by evidence class.
- `E4-F03`: Separate evidence class from confidence and review status.
- `E4-F04`: Display supporting, qualifying, conflicting, and contextual evidence.
- `E4-F05`: Validate exact contiguous quotes against immutable text versions.
- `E4-F06`: Show translation dependence when a claim rests on an English wording choice.
- `E4-F07`: Reject publication of claims lacking the required evidence type.
- `E4-F08`: Preserve model, prompt, schema, validator, and reviewer provenance.
- `E4-F09`: Let users trace `claim → evidence link → passage → version → source`.
- `E4-F10`: Display unsupported questions explicitly.

### 4.5 Epic E5 — Narrative structure and chronology

- `E5-F01`: Model reading order independently from chronological story order.
- `E5-F02`: Mark narrator, embedded narrator, speech, addressee, and audience.
- `E5-F03`: Represent Books 9–12 as an embedded narration at the Phaeacian court.
- `E5-F04`: Represent memories, prophecies, lying tales, reported stories, and flashbacks.
- `E5-F05`: Connect every narrative event to exact passages.
- `E5-F06`: Display duration as textual, approximate, disputed, or unknown.
- `E5-F07`: Provide synchronized Reading Timeline and Story Timeline views.
- `E5-F08`: Allow event comparison by character, place, theme, and narrative level.
- `E5-F09`: Distinguish an event's occurrence from the point at which it is narrated.

### 4.6 Epic E6 — Voyage graph and uncertainty-aware map

- `E6-F01`: Display an authoritative narrative graph for the voyage sequence.
- `E6-F02`: Allow graph nodes with no coordinates.
- `E6-F03`: Display secure ancient places through stable Pleiades identifiers.
- `E6-F04`: Model named traditional and scholarly identifications separately.
- `E6-F05`: Toggle multiple route hypotheses without merging them.
- `E6-F06`: Display mythic or unlocated places in an explicit non-geographic region.
- `E6-F07`: Show route branches, alternatives, returns, and uncertain transitions.
- `E6-F08`: Cite every asserted coordinate or region.
- `E6-F09`: Synchronize selected map features with text, timeline, claims, and assets.
- `E6-F10`: Export map state with legend, attribution, active hypotheses, and citations.
- `E6-F11`: Provide accessible list and table alternatives to every map interaction.

### 4.7 Epic E7 — Entities, themes, and motifs

- `E7-F01`: Model people, gods, groups, creatures, places, objects, flora, fauna, and concepts.
- `E7-F02`: Store exact entity mentions with surface form and resolved identity.
- `E7-F03`: Support aliases across Greek and translation naming conventions.
- `E7-F04`: Distinguish Odysseus/Ulysses-style translation aliases without losing identity.
- `E7-F05`: Provide entity profiles containing passages, events, relationships, map presence,
  vocabulary, and visual assets.
- `E7-F06`: Curate themes and motifs as reference data with citations.
- `E7-F07`: Show entity co-occurrence and relationship graphs as retrieval aids, not historical facts.

### 4.8 Epic E8 — Material culture and visual reception

- `E8-F01`: Ingest reusable museum records and images with raw provider payloads.
- `E8-F02`: Relate assets to passages, events, entities, themes, and claims.
- `E8-F03`: Require a historical/reception relationship on every displayed asset.
- `E8-F04`: Separate ancient representation from later artistic reception and modern reference.
- `E8-F05`: Preserve institution, object ID, dates, medium, culture, source URL, rights, image rights,
  and attribution.
- `E8-F06`: Filter public exports by image and metadata rights.
- `E8-F07`: Explain why each asset was selected and what it cannot establish.
- `E8-F08`: Downgrade or reject visually attractive assets that do not support the stated use.
- `E8-F09`: Provide passage-to-object and object-to-passage navigation.

### 4.9 Epic E9 — Research boards and workspaces

- `E9-F01`: Create a board from an agentic query or manual selections.
- `E9-F02`: Organize boards into user-editable sections.
- `E9-F03`: Save claims, passages, events, map views, entities, and assets.
- `E9-F04`: Preserve generated text separately from user-authored notes.
- `E9-F05`: Regenerate a section without silently replacing prior versions.
- `E9-F06`: Pin a board to corpus and annotation releases for reproducibility.
- `E9-F07`: Display warnings, conflicts, rights limits, and unresolved questions.
- `E9-F08`: Support board duplication and immutable snapshots.
- `E9-F09`: Persist agent and MCP timelines for every generated board.
- `E9-F10`: Allow a board to be reconstructed from stored references without rerunning AI.

### 4.10 Epic E10 — Exports and sharing

- `E10-F01`: Export a printable board as HTML and PDF.
- `E10-F02`: Export citations as plain text, Markdown, CSL-JSON, and BibTeX where applicable.
- `E10-F03`: Export passages and claims as JSON with CTS URNs.
- `E10-F04`: Export map features as GeoJSON, preserving hypothesis and confidence fields.
- `E10-F05`: Export a map image with legend and attribution.
- `E10-F06`: Generate a read-only share link to a frozen board snapshot.
- `E10-F07`: Apply license-aware omission or metadata-only fallback during export.
- `E10-F08`: Include a machine-readable provenance manifest in every board export package.

### 4.11 Epic E11 — Curation and administration

- `E11-F01`: Review and correct derived entities, events, speeches, morphology, alignments, claims,
  and place hypotheses.
- `E11-F02`: Preserve all revisions and reviewer identity.
- `E11-F03`: Promote annotations through draft, reviewed, trusted, rejected, and superseded states.
- `E11-F04`: Validate source licenses before enabling public display.
- `E11-F05`: Run idempotent corpus, gazetteer, and media imports.
- `E11-F06`: Compare new upstream releases before promotion.
- `E11-F07`: Rebuild derived layers without changing immutable source versions.
- `E11-F08`: Provide coverage and validation dashboards.

### 4.12 Epic E12 — Platform safety, reliability, and evaluation

- `E12-F01`: Enforce trusted-evidence row policies for the MCP role.
- `E12-F02`: Limit runtime to authenticated, read-only MCP access.
- `E12-F03`: Enforce query timeouts, result limits, and approved query patterns.
- `E12-F04`: Trace ingestion, extraction, validation, MCP calls, board assembly, and export.
- `E12-F05`: Test citation, span, map, rights, and board invariants.
- `E12-F06`: Keep a known-good offline corpus and completed board snapshots.
- `E12-F07`: Preserve the existing Lewis and Clark test and demo path.

## 5. Corpus, sources, and rights

### 5.1 Primary text source

Initial canonical source: PerseusDL `canonical-greekLit`, Odyssey work directory.

- Greek: `urn:cts:greekLit:tlg0012.tlg002.perseus-grc2`, A.T. Murray edition, 1919.
- English: `urn:cts:greekLit:tlg0012.tlg002.perseus-eng3`, A.T. Murray translation, 1919.
- English: `urn:cts:greekLit:tlg0012.tlg002.perseus-eng4`, Samuel Butler translation, 1900,
  revised by Timothy Power and Gregory Nagy.

Repository license defaults to CC BY-SA 4.0 unless a component states otherwise. Perseus notes
that component rights vary and that not all headers have been checked. Public release therefore
requires a component-level TEI-header review and a recorded legal/display decision.

References:

- <https://github.com/PerseusDL/canonical-greekLit>
- <https://github.com/PerseusDL/canonical-greekLit/tree/master/data/tlg0012/tlg002>
- <https://github.com/PerseusDL/canonical-greekLit/blob/master/data/tlg0012/tlg002/__cts__.xml>

### 5.2 Gazetteer source

Use Pleiades as the primary authority for real ancient places. Ingest a pinned numbered release or
comprehensive JSON dump offline. Store the Pleiades URI, names, representative geometry, feature
geometries, temporal attestations, source references, license, and release identifier.

Pleiades is CC BY 3.0. A Pleiades coordinate is an authority-provided representation of an ancient
place; it does not prove that a poetic place in the *Odyssey* refers to that location.

References:

- <https://pleiades.stoa.org/downloads>
- <https://api.pleiades.stoa.org/>

### 5.3 Visual asset sources

Initial source: The Metropolitan Museum of Art Open Access API. Ingest only items whose record and
image fields allow the intended display/export. Preserve the full API payload.

Additional providers may be added through the existing media-provider adapter only after a rights
review. Wikimedia Commons is permitted only with file-level license and attribution capture.

Reference: <https://metmuseum.github.io/>

### 5.4 Linguistic sources

- CLTK may provide derived tokenization, lemmatization, morphology, and normalization.
- Alpheios may be linked or integrated only after its API and data terms are reviewed.
- Machine-generated analyses remain derived annotations and require confidence/status labels.
- No automatically produced parse is silently presented as a scholarly determination.

References:

- <https://docs.cltk.org/>
- <https://alpheios.net/pages/tools/>

### 5.5 Scholarly and comparative sources

Curated bibliography records may reference books, articles, commentaries, digital projects, and
route reconstructions. Full text is not ingested unless its license permits it. The system stores
bibliographic metadata, stable URL/DOI, locator, a curator-written summary, and the precise claim or
hypothesis it supports.

ToposText and Scaife Viewer are product and interaction references. Do not ingest their data without
component-level permission or a compatible license.

Homer Multitext is a future source for multiformity, manuscript images, and variants only after the
specific Odyssey material and licenses are selected.

### 5.6 Rights taxonomy

Reuse the platform taxonomy:

- `public_domain`
- `cc0`
- `reusable_with_conditions`
- `rights_unclear`
- `restricted`

Add display decisions:

- `full_text_and_export`
- `full_text_no_bulk_export`
- `short_excerpt_and_citation`
- `metadata_and_citation_only`
- `internal_research_only`
- `blocked`

### 5.7 Public display rules

- Display only content allowed by the version or asset display decision.
- Always show source version and attribution near primary text.
- Include share-alike notices where required.
- Do not imply that a public-domain ancient work makes every transcription, translation, image, or
  scholarly annotation unrestricted.
- A board share page is public display and must pass the same rights filter as an export.

## 6. Evidence and interpretation contract

### 6.1 Evidence classes

- `PRIMARY_GREEK_EXPLICIT`: directly supported by the selected Greek passage.
- `TRANSLATION_WORDING`: a documented choice in a named translation.
- `TEXTUAL_INFERENCE`: a bounded inference from one or more primary passages.
- `VARIANT_READING`: a documented reading from a named textual witness or edition.
- `SCHOLIA_OR_ANCIENT_COMMENTARY`: supported by an identified ancient commentary source.
- `MODERN_SCHOLARLY_INTERPRETATION`: supported by a cited modern scholarly source.
- `TRADITIONAL_IDENTIFICATION`: a named reception or geographic tradition.
- `SCHOLARLY_GEOGRAPHIC_HYPOTHESIS`: a cited proposed geographic identification.
- `MATERIAL_OBJECT_RECORD`: supported by an institution's object record.
- `LATER_RECEPTION`: supported by a later artwork or reception source.
- `CONTEXT_ONLY`: relevant background that does not support the claim directly.
- `UNSUPPORTED`: requested conclusion lacks admissible support.

### 6.2 Confidence

Confidence is independent of evidence class:

- `HIGH`: exact support, unambiguous identity, and trusted review or deterministic derivation.
- `MEDIUM`: support is valid but interpretation, alignment, or identity contains bounded ambiguity.
- `LOW`: plausible and cited, but substantially disputed or weakly determined.
- `CONFLICTED`: admissible sources or hypotheses materially disagree.
- `UNKNOWN`: no defensible assessment.

### 6.3 Review status

- `draft`
- `machine_derived`
- `reviewed`
- `trusted`
- `rejected`
- `superseded`

Only `trusted` evidence rows are readable by the production MCP role. Curated reference data may be
read separately but must never be returned as primary textual evidence.

### 6.4 Claim rules

- Every public textual claim requires at least one trusted exact span.
- A translation claim must name the translation.
- A claim about Greek wording must point to the Greek version and relevant token/span.
- Translation agreement does not count as independent primary-source corroboration.
- Geographic coordinates require a place authority and cannot be inferred by the model.
- A poetic place-to-real-place link requires a named identification record.
- A visual asset supports only the relationship stated on its asset link.
- Model-generated summaries may combine evidence but cannot introduce uncited facts.
- Conflicting evidence remains visible and cannot be averaged into certainty.

### 6.5 Exact span invariant

For every passage evidence record:

```text
text_unit.normalized_text[source_start:source_end] == source_quote
```

Store the source version hash, unit hash, offsets, citation range, and validation timestamp. When
Unicode normalization changes code-point offsets, preserve both the immutable original string and
the normalized indexing representation with an explicit offset map.

## 7. Architecture

### 7.1 High-level architecture

```text
Browser
  ↓
Astro SourceCut Web App
  ├── Lewis and Clark corpus routes
  └── Odyssey corpus routes
  ↓
FastAPI Research and Corpus API
  ├── shared session, board, asset, export, and validation services
  └── Odyssey text, citation, narrative, linguistic, and map services
  ↓
Google ADK / Gemini Research Orchestrator
  ├── deterministic SourceCut tools
  └── ClickHouse MCP tool adapter
  ↓
official mcp-clickhouse server
  ↓ authenticated HTTP; dedicated read-only user
ClickHouse Cloud, sourcecut database

Offline pipelines
  ├── Perseus TEI/CTS
  ├── Pleiades snapshot
  ├── museum APIs
  ├── linguistic enrichment
  └── curated scholarship/hypotheses
  ↓ clickhouse-connect admin path
ClickHouse Cloud

All runtime and offline components
  ↓ OpenTelemetry
Grafana Cloud
```

### 7.2 Corpus adapter boundary

The shared platform operates on generic interfaces rather than journal-specific fields:

```python
class CorpusAdapter(Protocol):
    corpus_id: str

    def resolve_reference(self, reference: str) -> ResolvedReference: ...
    def get_passage(self, passage_id: str) -> Passage: ...
    def build_research_scope(self, request: ResearchRequest) -> ResearchScope: ...
    def validate_claim(self, claim: ClaimCandidate) -> ClaimValidation: ...
    def board_sections(self) -> list[BoardSectionDefinition]: ...
```

The existing historical adapter continues to use author/date semantics. The Odyssey adapter uses
work/version/book/line semantics. Shared services must not assume either model.

### 7.3 Trust boundary

- Raw text, source metadata, and rights records enter only through offline loaders.
- Derived annotations enter through validators and review workflows.
- The MCP user can read only approved views and trusted evidence.
- Exact passage resolution, citation validation, writes, and export rights enforcement are
  deterministic application responsibilities.
- Agent-generated SQL is allowed only through `mcp-clickhouse.run_query`.
- Direct repositories never execute model-generated SQL.

### 7.4 Deployment

- Frontend: Astro with prerendered public routes and React islands for interactive workbenches.
- API: existing FastAPI Cloud Run service.
- MCP: separately deployed authenticated `mcp-clickhouse` HTTP service.
- Database: existing ClickHouse Cloud deployment and `sourcecut` database.
- Object cache: existing confined archive cache or a Cloud Storage bucket with private origin and
  application-controlled delivery.
- Local development may disable MCP authentication only on a non-public endpoint.

### 7.5 Architectural requirements by epic

| Component | Implements |
|---|---|
| Odyssey corpus adapter | E1, E2, E4 |
| TEI/CTS ingestion pipeline | E1, E2, E11 |
| Text and linguistic services | E2, E3, E7 |
| Evidence validator | E4, E12 |
| Narrative service | E5 |
| Geography service | E6 |
| Media adapter and verifier | E8 |
| Research orchestrator | E4, E6, E8, E9 |
| Board and export services | E9, E10 |
| Curation services | E11 |
| Telemetry/evaluation | E12 |

## 8. ClickHouse data model

All new identifiers are stable strings generated deterministically where possible. Replacing tables
are queried with `FINAL` through approved views. Dates for modern metadata use `DateTime64`; poetic
story chronology does not use calendar dates.

### 8.1 `corpora`

- `corpus_id LowCardinality(String)` — `odyssey`
- `title String`
- `description String`
- `default_work_id String`
- `adapter_version LowCardinality(String)`
- `display_policy LowCardinality(String)`
- `status LowCardinality(String)`
- `updated_at DateTime64(3, 'UTC')`

Engine: `ReplacingMergeTree(updated_at) ORDER BY corpus_id`.

### 8.2 `works`

- `work_id String`
- `corpus_id LowCardinality(String)`
- `cts_work_urn String`
- `author_display_name String`
- `title String`
- `original_language LowCardinality(String)`
- `book_count UInt16`
- `metadata JSON`
- `updated_at DateTime64(3, 'UTC')`

Unique logical key: `work_id` and `cts_work_urn`.

### 8.3 `source_versions`

- `version_id String`
- `work_id String`
- `cts_version_urn String`
- `version_type Enum8('edition'=1, 'translation'=2, 'commentary'=3, 'witness'=4)`
- `language LowCardinality(String)`
- `label String`
- `editor_names Array(String)`
- `translator_names Array(String)`
- `bibliographic_description String`
- `publication_year Nullable(UInt16)`
- `source_url String`
- `upstream_revision String`
- `license_id String`
- `display_decision LowCardinality(String)`
- `raw_manifest JSON`
- `source_sha256 FixedString(64)`
- `ingested_at DateTime64(3, 'UTC')`

Engine: `ReplacingMergeTree(ingested_at) ORDER BY (work_id, version_id)`.

#### 8.3.1 `licenses`

- `license_id String`
- `spdx_or_rights_code String`
- `display_name String`
- `canonical_url String`
- `attribution_template String`
- `share_alike Bool`
- `commercial_use_allowed Nullable(Bool)`
- `derivatives_allowed Nullable(Bool)`
- `bulk_export_allowed Nullable(Bool)`
- `notes String`
- `reviewed_by String`
- `reviewed_at Nullable(DateTime64(3, 'UTC'))`
- `updated_at DateTime64(3, 'UTC')`

Engine: `ReplacingMergeTree(updated_at) ORDER BY license_id`. A license record describes terms; the
version- or asset-specific `display_decision` remains the final application policy.

### 8.4 `raw_source_documents`

- `document_id String`
- `version_id String`
- `media_type LowCardinality(String)`
- `raw_content String CODEC(ZSTD)` or confined object-storage reference
- `raw_sha256 FixedString(64)`
- `upstream_path String`
- `ingested_at DateTime64(3, 'UTC')`

The raw record is append-only by content hash. Corrections produce a new source version or document.

### 8.5 `text_units`

One row represents the smallest citable unit, normally one poetic line.

- `text_unit_id String`
- `work_id String`
- `version_id String`
- `book UInt16`
- `line_start UInt32`
- `line_end UInt32`
- `citation String` — e.g. `Od. 9.216`
- `cts_urn String`
- `unit_index UInt32`
- `original_text String`
- `normalized_text String`
- `normalization_map JSON`
- `source_document_id String`
- `source_char_start UInt64`
- `source_char_end UInt64`
- `text_sha256 FixedString(64)`
- `parser_version LowCardinality(String)`
- `ingested_at DateTime64(3, 'UTC')`

Engine: `ReplacingMergeTree(ingested_at) ORDER BY (version_id, book, line_start)`.

Indexes: token index on normalized text; projection for `(version_id, book, line_start)` lookup.

### 8.6 `text_passages`

Passages are deterministic windows over citable units and support retrieval without losing line
identity.

- `passage_id String`
- `version_id String`
- `book UInt16`
- `line_start UInt32`
- `line_end UInt32`
- `unit_ids Array(String)`
- `passage_text String`
- `passage_sha256 FixedString(64)`
- `embedding Array(Float32)`
- `embedding_model LowCardinality(String)`
- `created_at DateTime64(3, 'UTC')`

Invariant: the passage is reproducible by joining the ordered `text_units` in `unit_ids`.

### 8.7 `text_tokens`

- `token_id String`
- `text_unit_id String`
- `version_id String`
- `token_index UInt16`
- `surface String`
- `normalized_surface String`
- `lemma String`
- `part_of_speech LowCardinality(String)`
- `morphology JSON`
- `char_start UInt32`
- `char_end UInt32`
- `annotation_source String`
- `annotation_confidence Float32`
- `review_status LowCardinality(String)`
- `annotation_version LowCardinality(String)`
- `updated_at DateTime64(3, 'UTC')`

The exact surface span must validate against the owning text unit.

### 8.8 `translation_alignments`

- `alignment_id String`
- `source_version_id String`
- `target_version_id String`
- `source_book UInt16`
- `source_line_start UInt32`
- `source_line_end UInt32`
- `target_book UInt16`
- `target_line_start UInt32`
- `target_line_end UInt32`
- `source_token_ids Array(String)`
- `target_token_ids Array(String)`
- `alignment_level Enum8('line'=1, 'phrase'=2, 'token'=3)`
- `alignment_method LowCardinality(String)`
- `confidence Float32`
- `review_status LowCardinality(String)`
- `updated_at DateTime64(3, 'UTC')`

Line-range alignment is required. Token alignment is optional until reviewed.

### 8.9 `speeches`

- `speech_id String`
- `work_id String`
- `speaker_entity_id String`
- `addressee_entity_ids Array(String)`
- `audience_entity_ids Array(String)`
- `narrator_entity_id String`
- `narrative_level LowCardinality(String)`
- `book UInt16`
- `line_start UInt32`
- `line_end UInt32`
- `evidence_status LowCardinality(String)`
- `review_status LowCardinality(String)`
- `updated_at DateTime64(3, 'UTC')`

### 8.10 `classical_entities` and `classical_entity_mentions`

Entity fields:

- `entity_id String`
- `entity_type LowCardinality(String)`
- `canonical_name String`
- `greek_name String`
- `aliases Array(String)`
- `description String`
- `authority_uris Array(String)`
- `curation_citations Array(String)`
- `status LowCardinality(String)`
- `updated_at DateTime64(3, 'UTC')`

Mention fields:

- `mention_id String`
- `entity_id String`
- `text_unit_id String`
- `surface String`
- `char_start UInt32`
- `char_end UInt32`
- `mention_role LowCardinality(String)`
- `confidence Float32`
- `review_status LowCardinality(String)`
- `updated_at DateTime64(3, 'UTC')`

### 8.11 `themes` and `theme_passages`

Themes are curated reference data, not primary evidence.

Theme fields include `theme_id`, title, description, aliases, bibliography, curator, status, and
version. Link rows connect a theme to a passage with rationale, evidence class, review status, and
exact supporting span where applicable.

### 8.12 `narrative_events`

- `event_id String`
- `work_id String`
- `title String`
- `summary String`
- `event_type LowCardinality(String)`
- `reading_order_start UInt32`
- `reading_order_end UInt32`
- `story_order_start Decimal64(6)`
- `story_order_end Decimal64(6)`
- `duration_value Nullable(Float64)`
- `duration_unit LowCardinality(String)`
- `duration_certainty LowCardinality(String)`
- `narrative_level LowCardinality(String)`
- `narrator_entity_id String`
- `participant_entity_ids Array(String)`
- `parent_event_id Nullable(String)`
- `review_status LowCardinality(String)`
- `updated_at DateTime64(3, 'UTC')`

Story-order decimals permit insertions without renumbering the entire chronology. Values do not
represent historical dates.

### 8.13 `event_passages`

- `event_passage_id String`
- `event_id String`
- `version_id String`
- `book UInt16`
- `line_start UInt32`
- `line_end UInt32`
- `relationship LowCardinality(String)` — occurs, narrated, recalled, prophesied, summarized
- `evidence_class LowCardinality(String)`
- `review_status LowCardinality(String)`
- `updated_at DateTime64(3, 'UTC')`

### 8.14 `ancient_places`

- `place_id String`
- `canonical_name String`
- `aliases Array(String)`
- `pleiades_uri Nullable(String)`
- `authority_source String`
- `geometry_type LowCardinality(String)`
- `geometry GeoJSON-compatible JSON`
- `representative_lon Nullable(Float64)`
- `representative_lat Nullable(Float64)`
- `coordinate_certainty LowCardinality(String)`
- `source_release String`
- `license_id String`
- `updated_at DateTime64(3, 'UTC')`

This table represents authority places, not claims that an Odyssey place maps to them.

### 8.15 `poetic_places`

- `poetic_place_id String`
- `work_id String`
- `entity_id String`
- `canonical_name String`
- `place_class Enum8('identified'=1, 'region'=2, 'traditional'=3, 'hypothesized'=4,
  'mythic_unlocated'=5)`
- `default_map_behavior LowCardinality(String)`
- `description String`
- `review_status LowCardinality(String)`
- `updated_at DateTime64(3, 'UTC')`

### 8.16 `place_identifications`

- `identification_id String`
- `poetic_place_id String`
- `ancient_place_id Nullable(String)`
- `hypothesis_id String`
- `identification_class LowCardinality(String)`
- `geometry_override JSON`
- `confidence LowCardinality(String)`
- `status LowCardinality(String)`
- `rationale String`
- `scholarly_source_ids Array(String)`
- `curator_id String`
- `review_status LowCardinality(String)`
- `updated_at DateTime64(3, 'UTC')`

No row may be `trusted` without at least one source or an explicit `text_only_unlocated` status.

### 8.17 `route_hypotheses`

- `hypothesis_id String`
- `title String`
- `author_or_tradition String`
- `description String`
- `scholarly_source_ids Array(String)`
- `license_id String`
- `display_order UInt16`
- `is_default Bool`
- `review_status LowCardinality(String)`
- `updated_at DateTime64(3, 'UTC')`

The default hypothesis is `textual_sequence`, which has no obligation to supply coordinates.

### 8.18 `route_nodes` and `route_edges`

Node fields:

- `route_node_id String`
- `hypothesis_id String`
- `event_id String`
- `poetic_place_id String`
- `identification_id Nullable(String)`
- `sequence_index Decimal64(6)`
- `node_kind LowCardinality(String)`
- `geometry JSON`
- `display_region LowCardinality(String)`
- `citation_ids Array(String)`
- `review_status LowCardinality(String)`
- `updated_at DateTime64(3, 'UTC')`

Edge fields:

- `route_edge_id String`
- `hypothesis_id String`
- `from_node_id String`
- `to_node_id String`
- `edge_kind LowCardinality(String)` — traveled, proposed, branch, return, unknown transition
- `sequence_index Decimal64(6)`
- `geometry JSON`
- `certainty LowCardinality(String)`
- `citation_ids Array(String)`
- `review_status LowCardinality(String)`
- `updated_at DateTime64(3, 'UTC')`

Straight line geometry is never presented as a reconstructed sailing track unless the hypothesis
source explicitly provides that geometry. Sequence-only edges render differently from geographic
route claims.

### 8.19 `scholarly_sources`

- `scholarly_source_id String`
- `source_type LowCardinality(String)`
- `title String`
- `creator_names Array(String)`
- `publication_year Nullable(UInt16)`
- `publisher String`
- `doi Nullable(String)`
- `url String`
- `license_id String`
- `citation_text String`
- `metadata JSON`
- `updated_at DateTime64(3, 'UTC')`

### 8.20 `odyssey_claims` and `odyssey_claim_evidence`

Claim fields:

- `claim_id String`
- `corpus_id String`
- `claim_text String`
- `claim_category LowCardinality(String)`
- `evidence_class LowCardinality(String)`
- `confidence LowCardinality(String)`
- `review_status LowCardinality(String)`
- `created_by_type LowCardinality(String)`
- `created_by_id String`
- `schema_version LowCardinality(String)`
- `created_at DateTime64(3, 'UTC')`

Evidence-link fields:

- `claim_evidence_id String`
- `claim_id String`
- `support_role LowCardinality(String)` — supports, qualifies, conflicts, context
- `source_kind LowCardinality(String)` — text_span, token_span, scholarship, object, identification
- `source_record_id String`
- `version_id Nullable(String)`
- `source_quote String`
- `source_start Nullable(UInt32)`
- `source_end Nullable(UInt32)`
- `citation String`
- `validation_status LowCardinality(String)`
- `trusted Bool`
- `validator_version LowCardinality(String)`
- `updated_at DateTime64(3, 'UTC')`

### 8.21 Media tables

Reuse `media_assets`. Add:

- `asset_corpus_links` for corpus, entity, event, theme, place, passage, and claim relationships;
- `asset_relationship_assessments` for relationship class, production use, limitations, evidence,
  confidence, review status, and board/session context.

Odyssey relationship taxonomy:

- `ANCIENT_REPRESENTATION`
- `ANCIENT_COMPARATIVE_OBJECT`
- `LATER_CLASSICAL_RECEPTION`
- `POST_CLASSICAL_RECEPTION`
- `MODERN_REFERENCE`
- `GEOGRAPHIC_REFERENCE`
- `MATERIAL_CULTURE_COMPARATIVE`
- `UNRELATED_OR_UNSUPPORTED`

### 8.22 Board, snapshot, and export tables

Reuse `research_sessions` and `research_events`. Add or extend:

- `research_boards`: current board document and release pins;
- `board_revisions`: immutable board snapshots;
- `saved_searches`: normalized query and filters;
- `export_jobs`: requested format, rights decision, status, artifact reference, and manifest hash.

### 8.23 Governed views

Required runtime views:

- `odyssey_text_lookup_v`
- `odyssey_passage_context_v`
- `odyssey_trusted_claim_evidence_v`
- `odyssey_translation_comparison_v`
- `odyssey_lemma_occurrences_v`
- `odyssey_entity_mentions_v`
- `odyssey_event_timeline_v`
- `odyssey_route_nodes_v`
- `odyssey_route_edges_v`
- `odyssey_place_hypotheses_v`
- `odyssey_media_candidates_v`
- `odyssey_board_source_manifest_v`

Views expose only public-display-eligible source fields to the production MCP role.

## 9. Offline ingestion and enrichment

### 9.1 Pipeline stages

1. Create a source manifest pinned to an upstream revision.
2. Download and preserve raw CTS metadata and TEI files.
3. Verify declared licenses and record the display decision.
4. Parse work/version metadata.
5. Parse books and citable lines into immutable `text_units`.
6. Validate line numbering, ordering, uniqueness, and text hashes.
7. Assemble deterministic passage windows.
8. Align editions and translations at line-range level.
9. Tokenize and produce derived linguistic annotations.
10. Extract candidate entities, speeches, events, and themes.
11. Validate exact spans and load candidates as non-trusted.
12. Review and promote curated/trusted annotations.
13. Ingest a pinned Pleiades release.
14. Load curated poetic places, identifications, hypotheses, nodes, and edges.
15. Harvest and cache eligible museum assets.
16. Link candidate assets and review relationships.
17. Generate retrieval embeddings as guidance only.
18. Publish corpus and annotation release manifests.

### 9.2 TEI parser requirements

- Namespace-aware XML parsing.
- Reject malformed or structurally unexpected documents with an actionable report.
- Preserve every source line exactly as represented by the selected version.
- Normalize only into a separate indexed field.
- Generate deterministic IDs from version URN and citation.
- Detect missing, duplicated, non-monotonic, or malformed book/line identifiers.
- Preserve editorial notes and markup in structured metadata where relevant.
- Never flatten supplied textual variants into an invented single reading.

### 9.3 Translation alignment

- Begin with deterministic book/line correspondence where compatible.
- Store range-to-range mappings because prose translations may not preserve verse boundaries.
- Allow machine suggestions but require review before token-level alignment is trusted.
- Preserve many-to-many mappings.
- Display unaligned lines honestly.
- Version alignments independently from source texts.

### 9.4 Linguistic enrichment

- Normalize Unicode to a documented form for lookup while preserving original code points.
- Store accent-insensitive and case-folded search keys separately.
- Use deterministic token spans.
- Record the source and version of each morphological analyzer or lexicon.
- Treat ambiguity as multiple analyses or an unresolved state, not as forced certainty.
- Curated corrections supersede but do not delete machine annotations.

### 9.5 Event and speech extraction

Gemini may propose structured candidates. A candidate must include exact line ranges, event or speech
type, participants, narrative level, and confidence. The validator checks passage existence and span
bounds. Promotion of the canonical chronology requires human review.

### 9.6 Geographic curation

Geographic hypotheses are curated reference data rather than model-extracted facts. Each hypothesis
must name its source, scope, and licensing status. Every identification records whether it is secure,
regional, traditional, proposed, disputed, or rejected. The application never geocodes mythic names
automatically.

### 9.7 Media ingestion

- Query provider APIs during offline jobs.
- Store raw JSON and a normalized record.
- Download/cache only permitted images.
- Record an image checksum and upstream modification time.
- Recheck rights on refresh.
- Do not delete an older board's metadata when an upstream item changes; preserve the pinned snapshot.

### 9.8 Idempotency

Use stage-specific keys:

```text
source version: cts_version_urn + upstream_revision + raw_sha256
text unit: version_id + book + line + text_sha256 + parser_version
passage: ordered_unit_hashes + segmentation_version
linguistic annotation: text_sha256 + analyzer + model_version + schema_version
extraction: passage_sha256 + model + prompt_version + schema_version
gazetteer: authority_id + source_release + record_hash
media: provider + provider_id + upstream_modified + payload_hash
```

### 9.9 Release manifests

Every public corpus release records source versions, source hashes, parser version, annotation
versions, Pleiades release, route-hypothesis version, media refresh time, license decisions, and
known limitations. Boards pin this manifest ID.

## 10. Runtime agent and tool architecture

### 10.1 Orchestrator responsibilities

The single primary ADK Research Orchestrator:

- interprets the user's research goal;
- selects relevant analytical dimensions;
- queries governed ClickHouse views through MCP;
- asks deterministic tools for exact spans and structured records;
- distinguishes textual evidence from translation, interpretation, geography, and reception;
- proposes claims and asset relationships;
- surfaces conflicts and absences;
- assembles a structured board.

Avoid a multi-agent architecture until evaluation demonstrates a concrete need.

### 10.2 MCP tools

Agent-visible official MCP tools remain:

- `list_databases()`
- `list_tables(database)`
- `run_query(query)`

The MCP role may query only granted tables/views. The prompt includes a concise schema and approved
query patterns for citations, lemma frequency, entity co-occurrence, passage retrieval, translation
comparison, events, hypotheses, and asset candidates.

### 10.3 Deterministic application tools

- `resolve_citation(reference, version_id)`
- `get_text_span(version_id, book, line_start, line_end)`
- `get_parallel_passages(source_span, target_version_ids)`
- `get_token_analysis(token_id)`
- `get_entity_profile(entity_id)`
- `get_event_record(event_id)`
- `get_place_record(poetic_place_id)`
- `get_route_hypothesis(hypothesis_id)`
- `validate_claim(candidate)`
- `inspect_media_asset(asset_id)`
- `verify_asset_relationship(asset_id, claim_ids, intended_use)`
- `assemble_board(session_id)`
- `create_export(board_revision_id, format)`

These tools own exact lookups, validation, rights enforcement, and writes. They never accept arbitrary
model-generated SQL.

### 10.4 Research plan contract

```json
{
  "question": "How should a production visualize the Polyphemus episode?",
  "scope": {
    "books": [9],
    "line_ranges": [],
    "edition_ids": ["odyssey-perseus-grc2"],
    "translation_ids": ["odyssey-perseus-eng3", "odyssey-perseus-eng4"],
    "hypothesis_ids": ["textual-sequence"]
  },
  "dimensions": [
    "setting",
    "characters",
    "actions",
    "objects",
    "language",
    "narrative_context",
    "geography",
    "visual_reception"
  ],
  "display_policy": "public_reusable"
}
```

### 10.5 Claim candidate contract

```json
{
  "claim_text": "...",
  "claim_category": "setting",
  "evidence_class": "PRIMARY_GREEK_EXPLICIT",
  "confidence": "HIGH",
  "evidence": [
    {
      "version_id": "odyssey-perseus-grc2",
      "book": 9,
      "line_start": 216,
      "line_end": 230,
      "source_quote": "...",
      "support_role": "supports"
    }
  ],
  "limitations": []
}
```

### 10.6 Model rules

- Use external knowledge only to guide retrieval.
- Do not quote a passage that was not returned by a deterministic tool.
- Do not invent Greek, citations, line numbers, translations, coordinates, museum objects, or rights.
- Identify the version for every quoted passage.
- Distinguish a translation comparison from source corroboration.
- Return `UNSUPPORTED` when required evidence is absent.
- Preserve conflicting hypotheses.
- Keep summaries within the display rights of their sources.

## 11. API contracts

All routes are versioned under `/api/v1` when implementation begins. Existing compatibility routes
may proxy to them during migration.

### 11.1 Corpus and version routes

`GET /api/v1/corpora` returns available corpus cards and feature flags.

`GET /api/v1/corpora/odyssey` returns work, default versions, release manifest, rights summary,
coverage, and navigation metadata.

`GET /api/v1/works/{work_id}/versions` returns editions/translations with bibliographic and display
metadata.

### 11.2 Citation resolution

`GET /api/v1/text/resolve?reference=Od.%209.216-230&version_id=odyssey-perseus-grc2`

Response:

```json
{
  "resolved": true,
  "work_id": "odyssey",
  "version_id": "odyssey-perseus-grc2",
  "book": 9,
  "line_start": 216,
  "line_end": 230,
  "cts_urn": "urn:cts:greekLit:tlg0012.tlg002.perseus-grc2:9.216-9.230",
  "canonical_url": "/odyssey/read/9?lines=216-230"
}
```

Malformed, ambiguous, missing, and unavailable-version references return distinct 4xx codes.

### 11.3 Text retrieval

`GET /api/v1/text/{version_id}/{book}?from_line=216&to_line=260&include=entities,speeches,events`

Returns ordered text units, annotations, attribution, display policy, and adjacent navigation.
Maximum ranges prevent accidental bulk export where a license forbids it.

### 11.4 Parallel passages

`GET /api/v1/text/{version_id}/{book}/parallel?from_line=216&to_line=230&targets={ids}`

Returns source text, aligned target ranges, alignment confidence/status, and any unaligned units.

### 11.5 Search

`POST /api/v1/search/text`

```json
{
  "corpus_id": "odyssey",
  "query": "πολύτροπος",
  "mode": "lemma",
  "version_ids": ["odyssey-perseus-grc2"],
  "books": [],
  "speaker_ids": [],
  "entity_ids": [],
  "narrative_levels": [],
  "page_size": 25,
  "cursor": null
}
```

Response includes exact hits, highlighted spans, context, facets, query interpretation, and cursor.

### 11.6 Entity, theme, and event routes

- `GET /api/v1/entities/{entity_id}`
- `GET /api/v1/entities/{entity_id}/occurrences`
- `GET /api/v1/themes/{theme_id}`
- `GET /api/v1/events/{event_id}`
- `GET /api/v1/timelines/odyssey?mode=reading|story&filters=...`

### 11.7 Map routes

- `GET /api/v1/maps/odyssey/config`
- `GET /api/v1/maps/odyssey/graph`
- `GET /api/v1/maps/odyssey/geojson?hypotheses={ids}&classes={classes}`
- `GET /api/v1/places/{poetic_place_id}`
- `GET /api/v1/route-hypotheses`
- `GET /api/v1/route-hypotheses/{hypothesis_id}`

Every GeoJSON feature includes `feature_kind`, `identification_class`, `confidence`, `hypothesis_id`,
`source_ids`, `event_ids`, `citation_ids`, and `display_style`. Null geometry records remain present in
the graph response rather than being dropped.

### 11.8 Media routes

- `POST /api/v1/search/assets`
- `GET /api/v1/assets/{asset_id}`
- `GET /api/v1/assets/{asset_id}/relationships`

Asset responses distinguish record rights from image rights and return a cache URL only when allowed.

### 11.9 Research routes

`POST /api/v1/research`

```json
{
  "corpus_id": "odyssey",
  "query": "Build a research board for the Polyphemus episode",
  "scope": {
    "books": [9],
    "line_ranges": [],
    "entity_ids": ["polyphemus", "odysseus"],
    "hypothesis_ids": ["textual-sequence"]
  },
  "version_ids": [
    "odyssey-perseus-grc2",
    "odyssey-perseus-eng3",
    "odyssey-perseus-eng4"
  ],
  "display_policy": "public_reusable",
  "include_visual_assets": true
}
```

Response: `202` with `session_id`, `status`, and event-stream URL.

- `GET /api/v1/research/{session_id}/events` — SSE with replay support.
- `GET /api/v1/research/{session_id}` — status, plan, evidence, board, warnings, release pins.
- `POST /api/v1/research/{session_id}/cancel` — cooperative cancellation.
- `POST /api/v1/research/{session_id}/retry-stage` — retries a failed idempotent stage.

SSE event types:

- `session_started`
- `plan_created`
- `mcp_query_started`
- `mcp_query_completed`
- `evidence_resolved`
- `claim_validated`
- `claim_rejected`
- `map_hypothesis_loaded`
- `asset_candidate_found`
- `asset_verified`
- `board_section_completed`
- `warning`
- `failed`
- `completed`

### 11.10 Board routes

- `POST /api/v1/boards`
- `GET /api/v1/boards/{board_id}`
- `PATCH /api/v1/boards/{board_id}` with optimistic revision token
- `POST /api/v1/boards/{board_id}/duplicate`
- `POST /api/v1/boards/{board_id}/snapshot`
- `GET /api/v1/boards/{board_id}/revisions`
- `GET /api/v1/shared/boards/{share_token}` for a frozen, rights-filtered snapshot

### 11.11 Export routes

`POST /api/v1/boards/{board_id}/exports`

```json
{
  "revision_id": "...",
  "format": "pdf",
  "include": ["claims", "passages", "map", "assets", "provenance"],
  "display_policy": "public_reusable"
}
```

Returns an asynchronous export job. Completed artifacts are signed, expiring downloads. Export
generation repeats rights validation against the pinned metadata snapshot.

### 11.12 Curation routes

Admin-authenticated routes support candidate queues, record comparison, review decisions, and
release promotion. They do not expose arbitrary SQL or raw provider credentials.

## 12. Research board contract

```json
{
  "board_id": "uuid",
  "revision_id": "uuid",
  "corpus_id": "odyssey",
  "title": "Odysseus and Polyphemus — Book 9",
  "question": "...",
  "summary": "...",
  "release_manifest_id": "odyssey-release-...",
  "active_versions": ["..."],
  "active_hypotheses": ["textual-sequence"],
  "scope": {
    "books": [9],
    "line_ranges": [],
    "entities": ["odysseus", "polyphemus"]
  },
  "evidence_matrix": [
    {
      "claim_id": "...",
      "claim_text": "...",
      "evidence_class": "PRIMARY_GREEK_EXPLICIT",
      "confidence": "HIGH",
      "supports": ["claim-evidence-id"],
      "qualifies": [],
      "conflicts": [],
      "translation_notes": [],
      "limitations": []
    }
  ],
  "timeline": {
    "reading_event_ids": [],
    "story_event_ids": []
  },
  "map_state": {
    "selected_event_ids": [],
    "selected_place_ids": [],
    "hypothesis_ids": ["textual-sequence"],
    "viewport": null
  },
  "sections": [
    {
      "section_id": "setting",
      "title": "Setting",
      "generated_summary": "...",
      "user_notes": "",
      "claim_ids": [],
      "passage_refs": [],
      "event_ids": [],
      "asset_assessments": []
    }
  ],
  "warnings": [],
  "unsupported_questions": [],
  "sources_used": [],
  "rights_summary": {},
  "created_at": "...",
  "updated_at": "..."
}
```

Board sections are configurable. Default Odyssey sections are Narrative Context, Setting,
Characters, Actions and Blocking, Objects and Material Culture, Language and Translation,
Geography, Visual Reception, Conflicts and Unknowns, and Source List.

## 13. Text reader specification

### 13.1 Layout

- Persistent book navigation.
- Main reading column with line numbers and selectable ranges.
- Optional parallel translation columns.
- Context rail for entities, events, claims, map, and notes.
- Bottom or side citation drawer that never obscures the active span on desktop.
- Mobile uses one active text column with a version switcher and bottom sheets.

### 13.2 Reading modes

- Greek only.
- Translation only.
- Parallel Greek and one translation.
- Comparative Greek and two translations.
- Interlinear where trusted alignment exists.
- Focus mode with annotations hidden.

### 13.3 Annotation layers

Users may independently toggle:

- speakers and speeches;
- people and gods;
- places;
- objects and creatures;
- events;
- themes;
- linguistic morphology;
- claims and evidence;
- translation divergences.

Overlapping annotations must remain distinguishable without changing the underlying text.

### 13.4 Citation drawer

Displays selected text, version, edition/translator, conventional citation, CTS URN, bibliography,
license, copy actions, board action, and all claims using the span. It distinguishes selected lines
from automatically supplied context.

### 13.5 Translation comparison

- Align by source line range.
- Highlight additions, omissions, naming differences, and structurally divergent ranges as
  navigational aids.
- Do not label computational differences as mistranslations.
- Permit curator-written translation notes with source citations.
- Always retain the Greek anchor when comparing English versions.

### 13.6 Linguistic popover

Selecting a Greek token shows surface, normalized form, lemma, morphology candidates, gloss source,
occurrence count, nearby formulae, annotation source, confidence, and review status. Ambiguous parses
show alternatives.

## 14. Narrative timeline specification

### 14.1 Modes

- **Reading order:** follows Books 1–24 and the order in which the audience receives information.
- **Story order:** arranges represented events into the curated chronology.
- **Narration layers:** groups primary narration, embedded narration, speech, memory, prophecy, and
  fabricated/contested tales.

### 14.2 Visual encoding

- Reading position uses book and line.
- Story position uses ordinal sequence, never a fake BCE date.
- Duration bars appear only when the poem or cited scholarship supplies a defensible duration.
- Uncertain ordering uses overlapping or bracketed ranges.
- Events narrated retrospectively link back to their reading-order location.

### 14.3 Interaction

Selecting an event updates the reader, voyage graph, map, entities, claims, and assets. The browser
back button restores the previous synchronized state. Deep links preserve mode and selection.

### 14.4 Required initial chronology coverage

The complete release covers all major events in all 24 books, including the Telemachy, Calypso and
Phaeacia, the Books 9–12 wanderings, return to Ithaca, recognition sequences, contest of the bow,
slaying of the suitors, reunions, and resolution.

## 15. Map and voyage graph specification

### 15.1 Surfaces

The feature has two coordinated surfaces:

1. **Voyage Graph:** event-and-place sequence with no requirement for coordinates.
2. **Geographic Map:** authority places and named geographic hypotheses.

The graph is the default for first-time users because it most faithfully represents what can be
asserted from the poem.

### 15.2 Map modes

- Textual Sequence.
- Identified Ancient Places.
- Traditional Geography.
- Compare Hypotheses.
- Evidence Density.
- Reading Position.
- Visual Reception by Place.

### 15.3 Place styling

- Identified place: solid marker.
- Probable region: bounded translucent region.
- Traditional identification: outlined marker.
- Scholarly hypothesis: hypothesis-colored marker.
- Disputed identification: split or patterned marker.
- Mythic/unlocated: graph-only or explicit “Beyond” inset.
- Missing data: visible unknown state, never silently omitted.

Color is never the only carrier of classification.

### 15.4 Route styling

- Textual sequence edge: neutral dashed connector.
- Source-proposed route: solid hypothesis-colored geometry.
- Unknown transition: dotted edge or graph-only connector.
- Alternative branch: forked edge with decision annotation.
- Return/repeated visit: curved edge and sequence index.
- Rejected historical proposal: hidden by default and available only in scholarly comparison mode.

### 15.5 Basemap

Use MapLibre GL JS with a bounded, prebuilt Mediterranean basemap so the demo does not depend on a
third-party tile server. Natural Earth or another approved open dataset supplies coastlines and
political-free physical context. Attribution remains visible. If PMTiles is used, its archive is
versioned and served from the controlled static asset origin.

### 15.6 Hypothesis comparison

- Maximum three simultaneous hypotheses to preserve legibility.
- Each receives a stable color/pattern and complete bibliography.
- A disagreement panel lists nodes where identifications differ.
- “Consensus” means agreement among the currently selected hypotheses, not scholarly consensus in
  general.
- Distances and travel times are disabled for sequence-only or mythic edges.

### 15.7 Map evidence drawer

Selecting a feature displays poetic name, classification, active identification, responsible
hypothesis, confidence, exact Odyssey passages, Pleiades record when applicable, scholarly sources,
limitations, and related events/assets.

### 15.8 Accessibility

- Every map feature exists in an ordered list/table.
- Keyboard users can traverse nodes and edges.
- Screen readers receive place, class, hypothesis, sequence, and evidence summaries.
- Reduced-motion mode removes animated route traversal.
- Map legends pass contrast requirements and use symbols in addition to color.

## 16. Entity, theme, and relationship features

### 16.1 Entity profiles

Each profile includes canonical and Greek names, aliases by translation, entity type, curated
description, passage occurrences, speeches, events, relationships, places, vocabulary, themes,
claims, and visual assets.

### 16.2 Relationship graph

The graph supports character-character, character-place, character-object, and event participation
edges. Every edge is computed from trusted mentions/events or marked as curated. It is a navigation
tool, not independent evidence.

### 16.3 Themes

Initial curated themes include nostos/homecoming, xenia/hospitality, identity and disguise,
recognition, storytelling and truth, divine agency, mortality and immortality, loyalty, violence,
memory, cunning, and wandering. Each theme page explains its editorial scope and cites its passage
links.

## 17. Visual culture and asset specification

### 17.1 Asset card

Every card displays image/placeholder, title, institution, object ID, creator/culture, date, medium,
relationship class, rights status, image-rights status, production/research use, limitations, linked
passages, linked claims, and source link.

### 17.2 Relationship rules

- An ancient vase depicting an episode is `ANCIENT_REPRESENTATION`, not proof that the episode
  occurred historically.
- A contemporary object of similar type may be `ANCIENT_COMPARATIVE_OBJECT`, not an object owned by
  Odysseus.
- A later engraving is `POST_CLASSICAL_RECEPTION`.
- A landscape photograph is `GEOGRAPHIC_REFERENCE` only for the identified modern/ancient place.
- Unsupported matches remain searchable to curators but do not appear on public boards.

### 17.3 Search and facets

Search title, description, subject, creator, culture, medium, date, institution, event, entity,
theme, and relationship. Facets include century/period, ancient/later, object type, provider, rights,
image availability, and review status.

### 17.4 Verification

The verifier checks rights, relationship compatibility, linked evidence, anachronism risk, date,
provider identity, and whether the intended use overstates the record. It returns accepted,
accepted-with-warning, metadata-only, interpretive, rejected, or needs-review.

## 18. Research boards, saving, and exports

### 18.1 Board editing

Users can reorder sections/cards, edit their own notes, hide generated summaries, change the active
translation, select map hypotheses, and remove items. They cannot edit source text or overwrite the
stored generated/reviewed claim.

### 18.2 Versioning

Every meaningful save creates a revision with a parent revision, release manifest, changed fields,
actor, and timestamp. Agent regeneration creates a new candidate revision and requires explicit
acceptance before becoming current.

### 18.3 Sharing

Shared boards are frozen revisions, not live mutable workspaces. A share page applies public rights
rules, includes sources/attribution, and warns when an omitted restricted item existed in the private
board.

### 18.4 PDF/print

PDF output includes title/question, executive summary, evidence matrix, selected passages, timeline,
map with legend, assets, warnings, bibliography, licenses, and provenance manifest identifier. Greek
fonts must be embedded and line wrapping verified visually.

### 18.5 Structured export

The JSON export is the canonical machine-readable board. Markdown and HTML derive from it. GeoJSON
contains map records only. CSL-JSON/BibTeX contain bibliographic records only. Exporters never scrape
rendered HTML.

## 19. Frontend information architecture

### 19.1 Routes

```text
/
/odyssey
/odyssey/read/[book]
/odyssey/search
/odyssey/voyage
/odyssey/timeline
/odyssey/entities
/odyssey/entities/[entityId]
/odyssey/themes
/odyssey/themes/[themeId]
/odyssey/visual-culture
/odyssey/research/new
/odyssey/research/[sessionId]
/odyssey/boards/[boardId]
/odyssey/shared/[shareToken]
/admin/odyssey/...
```

### 19.2 Odyssey landing page

- Product proposition and corpus/rights note.
- Resume last reading or research state.
- Book navigator.
- Featured voyage graph.
- Curated entry points by episode, character, theme, and visual object.
- Research query composer with example prompts.
- Coverage and release information.

### 19.3 Shared context model

URL state is authoritative for shareable selection: corpus, book, lines, event, place, entity,
hypotheses, versions, and active panel. Ephemeral hover and open-menu state remains local. Board
edits persist through API revisions.

### 19.4 Responsive design

- Desktop: reader/map/board split panes where appropriate.
- Tablet: two panes with switchable context rail.
- Mobile: single main surface, sticky context summary, bottom-sheet details, and no hover dependency.
- Touch targets meet 44-by-44 CSS pixel guidance.

### 19.5 Accessibility

- WCAG 2.2 AA target.
- Semantic headings and landmarks.
- Full keyboard operation.
- Visible focus states.
- Greek language tags and correct pronunciation hints for assistive technology where supported.
- Accessible data-table equivalents for maps, charts, timelines, and graphs.
- Reduced motion, high contrast, and text resizing to 200%.
- Exported PDFs include reading order, tagged headings where tooling permits, and text alternatives.

### 19.6 Empty and error states

- No search results: explain query interpretation and offer reversible filter changes.
- Unaligned translation: show both ranges without suggesting exact correspondence.
- Unlocated place: keep it in the voyage graph and explain why no map point appears.
- Conflicting hypotheses: show disagreement, never pick one silently.
- Restricted image: show metadata-only card.
- Research failure: preserve completed stages and offer stage retry.
- Unsupported claim: show the question and absence of qualifying evidence.

## 20. Repository structure

```text
sourcecut/
├── apps/
│   ├── api/sourcecut_api/
│   │   ├── agents/
│   │   │   ├── research.py
│   │   │   └── odyssey_prompts.py
│   │   ├── corpora/
│   │   │   ├── base.py
│   │   │   ├── historical.py
│   │   │   └── odyssey.py
│   │   ├── models/
│   │   │   ├── corpus.py
│   │   │   ├── classical_text.py
│   │   │   ├── linguistic.py
│   │   │   ├── narrative.py
│   │   │   ├── geography.py
│   │   │   ├── claim.py
│   │   │   ├── board.py
│   │   │   └── export.py
│   │   ├── repositories/
│   │   │   ├── classical_text.py
│   │   │   ├── narrative.py
│   │   │   ├── geography.py
│   │   │   ├── claims.py
│   │   │   └── boards.py
│   │   ├── services/
│   │   │   ├── citations.py
│   │   │   ├── classical_text.py
│   │   │   ├── linguistic.py
│   │   │   ├── narrative.py
│   │   │   ├── geography.py
│   │   │   ├── claim_validation.py
│   │   │   ├── odyssey_board.py
│   │   │   └── exports.py
│   │   ├── integrations/
│   │   │   ├── clickhouse_mcp.py
│   │   │   └── map_assets.py
│   │   └── main.py
│   └── web/
│       ├── app/
│       │   ├── odyssey/
│       │   │   ├── page.tsx
│       │   │   ├── read/[book]/page.tsx
│       │   │   ├── search/page.tsx
│       │   │   ├── voyage/page.tsx
│       │   │   ├── timeline/page.tsx
│       │   │   ├── entities/[entityId]/page.tsx
│       │   │   ├── themes/[themeId]/page.tsx
│       │   │   ├── visual-culture/page.tsx
│       │   │   ├── research/[sessionId]/page.tsx
│       │   │   └── boards/[boardId]/page.tsx
│       │   └── admin/odyssey/...
│       ├── components/odyssey/
│       │   ├── text-reader.tsx
│       │   ├── parallel-text.tsx
│       │   ├── citation-drawer.tsx
│       │   ├── linguistic-popover.tsx
│       │   ├── voyage-graph.tsx
│       │   ├── odyssey-map.tsx
│       │   ├── dual-timeline.tsx
│       │   ├── hypothesis-legend.tsx
│       │   ├── evidence-matrix.tsx
│       │   └── reception-gallery.tsx
│       └── lib/odyssey/
├── pipelines/
│   ├── classics/
│   │   ├── cts.py
│   │   ├── tei.py
│   │   ├── passages.py
│   │   ├── alignment.py
│   │   ├── linguistics.py
│   │   ├── narrative.py
│   │   └── validation.py
│   ├── gazetteers/
│   │   └── pleiades.py
│   └── media/
│       └── met.py
├── data/
│   ├── manifests/odyssey/
│   ├── reference/odyssey/
│   │   ├── entities.json
│   │   ├── themes.json
│   │   ├── narrative_events.json
│   │   ├── poetic_places.json
│   │   ├── route_hypotheses.json
│   │   └── bibliography.json
│   └── curation/odyssey/
├── sql/clickhouse/
│   └── odyssey/
├── fixtures/
│   ├── odyssey/
│   └── evaluation/odyssey/
├── tests/
│   ├── odyssey/
│   └── integration/
└── docs/hackathon-build/
    └── odyssey-dashboard-spec.md
```

Keep migrations in the existing ordered migration mechanism. The directory grouping shown above may
be represented by filename prefixes if the bootstrap runner currently assumes a flat directory.

## 21. Data lifecycle

### 21.1 Primary text lifecycle

```text
pinned Perseus revision
→ raw CTS/TEI cache
→ source/version manifest
→ immutable citable text units
→ deterministic passages
→ derived annotations
→ validation/review
→ corpus release
→ runtime retrieval
→ exact passage display
```

### 21.2 Geographic lifecycle

```text
pinned Pleiades release + curated scholarship
→ authority places + poetic places
→ explicit identification records
→ hypothesis-specific route graph
→ review/promotion
→ governed runtime views
→ graph/map with citations and uncertainty
```

### 21.3 Research lifecycle

```text
user question
→ stored session/request
→ ADK plan
→ read-only MCP analytics
→ deterministic exact lookups
→ validated claims
→ verified asset relationships
→ board revision
→ rights-filtered share/export
```

### 21.4 State persistence

- Reading selection: URL and local recent-history preference.
- Saved search: ClickHouse saved-search record.
- Research execution: `research_sessions` and `research_events`.
- Board edits: versioned board document.
- Export: immutable job plus artifact and provenance manifest.
- Curation: append/versioned decision records.

## 22. Security, privacy, rights, and abuse controls

### 22.1 Database controls

- Dedicated read-only MCP user and role.
- Grants limited to approved SourceCut views/tables.
- Row policies expose only trusted evidence.
- `CLICKHOUSE_ALLOW_WRITE_ACCESS=false`.
- Query timeout, maximum rows, maximum result bytes, and concurrency limits.
- No credentials or raw authentication headers in telemetry.

### 22.2 Application controls

- Strict Pydantic validation for all model output and API payloads.
- Deterministic citation, span, geometry, and rights validators.
- Parameterized application SQL.
- Optimistic concurrency on board edits.
- Signed, expiring export URLs.
- Admin authentication and audit records for curation.

### 22.3 Model controls

- No arbitrary writes.
- No direct archive calls.
- No coordinates produced from free text.
- No unreturned passage quotation.
- No bulk text reconstruction through iterative searches.
- Rate limits and range limits on text/search endpoints.

### 22.4 Privacy

Research questions and user notes may be sensitive creative work. Store them only as required for the
workspace, restrict access by owner/share token, and redact them from broad telemetry. Log session IDs,
stage names, counts, timings, and error classes rather than full private prompts.

### 22.5 License enforcement

License decisions are data, not prompt instructions. API serializers and exporters enforce display
policies. A change in rights metadata invalidates new exports but does not rewrite historical board
snapshots; affected snapshots receive a warning and metadata-only rendering where required.

## 23. Error and resilience strategy

### 23.1 Critical failure points

1. **TEI structure or line numbering changes:** quarantine the new import and keep the last trusted
   corpus release active.
2. **MCP or ClickHouse unavailable:** stop live research, retain session progress, and allow browsing
   of cached completed boards and static corpus data if the API can serve it safely.
3. **Invalid generated evidence:** reject the claim, record the validation error, and continue the
   board with a warning rather than retrying semantically invalid output.
4. **External media provider unavailable:** use the harvested cache; do not call the provider during
   a research session.
5. **Map geometry failure:** preserve the voyage graph and textual place list.
6. **Export rendering failure:** keep the board intact and retry only the idempotent export job.

### 23.2 Retry policy

Retry transient network, timeout, rate-limit, and 5xx failures with bounded exponential backoff.
Do not retry schema, span, citation, rights, or semantic validation failures without changed input.

### 23.3 Degraded modes

- Reader-only mode.
- Voyage-graph mode without geographic basemap.
- Metadata-only assets.
- Completed-board replay without new agent execution.
- Greek/translation side-by-side without token alignment.

## 24. Observability

### 24.1 Trace spans

- corpus manifest fetch and validation;
- TEI parse per version/book;
- passage generation;
- linguistic enrichment;
- entity/event extraction and validation;
- Pleiades and media ingestion;
- MCP tool call and SQL query;
- deterministic passage/citation lookup;
- claim validation;
- map hypothesis load;
- asset verification;
- board assembly and revision save;
- export rights check and render.

### 24.2 Metrics

- citable units per version and missing-line count;
- passage and alignment coverage;
- token annotation and ambiguity coverage;
- entity/event/speech review coverage;
- trusted claim ratio and validation-failure reasons;
- place class and hypothesis coverage;
- map features without citations;
- asset rights and relationship distribution;
- MCP latency, rows, failures, timeouts, and rejected queries;
- research completion rate and per-stage latency;
- board/export success rate;
- existing Lewis and Clark regression status.

### 24.3 Logging

Structured logs include correlation ID, corpus, release manifest, session, stage, tool, status, and
duration. Do not log full text payloads, user notes, credentials, or signed asset URLs by default.

## 25. Testing and evaluation

### 25.1 Parser tests

- CTS metadata parsing.
- All expected versions discovered.
- Books 1–24 present.
- Book and line order monotonic.
- No duplicate citable URNs.
- Original text preservation and hashes.
- Unicode normalization offset mapping.
- Malformed TEI rejection.
- Idempotent reingestion.

### 25.2 Citation and reader tests

- Conventional citation and CTS URN resolution.
- Single line, range, book boundary, malformed, and missing references.
- Exact selected text and surrounding context separation.
- Share URL round trip.
- Display-policy range limits.
- Greek and translation attribution.

### 25.3 Linguistic tests

- Token spans reconstruct source text.
- Lemma/morphology ambiguity preserved.
- Accent-insensitive search does not alter displayed text.
- Frequency results link to exact occurrences.
- Derived annotations cannot become trusted primary evidence by themselves.

### 25.4 Evidence tests

- Exact substring validation.
- Wrong version, wrong line, and normalization mismatch rejection.
- Translation claims require translation identity.
- Geographic claims require identification/source records.
- Conflict links remain visible.
- MCP role cannot read untrusted rows.

### 25.5 Narrative tests

- Every canonical event has at least one passage link.
- Reading and story order are independent.
- Embedded narration round trips through API/UI.
- Uncertain and overlapping chronology remains representable.
- Books 9–12 correctly display narration context at Phaeacia.

### 25.6 Map tests

- Sequence graph retains unlocated places.
- Mythic places never receive synthesized coordinates.
- Every coordinate has an authority/source.
- Every hypothesis layer remains separately filterable.
- Selecting a feature resolves its citations and events.
- GeoJSON validates and preserves null/unlocated semantics in graph output.
- Legend, attribution, and accessible table match visible state.

### 25.7 Media and rights tests

- Raw provider payload retained.
- Record and image rights treated separately.
- Restricted image becomes metadata-only.
- Relationship labels required.
- Anachronistic or unsupported use is downgraded/rejected.
- Export respects the pinned rights snapshot and current blocking rules.

### 25.8 Agent evaluation

Curate gold research questions across:

- direct passage retrieval;
- Greek wording and lemma search;
- translation comparison;
- character/theme synthesis;
- narrative chronology;
- geographic uncertainty;
- visual reception;
- unsupported or misleading requests.

Human reviewers score citation precision, claim entailment, interpretation labeling, conflict
preservation, asset relationship accuracy, rights correctness, and important-detail recall.

### 25.9 Acceptance targets

- Citable-line parser correctness: 100% for all ingested versions.
- Trusted evidence span validity: 100%.
- Citation resolver precision: 100% on test fixtures.
- Trusted claims with valid evidence and class: 100%.
- Trusted map features with required source attribution: 100%.
- Mythic/unlocated records assigned unsupported coordinates: 0.
- Public assets with valid relationship and rights metadata: 100%.
- Gold research claim precision: at least 95%.
- Important-detail recall on reviewed benchmark: at least 90%.
- Repeated known-good research run success: greater than 95%.
- WCAG automated checks: no critical violations; manual keyboard and screen-reader flows pass.
- Existing SourceCut test suite: no regressions.

### 25.10 Performance targets

- Cached reader page API p95: under 500 ms for a normal 100-line range.
- Text search API p95: under 2 seconds for a paginated corpus query.
- Map/graph data API p95: under 1 second for one hypothesis and under 2 seconds for three.
- Reader selection-to-context update: under 150 ms after data is present in the browser.
- Initial Odyssey route load on a typical broadband connection: under 3 seconds at p75.
- Research progress: first meaningful SSE event within 2 seconds of accepted request.
- Completed-board replay: under 2 seconds at p95, excluding uncached image transfer.
- Standard PDF export: under 60 seconds or returned as an asynchronous in-progress job.

Performance measurements use production-sized data, cold/warm cases are reported separately, and a
failed target blocks launch only after the relevant feature's correctness gates pass.

## 26. Complete product demonstration flows

### 26.1 Polyphemus production board

Query: “Build a production research board for Odysseus and Polyphemus. Separate Homeric evidence,
translation choices, later iconography, material-culture comparisons, and geographic hypotheses.”

The demo shows exact Greek/English passages, evidence matrix, narrative placement, unlocated/textual
voyage node, hypothesis-aware map, public-domain artwork, one rejected overclaim, and export.

### 26.2 Books 9–12 voyage

Start in the reading timeline at Phaeacia, switch to story chronology, animate the narrative graph,
then compare geographic hypotheses. The user selects the Book 12 branch and opens its cited passage.

### 26.3 Translation and language

Search a Greek lemma or epithet, inspect morphology and occurrences, compare Murray and Butler, and
save a precisely bounded translation observation to a board.

### 26.4 Visual reception

Open an episode and compare an ancient representation, later engraving, and modern geographic
reference. Each card explains its distinct evidentiary role and rights.

### 26.5 Unsupported request

Ask for the exact modern coordinates of a mythic island. SourceCut returns the textual sequence,
available proposed identifications, disagreement, and an explicit refusal to manufacture a location.

## 27. Implementation sequence

Phases sequence delivery; they do not reduce the committed full-product scope.

### Phase 0 — Architecture and rights gate

- Approve component-level Perseus display decisions.
- Define corpus adapter interfaces.
- Freeze table and migration naming strategy.
- Select basemap dataset and attribution policy.
- Select initial scholarly route hypotheses and review their reuse terms.
- Record ADRs for multi-corpus architecture, Odyssey evidence classes, and map uncertainty.

Exit: architecture review passes and no source required for Phase 1 has unresolved display rights.

### Phase 1 — Corpus and citation foundation

- Implement corpus/work/version tables and models.
- Implement raw TEI/CTS ingestion.
- Parse all 24 books into citable units.
- Implement passage windows and citation resolver.
- Add reader APIs and basic Greek/translation reader.
- Add license/attribution UI.
- Add parser and citation evaluation fixtures.

Exit: complete corpus browsable with 100% tested citation resolution.

### Phase 2 — Search and linguistic layer

- Implement Greek/English full-text search.
- Add normalization, tokens, lemmas, morphology, and linguistic popovers.
- Implement line-range translation alignment and parallel reader.
- Add frequency, formula, epithet, and co-occurrence queries.
- Add saved search records.

Exit: search and parallel-text acceptance suite passes across all books.

### Phase 3 — Evidence, entities, and claims

- Add Odyssey claim/evidence tables, views, validators, and row policies.
- Build curated entity registry and mention extraction/review.
- Implement speeches and narrator/addressee model.
- Add themes and passage links.
- Adapt evidence matrix and exact trace UI.

Exit: trusted claim boundary is database-enforced and audited.

### Phase 4 — Narrative chronology

- Curate events for all 24 books.
- Add reading/story order and narration-layer APIs.
- Build dual timeline and synchronized selection model.
- Validate Books 9–12 embedded narrative and major flashbacks/prophecies.

Exit: all major events have reviewed passage links and both timeline modes work end to end.

### Phase 5 — Voyage graph and map

- Ingest pinned Pleiades release.
- Curate poetic places and textual-sequence graph.
- Add at least two citable geographic hypothesis layers plus secure-place layer.
- Build voyage graph, MapLibre surface, legends, evidence drawer, and accessible table.
- Add hypothesis comparison and GeoJSON/map exports.

Exit: unlocated-place and provenance invariants pass; full voyage is navigable.

### Phase 6 — Visual culture

- Add Met provider and cached open-access media.
- Curate episode/entity links and relationship assessments.
- Build search/facets, asset detail, reception gallery, and verification flow.
- Add rights-aware images and metadata-only fallback.

Exit: reviewed asset set covers all major episodes and passes relationship/rights evaluation.

### Phase 7 — Full research-board orchestration

- Add Odyssey schema/query guide to ADK and MCP adapter.
- Implement complete deterministic Odyssey tools.
- Build structured research plan, claim validation, asset verification, and board assembly.
- Add session progress UI, cancellation, stage retry, and completed-board replay.
- Evaluate across all gold question categories.

Exit: repeated agentic runs meet precision, recall, and reliability targets.

### Phase 8 — Workspaces, sharing, and exports

- Implement board editing, revisions, duplication, and snapshots.
- Add frozen rights-filtered share links.
- Implement JSON, HTML, Markdown, PDF, citation, and GeoJSON exports.
- Add provenance manifests and export audit trail.

Exit: a board can be reconstructed and exported without rerunning AI.

### Phase 9 — Curation and operations

- Add review queues and audit history.
- Add corpus release comparison/promotion.
- Add coverage and quality dashboards.
- Complete admin authentication and operational runbooks.
- Conduct accessibility, performance, security, rights, and disaster-recovery reviews.

Exit: full-product launch gates and definition of done are satisfied.

## 28. Dependencies and documentation

- Astro: <https://docs.astro.build/>
- FastAPI: <https://fastapi.tiangolo.com/>
- Pydantic v2: <https://docs.pydantic.dev/latest/>
- Google ADK: <https://google.github.io/adk-docs/>
- Google Gen AI SDK: <https://googleapis.github.io/python-genai/>
- ClickHouse: <https://clickhouse.com/docs>
- Official ClickHouse MCP: <https://github.com/ClickHouse/mcp-clickhouse>
- `clickhouse-connect`: <https://clickhouse.com/docs/integrations/language-clients/python/intro>
- OpenTelemetry Python: <https://opentelemetry.io/docs/languages/python/>
- MapLibre GL JS: <https://maplibre.org/maplibre-gl-js/docs/>
- PMTiles: <https://docs.protomaps.com/pmtiles/>
- Perseus canonical Greek literature: <https://github.com/PerseusDL/canonical-greekLit>
- Canonical Text Services overview: <https://cite-architecture.github.io/ctsurn_spec/>
- Pleiades: <https://pleiades.stoa.org/downloads>
- The Met Collection API: <https://metmuseum.github.io/>
- CLTK: <https://docs.cltk.org/>
- Alpheios: <https://alpheios.net/pages/tools/>
- Homer Multitext: <https://www.homermultitext.org/about/>

Pin exact application dependency versions during implementation. Pin datasets by revision or release,
not only by a floating URL.

## 29. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Perseus component rights differ from repository default | Public display/export risk | Audit TEI headers; store display decisions; gate release |
| Line structures differ across translations | Misleading alignment | Many-to-many range alignment; show confidence and gaps |
| Greek NLP produces ambiguous or wrong analyses | Scholarly inaccuracy | Preserve alternatives; label derived status; review key passages |
| A map implies false geographic certainty | Core product trust failure | Graph-first design; typed place classes; hypothesis layers; mandatory citations |
| Route scholarship cannot be redistributed | Missing comparison layer | Store bibliography and curator-authored summaries; seek permission or choose reusable sources |
| Later artwork is mistaken for Homeric evidence | Misleading production guidance | Mandatory relationship labels and limitations |
| ClickHouse schema becomes corpus-specific again | Expensive future adaptation | Enforce adapter boundary and corpus-neutral shared models |
| Full feature breadth weakens reliability | Demo and launch instability | Phase by dependency; keep known-good releases and snapshots |
| External source changes break ingestion | Pipeline failure | Pin revisions; quarantine new imports; retain last trusted release |
| Modern translation demand exceeds rights | User disappointment | Clearly offer licensed versions and citation-only links to other editions |
| Board edits conflict | Lost work | Optimistic revision tokens and immutable snapshots |
| Map assets or tiles create runtime dependency | Demo failure | Serve bounded prebuilt basemap from controlled storage |
| Existing historical dashboard regresses | Loss of original product | Compatibility tests and corpus-specific routes/services |

## 30. Launch gates and open decisions

### 30.1 Required launch gates

- Perseus source-version rights decisions approved.
- All 24 books parsed and citation-audited.
- Greek and at least two English versions available under their display policies.
- Trusted evidence row policy verified using the production-equivalent MCP role.
- Complete major-event chronology reviewed.
- Complete textual voyage graph reviewed.
- Every geographic feature and hypothesis has source attribution.
- No mythic/unlocated place receives an unsupported coordinate.
- Major episodes have reviewed visual assets or an explicit coverage gap.
- Research evaluation and repeated-run reliability meet targets.
- Public sharing and every exporter pass rights checks.
- Accessibility and regression gates pass.
- Operations and recovery runbooks exist.

### 30.2 Decisions to resolve during Phase 0

- Exact Perseus component display decisions after TEI-header audit.
- Which two or three geographic reconstructions may be represented and under what terms.
- Whether the bundled basemap uses Natural Earth GeoJSON directly or a PMTiles build.
- Authentication provider for saved private boards and admin curation.
- Whether full-text public API access requires stricter rate/range limits than the reader UI.
- Which CLTK/lexical model versions are acceptable for initial machine-derived morphology.
- Whether reviewed Alpheios data may be imported or only linked.

These decisions must not be silently delegated to the model or postponed until release.

## 31. Definition of done

The Odyssey feature is complete when:

1. It runs inside the existing SourceCut repository without breaking the historical dashboard.
2. All 24 books are available in the approved Greek edition and licensed English translations.
3. Every passage is addressable by conventional citation, stable internal ID, and CTS URN.
4. Reader, parallel translation, linguistic search, entities, themes, and speeches work end to end.
5. Reading order, story chronology, and narrative levels are complete and synchronized.
6. The voyage graph covers the entire poem and retains unlocated places.
7. The geographic map separates authorities, traditions, and hypotheses with citations.
8. Visual culture covers major episodes with rights and relationship labels.
9. Natural-language research produces validated claims and reproducible boards through read-only MCP.
10. Users can manually edit, version, share, and export boards without altering source evidence.
11. Curation and release workflows preserve immutable sources and revision history.
12. Tests meet all acceptance targets, including 100% trusted-span and map-source validity.
13. The existing Lewis and Clark suite and canonical demo remain operational.
14. Deployment, observability, security, accessibility, rights, and recovery reviews pass.

## 32. Build-checklist handoff

A build checklist derived from this specification must:

- preserve the phase ordering in Section 27;
- split work into independently verifiable tasks;
- name exact files, migrations, fixtures, and tests for each task;
- include a rights or evidence verification checkpoint wherever data becomes publicly displayable;
- require production-equivalent MCP-role tests before any runtime research milestone is complete;
- keep the existing SourceCut test suite as a blocking regression gate;
- distinguish complete-product scope from the smaller demonstration slice used during development.
