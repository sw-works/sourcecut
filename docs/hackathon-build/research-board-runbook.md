# Research board runtime

Build the canonical board through the authenticated official ClickHouse MCP server and perform up
to two Gemini inspections of cached thumbnails:

```bash
uv run \
  --env-file .env.mcp.local \
  --env-file .env.gemini.local \
  python -m sourcecut_api.services.board \
  "Build a historically grounded visual research board for the Corps of Discovery crossing the Bitterroot Mountains in September 1805."
```

Add `--summary` for the demo preflight or `--skip-visual-inspection` when Gemini image inspection
is unavailable. The board still uses ClickHouse MCP in both modes. Optional visual failures leave
metadata-matched assets at `INTERPRETIVE` confidence rather than aborting the board.

Confidence labels:

- `HIGH`: reusable, metadata-matched, near-contemporary asset backed by two journal authors;
- `SINGLE_SOURCE`: same, backed by one journal author;
- `INTERPRETIVE`: useful later/comparative reference, never presented as expedition proof;
- `UNSUPPORTED`: metadata or visual inspection does not support the requirement;
- `RIGHTS_REJECTED`: item-level rights are not explicitly reusable.

Every evidence-derived requirement includes exact stored passage IDs, author/date metadata, and
verbatim source excerpts for drill-down. Runtime execution never calls LOC.
