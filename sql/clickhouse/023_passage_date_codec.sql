ALTER TABLE passages MODIFY COLUMN entry_date Int32 CODEC(Delta, ZSTD);
