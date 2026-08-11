# Task 022 — Expedition Map and Timeline View

## Goal

Give the Sept 1805 corpus a spatial spine: a self-contained route map plus date scrubber.
Click a date or waypoint → that day's per-author evidence and matched media.

## Read first
- `docs/hackathon-build/decisions.md` (ADR-009: demo must not depend on external APIs —
  this rules out tile servers; new ADR-017 covers route reference data)
- `apps/web/app/page.tsx`, `apps/web/app/globals.css` (design system to extend)
- `tasks/021-cross-author-agreement.md` (per-date evidence queries to reuse)

## Background

Journals are inherently geospatial and the Bitterroot crossing is a famous route segment
(Lost Trail Pass → Lolo Trail → Weippe Prairie). Coordinates are not in the corpus, so route
data is **curated reference data with citations**, never presented as extracted evidence —
same standing as the entity registry (ADR-017 formalizes this class of data).

## Scope

### Route reference data

- `data/reference/route_sept_1805.json`, committed, human-curated: ordered waypoints with
  `waypoint_id`, `entry_date` (Int32 key convention), `name`, `lat`, `lon`,
  `citation_passage_ids` (passages that place the party there), `source_note` (scholarly
  reference used for coordinates, e.g. published trail maps — named, since coordinates
  themselves are modern reference values).
- Migration: `route_waypoints` table (`ReplacingMergeTree(updated_at)`,
  `ORDER BY (entry_date, waypoint_id)`) + loader CLI `sourcecut-load-route`; readable through
  MCP like all reference tables.

### UI

- New board section "Route" on the main page: inline SVG map (hand-projected from the
  waypoint coordinates with a simple equirectangular transform — no tiles, no external
  requests, works offline per ADR-009), route polyline, waypoint markers sized by that day's
  trusted-evidence count.
- Date scrubber (range = corpus window) synchronized with: waypoint highlight, per-author
  entry summary for the selected date, media assets whose match window covers the date.
- Waypoint click → existing passage inspector with the citation passages.
- Map is decorative-terrain-free: labeled river/pass names as SVG text only where a waypoint
  references them. Required caption: route positions are modern scholarly reference data,
  cited per waypoint — not extracted evidence.
- Responsive: map collapses to a vertical route strip below 48rem; scrubber becomes a native
  range input; `prefers-reduced-motion` honored for scrub animations.

### API

- Waypoints + per-date summaries embedded in the board payload (computed during board build
  via MCP queries), keeping the page one-fetch after `done`.

## Do not
- fetch map tiles, fonts, or geo data from any external host at runtime;
- geocode with an LLM or infer coordinates from journal text (curated file only);
- block board completion on route data (missing file → section absent, board still valid).

## Acceptance criteria

1. Canonical prompt renders the route with ≥8 waypoints spanning Sept 9–30 1805, each
   citing at least one real passage id that resolves in the inspector.
2. Scrubbing to Sept 16 highlights the snow-day evidence from both authors (the demo's
   marquee fact) and any matched media.
3. Zero external network requests from the map (verified via browser devtools network log,
   noted in summary; Playwright check if practical).
4. Mobile layout passes the existing Playwright visual checks pattern
   (`output/playwright/` screenshots regenerated).
5. Waypoint table loads idempotently; MCP can read it; agent allowlist updated only if the
   agent is given route query patterns (optional — decide and document).
