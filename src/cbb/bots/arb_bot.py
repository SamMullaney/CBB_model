"""Arb bot: fetch → normalize → store → detect arbs → alert.

Orchestration only — no heavy math, no direct SQL.
"""

from __future__ import annotations

import asyncio
import logging

from cbb.alerts.discord import format_arb_message, send_discord
from cbb.clients.odds_api import fetch_odds
from cbb.config.settings import settings
from cbb.db.repo import (
    get_latest_prices,
    insert_games_and_prices,
    is_alert_sent,
    mark_alert_sent,
)
from cbb.db.session import SessionLocal
from cbb.ingestion.odds_ingest import normalize_odds, prepare_for_db
from cbb.pricing.arb import arb_fingerprint, find_h2h_arbs

logger = logging.getLogger(__name__)

SPORT = "basketball_ncaab"


def run_once() -> None:
    """Execute one fetch → normalize → store → scan → alert cycle."""

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

        # 4) Detect arbs on the latest snapshot
        latest = get_latest_prices(db)
        arbs = find_h2h_arbs(latest)
        logger.info("Arb scan: %d opportunities found", len(arbs))

        # 5) Alert (deduplicated)
        if arbs and settings.discord_webhook_url:
            for opp in arbs:
                fp = arb_fingerprint(opp)
                if is_alert_sent(db, fp):
                    logger.debug("Arb %s already alerted, skipping", fp)
                    continue

                msg = format_arb_message(opp)
                try:
                    send_discord(settings.discord_webhook_url, msg)
                    mark_alert_sent(db, fp)
                    logger.info("Alerted arb %s (%.2f%%)", fp, opp.arb_percent * 100)
                except Exception:
                    logger.exception("Failed to send Discord alert for %s", fp)
        elif arbs:
            logger.warning(
                "%d arbs found but DISCORD_WEBHOOK_URL is not set — skipping alerts",
                len(arbs),
            )

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
