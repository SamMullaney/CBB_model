"""Repository: DB write functions for games and prices.

Uses SQLAlchemy Core (text()) — no ORM models required.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import TypedDict

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ── Input shapes ──────────────────────────────────────────────────────

class GameRow(TypedDict):
    external_game_id: str
    sport_key: str
    commence_time: datetime
    home_team: str
    away_team: str


class PriceRow(TypedDict):
    external_game_id: str          # resolved to game_id inside the function
    captured_at: datetime
    bookmaker: str
    market: str                    # h2h | spreads | totals
    outcome: str                   # team name, "Over", "Under"
    line: float | Decimal | None   # spread / total; None for h2h
    odds_american: int | None
    odds_decimal: float | Decimal | None


# ── SQL ───────────────────────────────────────────────────────────────

_UPSERT_GAME = text("""
    INSERT INTO games (external_game_id, sport_key, commence_time, home_team, away_team)
    VALUES (:external_game_id, :sport_key, :commence_time, :home_team, :away_team)
    ON CONFLICT (external_game_id) DO UPDATE SET
        commence_time = EXCLUDED.commence_time,
        home_team     = EXCLUDED.home_team,
        away_team     = EXCLUDED.away_team
    RETURNING id
""")

_INSERT_PRICE = text("""
    INSERT INTO prices (game_id, captured_at, bookmaker, market, outcome,
                        line, odds_american, odds_decimal)
    VALUES (:game_id, :captured_at, :bookmaker, :market, :outcome,
            :line, :odds_american, :odds_decimal)
    ON CONFLICT ON CONSTRAINT uq_prices_snapshot DO NOTHING
""")


# ── Public function ───────────────────────────────────────────────────

def insert_games_and_prices(
    db: Session,
    games: list[GameRow],
    prices: list[PriceRow],
) -> dict[str, int]:
    """Upsert games then insert price rows in a single transaction.

    Args:
        db: SQLAlchemy Session (caller manages the session lifecycle).
        games: Game rows to upsert.
        prices: Price rows to insert (linked via external_game_id).

    Returns:
        {"games_upserted": N, "prices_inserted": N}
    """
    # 1) Upsert games, collect external_game_id -> internal id mapping
    id_map: dict[str, int] = {}
    for g in games:
        row = db.execute(_UPSERT_GAME, g).fetchone()
        id_map[g["external_game_id"]] = row[0]

    # 2) Insert prices, resolving external_game_id to game_id
    prices_inserted = 0
    for p in prices:
        game_id = id_map.get(p["external_game_id"])
        if game_id is None:
            logger.warning(
                "Skipping price row — no game for external_game_id=%s",
                p["external_game_id"],
            )
            continue

        result = db.execute(_INSERT_PRICE, {
            "game_id": game_id,
            "captured_at": p["captured_at"],
            "bookmaker": p["bookmaker"],
            "market": p["market"],
            "outcome": p["outcome"],
            "line": p["line"],
            "odds_american": p["odds_american"],
            "odds_decimal": p["odds_decimal"],
        })
        prices_inserted += result.rowcount

    db.commit()

    counts = {"games_upserted": len(id_map), "prices_inserted": prices_inserted}
    logger.info("insert_games_and_prices: %s", counts)
    return counts
