-- 030_games_composite_unique.sql
-- Change games unique index from (external_game_id) to (sport_key, external_game_id)
-- Safe to run on a live DB with existing data.

DROP INDEX IF EXISTS uq_games_external_id;

CREATE UNIQUE INDEX IF NOT EXISTS uq_games_sport_external_id
    ON games (sport_key, external_game_id);
