ALTER TABLE term_expansions
ADD COLUMN IF NOT EXISTS provenance LowCardinality(String) DEFAULT 'curated' AFTER notes;
