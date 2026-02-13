-- 010_tables.sql  –  Minimal odds-snapshot schema
-- Postgres 16 compatible, idempotent (IF NOT EXISTS everywhere)

-- ── games ────────────────────────────────────────────────────────────
-- One row per unique event from The Odds API.
-- Uses bigserial PK: these IDs are internal-only, never leave the
-- system, so 8-byte ints are smaller and faster for joins/indexes
-- than 16-byte UUIDs.  The Odds API's own id lives in external_game_id.

CREATE TABLE IF NOT EXISTS games (
    id                bigserial       PRIMARY KEY,
    external_game_id  text            NOT NULL,
    sport_key         text            NOT NULL,
    commence_time     timestamptz     NOT NULL,
    home_team         text            NOT NULL,
    away_team         text            NOT NULL,
    created_at        timestamptz     NOT NULL DEFAULT now()
);

-- One row per game per sport from the API; upsert-friendly
CREATE UNIQUE INDEX IF NOT EXISTS uq_games_sport_external_id
    ON games (sport_key, external_game_id);

-- ── prices ───────────────────────────────────────────────────────────
-- One row per bookmaker × market × outcome per capture batch.

CREATE TABLE IF NOT EXISTS prices (
    id              bigserial       PRIMARY KEY,
    game_id         bigint          NOT NULL REFERENCES games (id),
    captured_at     timestamptz     NOT NULL DEFAULT now(),
    bookmaker       text            NOT NULL,
    market          text            NOT NULL,   -- h2h | spreads | totals
    outcome         text            NOT NULL,   -- team name, "Over", "Under"
    line            numeric,                    -- spread / total number; NULL for h2h
    odds_american   int,
    odds_decimal    numeric,
    CONSTRAINT uq_prices_snapshot
        UNIQUE (game_id, captured_at, bookmaker, market, outcome)
);

-- Fast lookup: latest prices per game/market/book/outcome
CREATE INDEX IF NOT EXISTS ix_prices_latest
    ON prices (game_id, market, bookmaker, outcome, captured_at DESC);
