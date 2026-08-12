CREATE ROLE IF NOT EXISTS sourcecut_mcp_role;

ALTER ROLE sourcecut_mcp_role SETTINGS
    readonly = 2,
    max_execution_time = 10,
    max_result_rows = 500,
    result_overflow_mode = 'throw',
    max_result_bytes = 2000000,
    max_rows_to_read = 1000000,
    max_concurrent_queries_for_user = 4;

CREATE ROW POLICY IF NOT EXISTS sourcecut_mcp_observations_trusted
ON sourcecut.observations
USING trusted = 1 AND validation_status = 'valid'
TO sourcecut_mcp_role;

CREATE ROW POLICY IF NOT EXISTS sourcecut_admin_observations_all
ON sourcecut.observations
USING 1
TO ALL EXCEPT sourcecut_mcp_role;

CREATE ROW POLICY IF NOT EXISTS sourcecut_mcp_entity_mentions_trusted
ON sourcecut.entity_mentions
USING trusted = 1 AND validation_status = 'valid'
TO sourcecut_mcp_role;

CREATE ROW POLICY IF NOT EXISTS sourcecut_admin_entity_mentions_all
ON sourcecut.entity_mentions
USING 1
TO ALL EXCEPT sourcecut_mcp_role;

GRANT SELECT ON sourcecut.odyssey_text_lookup_v TO sourcecut_mcp_role;
GRANT SELECT ON sourcecut.odyssey_passage_context_v TO sourcecut_mcp_role;
GRANT SELECT ON sourcecut.odyssey_lemma_occurrences_v TO sourcecut_mcp_role;
GRANT SELECT ON sourcecut.odyssey_text_search_v TO sourcecut_mcp_role;
GRANT SELECT ON sourcecut.odyssey_formula_occurrences_v TO sourcecut_mcp_role;
GRANT SELECT ON sourcecut.odyssey_trusted_claim_evidence_v TO sourcecut_mcp_role;
GRANT SELECT ON sourcecut.odyssey_claim_source_v TO sourcecut_mcp_role;
GRANT SELECT ON sourcecut.odyssey_scholarly_source_v TO sourcecut_mcp_role;
GRANT SELECT ON sourcecut.odyssey_event_timeline_v TO sourcecut_mcp_role;
GRANT SELECT ON sourcecut.odyssey_speeches_v TO sourcecut_mcp_role;
GRANT SELECT ON sourcecut.odyssey_event_passages_v TO sourcecut_mcp_role;
GRANT SELECT ON sourcecut.odyssey_map_features_v TO sourcecut_mcp_role;
GRANT SELECT ON sourcecut.odyssey_entity_occurrences_v TO sourcecut_mcp_role;
GRANT SELECT ON sourcecut.odyssey_theme_passages_v TO sourcecut_mcp_role;
GRANT SELECT ON sourcecut.odyssey_visual_assets_v TO sourcecut_mcp_role;
GRANT SELECT ON sourcecut.evidence_window TO sourcecut_mcp_role;
GRANT SELECT ON sourcecut.author_term_presence TO sourcecut_mcp_role;
GRANT SELECT ON sourcecut.author_date_matrix TO sourcecut_mcp_role;
GRANT SELECT ON sourcecut.entity_mentions_window TO sourcecut_mcp_role;
GRANT SELECT ON sourcecut.passage_lookup TO sourcecut_mcp_role;
GRANT SELECT ON sourcecut.passages TO sourcecut_mcp_role;
GRANT SELECT ON sourcecut.observations TO sourcecut_mcp_role;
GRANT SELECT ON sourcecut.entity_mentions TO sourcecut_mcp_role;
GRANT SELECT ON sourcecut.media_assets TO sourcecut_mcp_role;
GRANT SELECT ON system.tables TO sourcecut_mcp_role;
GRANT SELECT ON system.columns TO sourcecut_mcp_role;
