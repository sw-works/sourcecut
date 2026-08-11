ALTER TABLE journal_entries MODIFY COLUMN raw_text String CODEC(ZSTD(3));
