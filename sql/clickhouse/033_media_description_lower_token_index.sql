ALTER TABLE media_assets ADD INDEX idx_media_description_lower_tokens lower(description) TYPE tokenbf_v1(8192, 3, 0) GRANULARITY 4;
