# Devpost copy — SourceCut

Draft for project 1378754. Numbers checked against `data/examples/corpora.json`
on 2026-09-07.

## Name (max 60)

    SourceCut

## Tagline (max 200)

    An agentic research producer for film and documentary: describe a scene, get a research board where every claim resolves to a passage somebody actually wrote.

(153 characters.)

## Description

Getting the past right means getting small things right — what people ate, what
they carried, what the weather did on a particular afternoon. Those answers sit
in what people wrote at the time: diaries, letters, logs, poems. Finding them
means reading, and reading is the part a production schedule never has room for.

SourceCut is an agentic research producer for historically grounded film and
documentary. Describe a scene the way you would brief an art department, and it
researches that scene against a primary-source corpus and hands back a research
board where every claim resolves to a passage somebody actually wrote.

### What it does

**Plans the research.** Gemini on Vertex AI turns a scene brief into a plan:
which stretch of the record to search, which requirements the scene needs, and
which period spellings to look for. The date window is read from a curated file
of expedition segments rather than guessed.

**Retrieves through ClickHouse.** Every search is read-only SQL sent through the
official ClickHouse MCP server — parametrized views for the date window, vector
search over passage embeddings, and row policies on the tables underneath. The
research role can read the texts and nothing else.

**Scores coverage one requirement at a time.** Each requirement carries its own
success criterion, so the run knows exactly which ones are still unmet. When a
round comes up short it widens the vocabulary for those requirements only —
reaching for the words a diarist would have written in 1805, *ironboat*, *sward*,
*vapour* — and searches the same window again.

**Verifies every quotation.** An observation stores the character offsets of the
text it cites, and those characters are checked against the stored passage. A
span that does not match is never marked trusted, so a quotation on the board is
the source's words rather than a paraphrase of them.

**Correlates archive material.** Library of Congress maps and photographs arrive
with their provider, catalogue number, rights status, and a confidence label
saying how much each one actually proves — `HIGH`, `INTERPRETIVE · NOT PROOF`,
or unsupported.

**Says what the corpus cannot support.** Where the record is silent the board
says so. The expedition's iron-frame boat is in the history books; it is not in
these three diaries, and the board reports that rather than reaching for
something that sounds close.

### How a corpus is built

The research agent is only as good as the corpus under it, so the extraction
workflow is the other half of the product — five stages, each one a command that
can be re-run and audited.

**Acquire.** A public-domain or openly-licensed source is fetched once and
pinned to a source version, with its licence recorded against it: Project
Gutenberg 8419 and an archive.org OCR of Gass's 1904 edition for the journals,
Perseus for the Greek and both translations of the Odyssey.

**Parse.** Raw text becomes dated entries with an author attached — 2,267 of
them for the journals — or, for a poem, numbered lines.

**Segment.** Entries become passages carrying their character offsets and a
SHA-256 of the text, which is what makes a quotation checkable later.

**Extract.** Gemini reads one passage at a time and proposes observations, each
naming a category, a term, and the exact character span it is claiming. The same
passage is sampled three times and only candidates that recur in at least two
runs survive, matched on the span they point at — a reading that appears once in
three is exactly the kind not to trust. What survives is then validated against
the stored text: spans that do not match the source are rejected, as are exact
duplicates. Only what is left becomes a trusted observation.

**Reference.** Archive material is correlated to requirements, and its rights
are accepted by a person. The model never decides what may be used.

Extraction runs over a bounded window — a source and a date range — so a corpus
grows in reviewable increments rather than one unrepeatable pass, and every
count on the project page traces back to a command someone can run again.

### Two corpora, one pipeline

The five stages — acquire, parse, segment, extract, reference — are not built
around diaries.

**The Lewis and Clark journals**: 2,267 dated entries from three diarists,
2,384 passages, 14,685 trusted observations over 5,546 distinct terms, 22
catalogued archive references, nine route waypoints.

**Homer's Odyssey**: 15,570 lines and 87,189 tokens across the Greek and two
translations, 1,048 passages, 80,091 formula occurrences, 39 narrative events,
16 places, and three competing route hypotheses held apart rather than merged
into one line on a map. A poem is read, not dated, so it is addressed by book
and line — same pipeline, same evidence rules.

### How we built it

**Agents** — Google's Agent Development Kit runs a sequential pipeline of
planner, researcher and auditor, separated by what each one can touch. The
planner holds no tools at all; only the researcher holds the ClickHouse toolset,
and a `before_tool_callback` guardrail validates every query before it leaves
the process.

**Models** — Gemini 2.5 Flash through Vertex AI, using the service account's own
credentials, so the deployed services carry no model API key.

**Data** — ClickHouse Cloud behind the official `mcp-clickhouse` server, with a
dedicated read-only role, row policies, parametrized views for date windows, and
`cosineDistance` for vector ranking. 133 migrations back the schema. Every step
of every run is itself a row in ClickHouse, which is what the execution trace in
the UI reads back.

**Surface** — an Astro + React application on Cloud Run. Every page is
prerendered from committed example boards, so the record stays readable even
when the backend is asleep.

### Challenges

ClickHouse `Date` and `Date32` do not reach back to 1804, so historical dates
are stored as sortable `Int32` `YYYYMMDD` values.

Gass's journal is an OCR transcription of a 1904 edition, and its spelling is
the editor's rather than the manuscript's — which is why vocabulary expansion
had to be a first-class step rather than a fallback.

Span verification caught what nothing else would have: a model will paraphrase
a quotation while believing it is quoting. Checking offsets against the stored
text is the difference between a citation and a claim.

ClickHouse Cloud suspends when idle and refuses the first connection while it
resumes. Both clients now wait that out and retry, so an idle link answers
slowly instead of failing.

### What we learned

Evidence beats fluency. The most useful thing the system does is decline —
naming the requirement the corpus cannot defend is worth more to a production
than a confident paragraph that cannot be traced.

Coverage has to be measured per requirement. A single score for a whole board
hides exactly the gap somebody needs to know about.

### What's next

A third corpus is scoped: Scott's *Terra Nova* journals, 378 dated entries, 357
of which resolve to a unique year by weekday alone.

### Built with

Google Cloud · Vertex AI · Gemini 2.5 Flash · Agent Development Kit ·
google-genai · Cloud Run · Secret Manager · Cloud Storage · ClickHouse Cloud ·
Model Context Protocol · mcp-clickhouse · Python · FastAPI · Pydantic · Astro ·
React · TypeScript · Playwright
