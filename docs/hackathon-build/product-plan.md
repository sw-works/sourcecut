# Product Plan

## Product

**SourceCut — an agentic research producer for historically grounded film and documentary production.**

A filmmaker describes a scene, historical event, person, place, or research question. SourceCut:

1. identifies the relevant historical period and research dimensions;
2. investigates primary-source journal passages;
3. compares evidence across diarists;
4. derives visual/production requirements from evidence;
5. finds candidate archival media;
6. verifies media against the evidence;
7. produces a research board with provenance, rights, and confidence labels.

## Initial domain

Lewis & Clark Expedition, 1804–1806.

Canonical demo: the Corps of Discovery crossing the Bitterroot Mountains in September 1805.

## Target user

Documentary producer, researcher, production designer, writer, or historical consultant.

## Core promise

**Creative recommendations should be traceable back to historical evidence.**

## Signature features

### Evidence Matrix

Shows which visual details are supported by which diarists and whether support is high, single-source, interpretive, conflicted, or unsupported.

### Evidence-backed asset cards

Each asset includes:
- source institution;
- rights status;
- production relevance;
- historical relationship classification;
- confidence status;
- supporting passage(s);
- explanation of why SourceCut selected it.

### Historical confidence model

- `HIGH`: multiple relevant primary-source observations.
- `MEDIUM`: one strong primary source or indirect contemporaneous evidence.
- `INTERPRETIVE`: plausible production reference but not directly demonstrated by expedition evidence.
- `UNSUPPORTED`: insufficient or conflicting evidence.

## MVP success condition

Given a Bitterroot research prompt, SourceCut must reliably:

1. identify September 1805;
2. retrieve Lewis and Clark passages;
3. extract production-relevant evidence;
4. compare accounts;
5. generate media requirements;
6. retrieve candidate assets;
7. reject or downgrade at least one unsupported asset;
8. produce a visual board;
9. let the user trace recommendations to source passages.

## Non-goals

Do not build:
- a universal archive ingestion platform;
- a general-purpose knowledge graph;
- collaborative production management;
- a video editor;
- generated historical reenactment imagery;
- screenplay generation;
- autonomous arbitrary web browsing;
- exhaustive Lewis & Clark scholarship.

## Judging story

- **Technological implementation**: Gemini + ADK perform agentic planning/verification; ClickHouse performs meaningful runtime analytical retrieval.
- **Design**: research board, not chat UI, is the main product surface.
- **Potential impact**: reduces fragmented archive/journal research for production teams.
- **Quality of idea**: evidence first, then creative requirements, then media verification.
