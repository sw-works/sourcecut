CREATE VIEW IF NOT EXISTS odyssey_visual_assets_v AS
SELECT a.asset_id, a.provider, a.provider_id, a.title, a.description, a.creators,
       a.asset_type, a.creation_date_text, a.subjects, a.source_url, a.media_url,
       a.thumbnail_path, a.rights_status, a.rights_text, a.raw_metadata,
       m.institution, m.object_id, m.culture, m.period, m.object_date,
       m.object_begin_date, m.object_end_date, m.medium, m.image_rights_status,
       m.image_attribution, m.cached_image_path, m.public_display,
       r.relationship_class, r.production_use, r.limitations, r.evidence_ids,
       r.confidence, r.verification_status,
       groupArray((l.target_kind, l.target_id)) AS corpus_links
FROM media_assets AS a FINAL
INNER JOIN odyssey_asset_metadata AS m FINAL ON m.asset_id = a.asset_id
INNER JOIN asset_relationship_assessments AS r FINAL ON r.asset_id = a.asset_id
LEFT JOIN asset_corpus_links AS l FINAL ON l.asset_id = a.asset_id
WHERE r.review_status = 'trusted'
GROUP BY a.asset_id, a.provider, a.provider_id, a.title, a.description, a.creators,
         a.asset_type, a.creation_date_text, a.subjects, a.source_url, a.media_url,
         a.thumbnail_path, a.rights_status, a.rights_text, a.raw_metadata,
         m.institution, m.object_id, m.culture, m.period, m.object_date,
         m.object_begin_date, m.object_end_date, m.medium, m.image_rights_status,
         m.image_attribution, m.cached_image_path, m.public_display,
         r.relationship_class, r.production_use, r.limitations, r.evidence_ids,
         r.confidence, r.verification_status;
