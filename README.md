# SourceCut

SourceCut is an agentic research producer for historically grounded film and documentary production.

The initial demo corpus is the Lewis & Clark Expedition (1804–1806). A filmmaker asks for a historically grounded visual research board; SourceCut investigates primary sources, derives evidence-backed production requirements, finds candidate media assets, verifies them, and produces a board where recommendations trace back to evidence.

## Hackathon architecture

- **Gemini + Google ADK**: research planning, interpretation, multimodal inspection, verification.
- **ClickHouse**: primary-source evidence store, analytical retrieval, cross-author comparison, media catalog, research events.
- **Grafana + OpenTelemetry**: ingestion and agent observability.
- **FastAPI**: backend API.
- **Next.js + TypeScript**: frontend.
- **Google Cloud Run**: backend deployment target.

## Core invariant

Historical claims shown to users must be grounded in stored source passages. Gemini may guide search, but model memory is never treated as evidence.

## Start here

1. Read `AGENTS.md`.
2. Read `docs/hackathon-build/decisions.md`.
3. Implement tasks in numeric order from `tasks/`.
4. Do not begin serious media ingestion until Task 008 acceptance criteria pass.
