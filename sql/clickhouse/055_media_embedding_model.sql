ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS embedding_model LowCardinality(String) DEFAULT '' AFTER embedding;
