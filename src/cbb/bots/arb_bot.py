"""Arb bot: fetch → normalize → store.

Orchestration only — no heavy math, no direct SQL.
"""

from __future__ import annotations

import asyncio
import logging

from cbb.clients.odds_api import fetch_odds
from cbb.db.repo import insert_games_and_prices
from cbb.db.session import SessionLocal
from cbb.ingestion.odds_ingest import normalize_odds, prepare_for_db

logger = logging.getLogger(__name__)

SPORT = "basketball_ncaab"


def run_once() -> None:
    """Execute one fetch → normalize → store cycle."""

    # 1) Fetch
    logger.info("Fetching odds for %s …", SPORT)
    events = asyncio.run(fetch_odds(sport=SPORT))
    logger.info("Received %d events", len(events))

    if not events:
        logger.info("No events returned — nothing to store.")
        return

    # 2) Normalize
    odds_rows = normalize_odds(events)
    logger.info("Normalized into %d odds rows", len(odds_rows))

    games, prices = prepare_for_db(odds_rows, sport_key=SPORT)
    logger.info("Prepared %d games, %d prices for DB", len(games), len(prices))

    # 3) Store
    db = SessionLocal()
    try:
        counts = insert_games_and_prices(db, games, prices)
        logger.info("Stored: %s", counts)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
