# Demo UI design

Source for the SourceCut demo interface, authored as Design Components and published as a
canvas: <https://claude.ai/code/artifact/4e715a5d-ddc2-419a-90cc-677b093cf704>

## Screens

The chosen direction is **Cutting Room** — letterboxed frame, Instrument Serif over Archivo,
coverage as a filmstrip, the gap round as a lower third.

| File | Screen |
|---|---|
| `Landing.dc.html` | What a visitor sees before running anything: the input, then a prerendered worked example |
| `Brief.dc.html` | The compose state, with the five curated corpus segments alongside |
| `Main.dc.html` | The run — the second research round firing, with the live trace |
| `Board.dc.html` | The finished board: references, confidence, the unmet requirement |
| `Evidence.dc.html` | Drill-down: the whole passage with the claimed span highlighted in place |

`CuttingRoom.dc.html`, `FieldDossier.dc.html` and `ControlRoom.dc.html` are the three original
direction sketches, kept for the record on the canvas's second page. C was chosen.

## What is real in these mockups

Real: the journal text and passage ids (Project Gutenberg 8419), the character offsets
(600–653 of 725 in Clark's 18 September 1805 entry), the five corpus segments from
`data/reference/research_scopes.json`, and the four Library of Congress records with their
ids, dates and cached thumbnails.

Sample values: row counts, latencies, the session id, the passage hash, and the per-category
citation counts.

## Regenerating the canvas

The canvas is assembled by the `design` skill's seeding helper from these working files. The
seeded `sourcecut-demo-ui.html` is a build artifact (~2.6 MB, the editor is baked into it) and
is not committed — edit the `.dc.html` files and `canvas.json`, then re-seed and republish to
the same artifact URL.
