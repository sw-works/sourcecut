ALTER TABLE passages ADD PROJECTION by_passage_id (SELECT * ORDER BY passage_id);
