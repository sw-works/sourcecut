---
name: SourceCut Archival OS
colors:
  surface: '#0e141c'
  surface-dim: '#0e141c'
  surface-bright: '#343a42'
  surface-container-lowest: '#090f16'
  surface-container-low: '#161c24'
  surface-container: '#1a2028'
  surface-container-high: '#242a33'
  surface-container-highest: '#2f353e'
  on-surface: '#dde3ee'
  on-surface-variant: '#d4c4b7'
  inverse-surface: '#dde3ee'
  inverse-on-surface: '#2b3139'
  outline: '#9c8e82'
  outline-variant: '#50453b'
  surface-tint: '#f0bd8b'
  primary: '#f2be8c'
  on-primary: '#482904'
  primary-container: '#d4a373'
  on-primary-container: '#5b3912'
  inverse-primary: '#7d562d'
  secondary: '#74db9d'
  on-secondary: '#00391f'
  secondary-container: '#00804c'
  on-secondary-container: '#d2ffde'
  tertiary: '#a6caff'
  on-tertiary: '#00315d'
  tertiary-container: '#71afff'
  on-tertiary-container: '#004178'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffdcbd'
  primary-fixed-dim: '#f0bd8b'
  on-primary-fixed: '#2c1600'
  on-primary-fixed-variant: '#623f18'
  secondary-fixed: '#91f8b8'
  secondary-fixed-dim: '#74db9d'
  on-secondary-fixed: '#002110'
  on-secondary-fixed-variant: '#00522f'
  tertiary-fixed: '#d4e3ff'
  tertiary-fixed-dim: '#a4c9ff'
  on-tertiary-fixed: '#001c39'
  on-tertiary-fixed-variant: '#004883'
  background: '#0e141c'
  on-background: '#dde3ee'
  surface-variant: '#2f353e'
  canvas-base: '#0B0F14'
  surface-panel: '#121820'
  surface-recessed: '#080B0E'
  surface-elevated: '#1A222D'
  border-subtle: '#1E293B'
  border-strong: '#334155'
  gold-parchment: '#E0A96D'
  gold-amber: '#F4A261'
  gold-deep: '#D4A373'
  matrix-active: '#F4A261'
  matrix-silent: '#263546'
  matrix-absent: '#0E141B'
  status-covered: '#2DD4BF'
  status-single-source: '#F59E0B'
  status-interpretive: '#64748B'
  text-primary: '#F1F5F9'
  text-secondary: '#94A3B8'
  text-muted: '#64748B'
typography:
  display-h1:
    fontFamily: Newsreader
    fontSize: 42px
    fontWeight: '400'
    lineHeight: 48px
    letterSpacing: -0.02em
  display-h1-mobile:
    fontFamily: Newsreader
    fontSize: 30px
    fontWeight: '400'
    lineHeight: 36px
    letterSpacing: -0.01em
  section-h2:
    fontFamily: Newsreader
    fontSize: 26px
    fontWeight: '400'
    lineHeight: 32px
    letterSpacing: -0.015em
  section-h2-mobile:
    fontFamily: Newsreader
    fontSize: 22px
    fontWeight: '400'
    lineHeight: 28px
  category-h3:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 18px
    letterSpacing: 0.08em
  journal-quote:
    fontFamily: Newsreader
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 23px
  body-default:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 21px
  body-muted:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 17px
  label-tabular:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.02em
  code-terminal:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 16px
  metric-stat:
    fontFamily: Newsreader
    fontSize: 34px
    fontWeight: '400'
    lineHeight: 38px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  step-xxs: 2px
  step-xs: 4px
  step-sm: 8px
  step-md: 12px
  step-base: 16px
  step-lg: 24px
  step-xl: 32px
  step-xxl: 48px
  gutter-dense: 12px
  gutter-default: 20px
  container-max: 1440px
---

## Brand & Style

### Brand Personality
The design system embodies the rigor of historical scholarship fused with the precision and speed of a cinematic production studio. It is forensic, authoritative, and obsessively transparent. Designed for historical researchers, production designers, screenwriters, and archival visualists, the interface strips away decorative superficiality in favor of undeniable documentary defensibility. Every assertion made on screen is tied back to primary journal quotes, precise calendar coordinates, institutional archive keys, or reproducible database executions.

### Aesthetic Movement & Visual Mood
The aesthetic combines **Archival Brutalism** with **Modern Forensic Minimalism**. It marries the tactile, ink-stained weight of 18th-and-19th-century expedition ledgers with the high-efficiency ergonomics of a modern query console. 

Key attributes:
- **Atmospheric Charcoal & Parchment Palette:** An ultra-dark, low-luminance canvas that evokes viewing rare manuscripts under conservation light, punctuated by archival parchment ambers, raw ochres, and muted expedition greens.
- **Tri-Tier Typography:** An intentional pairing of literary, bookish serifs for historical journal testimony, hyper-dense tabular monospace for timestamps, SQL statements, and offset coordinates, and an unobtrusive, razor-sharp sans-serif for functional UI controls.
- **Forensic Information Architecture:** Dense multi-column layouts, strict hairline dividers, metadata middle-dot chains (`Author · Date · Catalog ID`), and specialized visual data structures like the 22-day Journal Silence Matrix.

## Colors

### Color Philosophy
The color system operates on an archival low-reflectance paradigm. True pure white is eliminated from body surfaces to avoid harsh glare and maintain an intimate, document-inspection environment.

### Application Roles
- **Canvas Base (`#0B0F14`):** The ground level for the workspace. Everything rests on this pitch-slate foundation.
- **Surface Panel (`#121820`):** Applied to primary cards, research modules, citation rows, and data grids.
- **Surface Recessed (`#080B0E`):** Used for terminal logs, SQL traces, and interactive route tracks to create visual depth without high drop shadows.
- **Parchment Gold Accents (`#D4A373`, `#E0A96D`, `#F4A261`):** Serves as the primary chromatic brand accent. Reserved for active search prompts, direct passage highlights, primary callouts, and positive timeline presence.
- **Matrix Tiers:**
  - `matrix-active` (`#F4A261`): Explorer journal explicitly mentions the audit keyword on this specific date.
  - `matrix-silent` (`#263546`): Explorer wrote an entry on this date, but remained silent on the topic (critical historiographical signal).
  - `matrix-absent` (`#0E141B`): No journal entry exists for this explorer on this date.
- **Provenance Badging:**
  - `status-covered` (`#2DD4BF`): Multi-source verification achieved across requirements.
  - `status-single-source` (`#F59E0B`): Cautionary status indicating narrative reliance on only one observer.
  - `status-interpretive` (`#64748B`): Secondary or modern reconstruction (not contemporary primary proof).

## Typography

### Structural Hierarchy & Typographic Strategy
The system relies on three distinct font families to articulate information source and authority:

1. **Newsreader (Editorial & Historical):** Used for top-level philosophical directives, section titles, and verbatim primary quotes transcribed from expedition manuscripts. Its classical proportions evoke archival reading room catalogs.
2. **Inter (Operational & Structural):** Provides invisible, utilitarian legibility for navigational items, requirement criteria, card titles, and user inputs.
3. **JetBrains Mono (Forensic & Tabular):** Reserved for technical provenance—timestamps, ClickHouse trace steps, SQL commands, matrix day columns (`09` through `30`), and institutional catalog identifiers (`loc:mtjbib016499`).

### Rules for Quoted Evidence
Primary quotes rendered in `journal-quote` must preserve the original idiosyncratic spelling, punctuation, and capitalizations of the historical diarists (e.g., *"thro a plain"*, *"Colter's Creek"*). Quotes always feature a thin 2px gold accent border on the left or an italicized bookish treatment to separate them from modern user input.

## Layout & Spacing

### Grid & Density System
The layout is structured around an editorial 12-column high-density grid engineered for forensic workspace efficiency:
- **Maximum Container Width:** 1440px centered, allowing for expansive citation timelines without sacrificing line-length comfort.
- **Vertical Spacing Rhythm:** Driven by an 8px base rhythm. Tight groupings (e.g., metadata rows and matrix cell strips) leverage 2px and 4px micro-spacers.
- **Section Stack Rhythm:** 48px standard spacing between disparate investigation blocks (e.g., moving from Terrain into Weather, or from Evidence into Waypoint Reference).

### Multi-Tier Layout Panels
1. **Header & Query Console:** Full-width container housing the production brief textarea, active round counter, and database connection status pills.
2. **Scorecard Strip:** A 5-column or flexible flexbox grid displaying progress gauges, audit categories (`terrain`, `weather`, `food`, `health`, `transportation`), and keyword tags.
3. **Execution Trace Feed:** Single-column sequential stream with fixed left-hand tabular step indicators (`01`–`17`).
4. **Evidence & Citation Streams:** 3-column masonry/flex layouts for transcription excerpt cards, coupled directly beneath with the continuous 22-column heat-map matrix.
5. **Archive Gallery:** 3-to-4 column responsive grid for visual artifacts (manuscripts, hand-drawn route maps, photographic plates).

### Form Factor Adaptations
- **Desktop (1024px+):** Full multi-panel view. Matrix displays all 22 days horizontally without scroll.
- **Tablet (768px–1023px):** Trace feed and scorecard wrap into 2 columns. Timeline matrix enables subtle horizontal drag/scroll with sticky author labels (`Lewis`, `Gass`, `Clark`).
- **Mobile (<768px):** Single-column stacked cards. Query controls remain fixed or top-docked.

## Elevation & Depth

### Depth Philosophy
The interface uses **Tonal Layering with Crisp Hairline Outlines** instead of heavy, diffuse drop shadows. Because the background is a saturated dark slate (`#0B0F14`), depth is achieved through lightness gradation and subtle border contrast.

### Surface Tiers
- **Tier 0 (Base Ground):** `#0B0F14` — Background for the application shell.
- **Tier 1 (Panels & Dossiers):** `#121820` bordered with `1px solid #1E293B`. Houses citation cards, requirement blocks, and image tiles.
- **Tier 2 (Recessed Terminals & Visualizers):** `#080B0E` bordered with `1px solid #1A222D` with an inset shadow (`inset 0 1px 3px rgba(0,0,0,0.5)`). Used for the route map track, code execution log, and the timeline matrix background.
- **Tier 3 (Floating Overlays & Popovers):** `#1A222D` with `1px solid #334155` and a tight precision shadow (`0 4px 16px -2px rgba(0,0,0,0.6)`). Used for date-specific cell inspection cards and passage citation flyouts.

### Outlines & Boundaries
- All card borders use low-contrast slate hairlines (`#1E293B`).
- When a panel or citation is hovered or active, its border shifts to parchment gold (`#D4A373`) at 40% opacity, never completely jarring the user's focus.

## Shapes

### Shape Language
The system employs **Soft & Architectural (`roundedness: 1`)** geometry. Sharp, crisp corners anchor the serious, institutional feel, softened just enough (2px to 4px) to look refined on high-DPI displays.

### Radius Assignments
- **Evidence Cards, Panels, & Terminal Blocks:** `4px` (`rounded-sm`). Maintains structural alignment with the dense grid.
- **Buttons & Action Anchors:** `4px` (`rounded-sm`). Solid, deliberate, blocky.
- **Matrix Timeline Day Cells:** `2px`. Creates compact, brick-like data blocks that coalesce into solid visual bars of evidence.
- **Keyword Pills, Provenance Badges, & Offset Indicators:** Fully rounded `9999px` (Pill). Differentiates metadata tags and status indicators from structural cards.

## Components

### 1. Query & Brief Input Console
- **Textarea Container:** Recessed dark slate background (`#080B0E`) with an active amber glow outline when focused.
- **Top Metadata Bar:** Houses the expedition indicator, session counter (`ROUND 1 OF 3`), and a green status dot with the label `CLICKHOUSE MCP: READ-ONLY`.
- **Primary Action Button:** Background `#E0A96D`, text `#0B0F14`, font `Inter` 600, uppercase letter-spacing. On hover, shifts to `#F4A261`.

### 2. Criterion Scorecard & Status Indicators
- **Category Header:** Small caps font `Inter` bold with a status indicator positioned directly above or beside it.
- **Badges:**
  - `COVERED`: Pill-shaped badge, background `rgba(45, 212, 191, 0.12)`, text `#2DD4BF`, border `1px solid rgba(45, 212, 191, 0.3)`.
  - `1/3 ONE AUTHOR ONLY`: Pill-shaped badge, background `rgba(245, 158, 11, 0.12)`, text `#F59E0B`, border `1px solid rgba(245, 158, 11, 0.3)`.
- **Keyword Chips:** Inline dark pills (`#1A222D`), border `#334155`, text `#94A3B8`, padding `2px 8px`, `JetBrains Mono` 11px.

### 3. Execution Trace Log
- **Feed Item:** A structured row with step numbers (`01`, `02`, ..., `17`) in monospace amber, followed by tool calls (e.g., `MCP TOOL CALL: Clickhouse MCP returned 200 rows`) and latency metrics right-aligned in muted grey.
- **SQL Drawer:** Collapsible panel with background `#080B0E`, displaying syntax-highlighted SQL with syntax tokens in warm ochre, muted cyan, and parchment white.

### 4. Citation Excerpt Cards & Author Silence Matrix
- **Excerpt Card:** Surface `#121820`, hairline border `#1E293B`, with an italicized excerpt in `Newsreader`. Below the quote, a metadata row displays: `Author · Date · Archive Source · passage ID` formatted in `Inter` and `JetBrains Mono`.
- **Timeline Matrix:**
  - Row labels: `Lewis`, `Gass`, `Clark` in monospace tabular.
  - Column headers: Days `09` through `30`.
  - Matrix cell: 14px x 18px block. Gold (`#F4A261`) for keyword mention; deep slate (`#263546`) for silent entry; near-black (`#0E141B`) for absent entry.
  - Legend: Placed beneath the matrix with sample filled micro-boxes matching state tokens.

### 5. Waypoint Reference & Route Map
- **Canvas:** Dark map vector canvas with dashed yellow/amber historical paths and circular milestone pins (`Lolo Creek`, `Packers Meadow`, `Lolo Pass`).
- **Coordinate Callout:** Bottom bar displaying historical date range, modern NPS reference coordinates disclaimer, and scholarly attribution.

### 6. Archive Reference Gallery
- **Thumbnail Cards:** Deep card container displaying historical cartography, scanned correspondence, or period landscape photographs.
- **Provenance Stamp:** Positioned at the top of the card thumbnail:
  - `HIGH`: Confirmed primary evidence.
  - `INTERPRETIVE · NOT EXPEDITION PROOF`: Educational reconstructions or later-dated materials.
  - `SINGLE SOURCE`: Needs collaborative corroboration.
- **Card Action Trigger:** Subtle right-arrow link (`Create previs →`) set in gold parchment typography with hover transition.