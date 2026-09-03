ALTER TABLE source_repositories
ADD COLUMN IF NOT EXISTS rights_match LowCardinality(String) DEFAULT 'value' AFTER rights_field;
