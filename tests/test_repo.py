"""Integration tests for db.repo – requires a running Postgres instance.

Run:  pytest tests/test_repo.py -v
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from cbb.db.repo import insert_games_and_prices, GameRow, PriceRow
from cbb.db.session import SessionLocal


def _clean(db):
    """Remove test rows (prices first due to FK)."""
    db.execute(text("DELETE FROM prices WHERE game_id IN "
                     "(SELECT id FROM games WHERE external_game_id LIKE 'test_%')"))
    db.execute(text("DELETE FROM games WHERE external_game_id LIKE 'test_%'"))
    db.commit()


def _make_fixtures() -> tuple[list[GameRow], list[PriceRow]]:
    now = datetime(2025, 3, 1, 18, 0, 0, tzinfo=timezone.utc)
    captured = datetime(2025, 3, 1, 17, 55, 0, tzinfo=timezone.utc)

    games: list[GameRow] = [
        {
            "external_game_id": "test_abc123",
            "sport_key": "basketball_ncaab",
            "commence_time": now,
            "home_team": "Duke",
            "away_team": "UNC",
        },
    ]

    prices: list[PriceRow] = [
        {
            "external_game_id": "test_abc123",
            "captured_at": captured,
            "bookmaker": "fanduel",
            "market": "spreads",
            "outcome": "Duke",
            "line": -3.5,
            "odds_american": -110,
            "odds_decimal": 1.91,
        },
        {
            "external_game_id": "test_abc123",
            "captured_at": captured,
            "bookmaker": "fanduel",
            "market": "spreads",
            "outcome": "UNC",
            "line": 3.5,
            "odds_american": -110,
            "odds_decimal": 1.91,
        },
    ]
    return games, prices


class TestInsertGamesAndPrices:
    """Tests that hit the real DB — clean up after themselves."""

    def setup_method(self):
        self.db = SessionLocal()
        _clean(self.db)

    def teardown_method(self):
        _clean(self.db)
        self.db.close()

    def test_insert_one_game_two_prices(self):
        games, prices = _make_fixtures()
        counts = insert_games_and_prices(self.db, games, prices)

        assert counts["games_upserted"] == 1
        assert counts["prices_inserted"] == 2

        # Verify rows landed
        row = self.db.execute(
            text("SELECT home_team, away_team FROM games "
                 "WHERE external_game_id = 'test_abc123'")
        ).fetchone()
        assert row is not None
        assert row[0] == "Duke"
        assert row[1] == "UNC"

        price_count = self.db.execute(
            text("SELECT count(*) FROM prices p "
                 "JOIN games g ON g.id = p.game_id "
                 "WHERE g.external_game_id = 'test_abc123'")
        ).scalar()
        assert price_count == 2

    def test_duplicate_prices_are_skipped(self):
        games, prices = _make_fixtures()

        # First insert
        counts1 = insert_games_and_prices(self.db, games, prices)
        assert counts1["prices_inserted"] == 2

        # Second insert — same captured_at, same bookmaker/market/outcome
        counts2 = insert_games_and_prices(self.db, games, prices)
        assert counts2["prices_inserted"] == 0

        # Total rows still 2
        total = self.db.execute(
            text("SELECT count(*) FROM prices p "
                 "JOIN games g ON g.id = p.game_id "
                 "WHERE g.external_game_id = 'test_abc123'")
        ).scalar()
        assert total == 2

    def test_game_upsert_updates_fields(self):
        games, prices = _make_fixtures()
        insert_games_and_prices(self.db, games, prices)

        # Change home/away and re-upsert
        games[0]["home_team"] = "Duke Blue Devils"
        games[0]["away_team"] = "North Carolina"
        insert_games_and_prices(self.db, games, [])

        row = self.db.execute(
            text("SELECT home_team, away_team FROM games "
                 "WHERE external_game_id = 'test_abc123'")
        ).fetchone()
        assert row[0] == "Duke Blue Devils"
        assert row[1] == "North Carolina"
