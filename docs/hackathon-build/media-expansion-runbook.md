# Media expansion runbook

Set `SMITHSONIAN_API_KEY` and `NPS_API_KEY` in ignored local environment files. Smoke-test with:

```bash
uv run --env-file .env.admin.local --env-file .env.smithsonian.local sourcecut-harvest-smithsonian --max-items 3
uv run --env-file .env.admin.local --env-file .env.nps.local sourcecut-harvest-nps --max-items 3
```

Full harvest and embedding backfill:

```bash
uv run --env-file .env.admin.local --env-file .env.smithsonian.local sourcecut-harvest-smithsonian
uv run --env-file .env.admin.local --env-file .env.nps.local sourcecut-harvest-nps
uv run --env-file .env.admin.local --env-file .env.gemini.local sourcecut-embed
```

Smithsonian query curation lives in `data/curation/smithsonian-media-queries.json`.
Smithsonian stores only media explicitly marked CC0 and maps that explicit dedication to
`public_domain`. NPS stores only item metadata that states public domain, National Park Service
authorship, or U.S. Government authorship. Both CLIs report rejected-rights counts; ambiguous items
are never loaded. Approved thumbnails and raw API responses are cached under `data/archive-cache/`.
The demo reads only ClickHouse and the local cache, never either live API.

Post-load verification:

```sql
SELECT provider, rights_status, count() AS assets
FROM media_assets FINAL
GROUP BY provider, rights_status
ORDER BY provider, rights_status;

SELECT provider, countIf(length(embedding) = 768) AS embedded, count() AS total
FROM media_assets FINAL
GROUP BY provider
ORDER BY provider;
```
