ALTER TABLE passages MODIFY COLUMN created_at DateTime64(3, 'UTC') DEFAULT now64(3) CODEC(Delta, ZSTD);
