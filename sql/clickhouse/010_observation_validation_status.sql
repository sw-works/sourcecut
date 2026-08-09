ALTER TABLE observations
ADD COLUMN IF NOT EXISTS validation_status LowCardinality(String) DEFAULT 'invalid'
AFTER trusted;
