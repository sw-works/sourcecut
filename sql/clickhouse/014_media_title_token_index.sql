ALTER TABLE media_assets ADD INDEX idx_media_title_tokens title TYPE tokenbf_v1(8192, 3, 0) GRANULARITY 4;
