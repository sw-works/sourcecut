ALTER TABLE journal_entries MODIFY COLUMN entry_date Int32 CODEC(Delta, ZSTD);
