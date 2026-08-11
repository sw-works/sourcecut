ALTER TABLE passages ADD INDEX idx_passage_text_lower_tokens lower(passage_text) TYPE tokenbf_v1(8192, 3, 0) GRANULARITY 4;
