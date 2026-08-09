# Data Acquisition Specification

## 1. Primary journal corpus

Initial distributable corpus: Project Gutenberg eBook 8419, *The Journals of Lewis and Clark, 1804–1806*.

Use it because:
- public-domain US text;
- complete expedition coverage in a convenient electronic edition;
- headings identify author/date deterministically.

Preserve known limitations in `sources` metadata:
- edited/transcribed edition, not a diplomatic manuscript transcription;
- some material omitted by the edition;
- occasional OCR/transcription issues may exist.

### Parsing

Recognize headings similar to:

```regex
^\[(Lewis|Clark), ([A-Za-z]+) ([0-9]{1,2}), (180[3-6])\]$
```

Each heading begins a new journal entry. Preserve same-date entries separately.

## 2. Scholarly validation source

University of Nebraska's Journals of the Lewis & Clark Expedition may be used for manual validation and historical cross-checking.

Do not redistribute its editorial text as the app's source corpus without permission.

## 3. Media Source — Library of Congress

Role:
- expedition maps;
- manuscripts;
- historic imagery;
- documents.

Ingest via public structured APIs and cache results.

Preserve:
- provider ID;
- raw JSON;
- source URL;
- media URL;
- contributors;
- dates;
- subjects;
- locations;
- rights text.

Do not assume all LOC items are public domain; use item-level rights information.

## 4. Media Source — Smithsonian Open Access

Role:
- CC0 material culture;
- natural-history objects;
- artifacts;
- visual references.

Only ingest reusable media automatically when the record is explicitly open/CC0.

Restricted items may be retained metadata-only if useful for research.

## 5. Media Source — National Park Service

Role:
- modern location references;
- Fort Clatsop/environmental references;
- interpretive/replica material.

NPS material must preserve relationship labels such as:
- representative;
- replica;
- modern reference;
- archaeological;
- direct provenance if established.

Never present a representative/replica object as expedition-owned.

Rights are per item; do not assume all NPS images are automatically reusable.

## 6. Normalized media schema

Required fields:
- `asset_id`;
- `provider`;
- `provider_id`;
- `title`;
- `description`;
- `creator[]`;
- `asset_type`;
- `creation_date_text`;
- `creation_year`;
- `subjects[]`;
- `places[]`;
- `source_url`;
- `media_url`;
- `rights_status`;
- `rights_text`;
- `historical_relationship`;
- `raw_metadata`.

## 7. Rights taxonomy

- `public_domain`
- `cc0`
- `reusable_with_conditions`
- `rights_unclear`
- `restricted`

Default board mode should favor public-domain/CC0 material.

## 8. Historical relationship taxonomy

- `PRIMARY`
- `NEAR_CONTEMPORARY`
- `PERIOD_COMPARATIVE`
- `LATER_REPRESENTATION`
- `MODERN_REFERENCE`
- `REPLICA`
- `UNKNOWN`

## 9. Initial target volumes

Engineering targets only:
- full Lewis/Clark journal corpus;
- LOC: roughly 500–2,000 relevant records;
- Smithsonian: roughly 1,000–5,000 selected open records;
- NPS: roughly 100–500 carefully curated records.

Stop when the demo has enough diversity; do not ingest irrelevant volume for its own sake.
