ALTER TABLE passages ADD COLUMN IF NOT EXISTS embedding Array(Float32) DEFAULT [] AFTER passage_sha256;
