# Library of Congress media ingestion

Task 010 uses the public LOC JSON API for offline harvesting and `clickhouse-connect` for loading.
No LOC API key is required. The runtime research path does not call LOC.

Run the ingestion with the administrative ClickHouse credentials:

```bash
uv run --env-file .env.admin.local python -m pipelines.media
```

For a smaller smoke run:

```bash
uv run --env-file .env.admin.local python -m pipelines.media --max-items 3
```

Raw search and item responses are written once under `data/archive-cache/loc`. Approved thumbnails
are cached there only when item-level rights are explicitly reusable. A changed response never
overwrites an existing cache file; retain the old cache for provenance or start a separately named
cache directory.

Useful local checks after loading:

```sql
SELECT rights_status, asset_type, count()
FROM media_assets
GROUP BY rights_status, asset_type
ORDER BY rights_status, asset_type;

SELECT asset_id, title, creation_year, rights_status, thumbnail_path
FROM media_assets
WHERE provider = 'Library of Congress'
  AND rights_status IN ('public_domain', 'cc0', 'reusable_with_conditions')
ORDER BY creation_year, asset_id
LIMIT 50;
```
