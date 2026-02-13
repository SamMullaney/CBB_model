"""Arb bot: fetch → normalize → store → detect arbs → alert.

Orchestration only — no heavy math, no direct SQL.
Loops over all sports defined in config.sports.SPORTS.
"""

from __future__ import annotations

import asyncio
import logging

from cbb.alerts.discord import format_arb_message, send_discord
from cbb.clients.odds_api import fetch_odds
from cbb.config.settings import settings
from cbb.config.sports import SPORTS
from cbb.db.repo import (
    get_latest_prices,
    insert_games_and_prices,
    is_alert_sent,
    mark_alert_sent,
)
from cbb.db.session import SessionLocal
from cbb.ingestion.odds_ingest import normalize_odds, prepare_for_db
from cbb.pricing.arb import arb_fingerprint, find_all_arbs

logger = logging.getLogger(__name__)


def _fetch_and_store(sport: str) -> int:
    """Fetch, normalize, and store odds for a single sport.

    Returns the number of prices inserted.
    """
    logger.info("[%s] Fetching odds …", sport)
    events = asyncio.run(fetch_odds(sport=sport))
    logger.info("[%s] Received %d events", sport, len(events))

    if not events:
        return 0

    odds_rows = normalize_odds(events)
    games, prices = prepare_for_db(odds_rows, sport_key=sport)
    logger.info("[%s] Prepared %d games, %d prices", sport, len(games), len(prices))

    db = SessionLocal()
    try:
        counts = insert_games_and_prices(db, games, prices)
        logger.info("[%s] Stored: %s", sport, counts)
        return counts["prices_inserted"]
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _scan_and_alert_sport(db, sport: str) -> int:
    """Run arb detection for one sport and send new alerts. Returns arb count."""
    latest = get_latest_prices(db, sport)
    if not latest:
        return 0

    arbs = find_all_arbs(latest)
    if not arbs:
        return 0

    logger.info("[%s] Arb scan: %d opportunities", sport, len(arbs))

    if settings.discord_webhook_url:
        for opp in arbs:
            fp = arb_fingerprint(opp)
            if is_alert_sent(db, fp):
                continue
            msg = format_arb_message(opp)
            try:
                send_discord(settings.discord_webhook_url, msg)
                mark_alert_sent(db, fp)
                logger.info("[%s] Alerted arb %s (%.2f%%)", sport, fp, opp.arb_percent * 100)
            except Exception:
                logger.exception("[%s] Failed to send alert for %s", sport, fp)
    else:
        logger.warning(
            "[%s] %d arbs found but DISCORD_WEBHOOK_URL is not set",
            sport, len(arbs),
        )

    return len(arbs)


def run_once() -> None:
    """Execute one full cycle across all configured sports."""
    total_prices = 0
    for sport in SPORTS:
        try:
            total_prices += _fetch_and_store(sport)
        except Exception:
            logger.exception("Failed to fetch/store %s — continuing", sport)

    logger.info("Total prices stored across %d sports: %d", len(SPORTS), total_prices)

    # Scan each sport independently so arbs don't mix across sports
    db = SessionLocal()
    try:
        total_arbs = 0
        for sport in SPORTS:
            try:
                total_arbs += _scan_and_alert_sport(db, sport)
            except Exception:
                logger.exception("Failed arb scan for %s — continuing", sport)
        logger.info("Arb scan complete: %d total opportunities across all sports", total_arbs)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
