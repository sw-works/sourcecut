ALTER TABLE passages ADD COLUMN IF NOT EXISTS embedding_model LowCardinality(String) DEFAULT '' AFTER embedding;
