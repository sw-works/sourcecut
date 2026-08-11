ALTER TABLE media_assets MODIFY COLUMN ingested_at DateTime64(3, 'UTC') DEFAULT now64(3) CODEC(Delta, ZSTD);
