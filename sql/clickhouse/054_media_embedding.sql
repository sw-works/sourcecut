ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS embedding Array(Float32) DEFAULT [] AFTER metadata_sha256;
