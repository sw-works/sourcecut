ALTER TABLE research_events ADD COLUMN IF NOT EXISTS duration_ms UInt32 DEFAULT 0 AFTER payload_json;
