CREATE VIEW IF NOT EXISTS odyssey_map_features_v AS
SELECT i.identification_id, i.poetic_place_id, p.canonical_name, p.place_class,
       i.hypothesis_id, i.identification_class, i.longitude, i.latitude,
       i.confidence, i.status, i.rationale, i.scholarly_source_ids
FROM place_identifications FINAL AS i
INNER JOIN poetic_places FINAL AS p ON p.poetic_place_id = i.poetic_place_id
WHERE i.review_status = 'trusted' AND p.review_status = 'trusted';
