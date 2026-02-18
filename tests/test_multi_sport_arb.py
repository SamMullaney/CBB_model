"""End-to-end synthetic tests proving arb detection works across
multiple sports and both markets (h2h + spreads).

No DB, no network — pure in-memory PriceRow dicts fed to find_all_arbs.
"""

from datetime import datetime, timezone

from cbb.db.repo import PriceRow
from cbb.pricing.arb import find_all_arbs, find_h2h_arbs, find_spread_arbs

NOW = datetime(2025, 3, 1, 18, 0, 0, tzinfo=timezone.utc)


def _price(
    game: str,
    book: str,
    outcome: str,
    odds: int,
    market: str = "h2h",
    line: float | None = None,
) -> PriceRow:
    return PriceRow(
        external_game_id=game,
        captured_at=NOW,
        bookmaker=book,
        market=market,
        outcome=outcome,
        line=line,
        odds_american=odds,
        odds_decimal=None,
    )


# ── Multi-sport h2h ────────────────────────────────────────────────

class TestMultiSportH2H:
    """Prove h2h arb detection works with non-NCAAB game IDs."""

    def test_nba_h2h_arb(self):
        rows = [
            _price("nba_game_1", "draftkings", "Lakers", 110),
            _price("nba_game_1", "draftkings", "Celtics", -130),
            _price("nba_game_1", "fanduel", "Lakers", -130),
            _price("nba_game_1", "fanduel", "Celtics", 110),
        ]
        arbs = find_h2h_arbs(rows, min_edge=0.0)
        assert len(arbs) == 1
        assert arbs[0].external_game_id == "nba_game_1"
        assert arbs[0].market == "h2h"
        assert arbs[0].arb_percent > 0.04

    def test_nhl_h2h_arb(self):
        rows = [
            _price("nhl_game_1", "betmgm", "Bruins", 115),
            _price("nhl_game_1", "betmgm", "Rangers", -135),
            _price("nhl_game_1", "caesars", "Bruins", -135),
            _price("nhl_game_1", "caesars", "Rangers", 115),
        ]
        arbs = find_h2h_arbs(rows, min_edge=0.0)
        assert len(arbs) == 1
        assert arbs[0].external_game_id == "nhl_game_1"

    def test_nfl_h2h_arb(self):
        rows = [
            _price("nfl_game_1", "bovada", "Chiefs", 120),
            _price("nfl_game_1", "bovada", "Eagles", -140),
            _price("nfl_game_1", "pointsbet", "Chiefs", -140),
            _price("nfl_game_1", "pointsbet", "Eagles", 120),
        ]
        arbs = find_h2h_arbs(rows, min_edge=0.0)
        assert len(arbs) == 1
        assert arbs[0].external_game_id == "nfl_game_1"

    def test_mlb_h2h_arb(self):
        rows = [
            _price("mlb_game_1", "draftkings", "Yankees", 130),
            _price("mlb_game_1", "draftkings", "Dodgers", -150),
            _price("mlb_game_1", "fanduel", "Yankees", -150),
            _price("mlb_game_1", "fanduel", "Dodgers", 130),
        ]
        arbs = find_h2h_arbs(rows, min_edge=0.0)
        assert len(arbs) == 1
        assert arbs[0].external_game_id == "mlb_game_1"


# ── Multi-sport spreads ─────────────────────────────────────────────

class TestMultiSportSpreads:
    """Prove spread arb detection works across sports."""

    def test_nba_spread_arb(self):
        rows = [
            _price("nba_game_2", "draftkings", "Lakers", 105, "spreads", -4.5),
            _price("nba_game_2", "draftkings", "Celtics", -125, "spreads", 4.5),
            _price("nba_game_2", "fanduel", "Lakers", -125, "spreads", -4.5),
            _price("nba_game_2", "fanduel", "Celtics", 105, "spreads", 4.5),
        ]
        arbs = find_spread_arbs(rows, min_edge=0.0)
        assert len(arbs) == 1
        opp = arbs[0]
        assert opp.market == "spreads"
        assert opp.external_game_id == "nba_game_2"
        # Verify lines are preserved
        legs = {opp.leg_a.outcome: opp.leg_a, opp.leg_b.outcome: opp.leg_b}
        assert legs["Lakers"].line == -4.5
        assert legs["Celtics"].line == 4.5

    def test_nfl_spread_arb(self):
        rows = [
            _price("nfl_game_2", "bovada", "Chiefs", 108, "spreads", -3.0),
            _price("nfl_game_2", "bovada", "Eagles", -128, "spreads", 3.0),
            _price("nfl_game_2", "pointsbet", "Chiefs", -128, "spreads", -3.0),
            _price("nfl_game_2", "pointsbet", "Eagles", 108, "spreads", 3.0),
        ]
        arbs = find_spread_arbs(rows, min_edge=0.0)
        assert len(arbs) == 1
        assert arbs[0].external_game_id == "nfl_game_2"

    def test_ncaab_spread_arb(self):
        rows = [
            _price("ncaab_game_1", "draftkings", "Duke", 110, "spreads", -7.5),
            _price("ncaab_game_1", "draftkings", "UNC", -130, "spreads", 7.5),
            _price("ncaab_game_1", "fanduel", "Duke", -130, "spreads", -7.5),
            _price("ncaab_game_1", "fanduel", "UNC", 110, "spreads", 7.5),
        ]
        arbs = find_spread_arbs(rows, min_edge=0.0)
        assert len(arbs) == 1


# ── Combined multi-sport + multi-market ─────────────────────────────

class TestCombinedMultiSportMultiMarket:
    """Prove find_all_arbs returns arbs from multiple sports and markets."""

    def test_finds_arbs_across_3_sports_and_both_markets(self):
        """Mix of NBA h2h, NCAAB spread, and NHL h2h — all should be found."""
        rows = [
            # NBA h2h arb
            _price("nba_g1", "draftkings", "Lakers", 110),
            _price("nba_g1", "draftkings", "Celtics", -130),
            _price("nba_g1", "fanduel", "Lakers", -130),
            _price("nba_g1", "fanduel", "Celtics", 110),
            # NCAAB spread arb
            _price("ncaab_g1", "betmgm", "Duke", 105, "spreads", -3.5),
            _price("ncaab_g1", "betmgm", "UNC", -125, "spreads", 3.5),
            _price("ncaab_g1", "caesars", "Duke", -125, "spreads", -3.5),
            _price("ncaab_g1", "caesars", "UNC", 105, "spreads", 3.5),
            # NHL h2h arb
            _price("nhl_g1", "bovada", "Bruins", 115),
            _price("nhl_g1", "bovada", "Rangers", -135),
            _price("nhl_g1", "pointsbet", "Bruins", -135),
            _price("nhl_g1", "pointsbet", "Rangers", 115),
            # NBA spread — NO arb (standard vig)
            _price("nba_g1", "draftkings", "Lakers", -110, "spreads", -5.5),
            _price("nba_g1", "draftkings", "Celtics", -110, "spreads", 5.5),
        ]
        arbs = find_all_arbs(rows, min_edge=0.0)
        assert len(arbs) == 3

        game_ids = {a.external_game_id for a in arbs}
        assert game_ids == {"nba_g1", "ncaab_g1", "nhl_g1"}

        markets = {a.external_game_id: a.market for a in arbs}
        assert markets["nba_g1"] == "h2h"
        assert markets["ncaab_g1"] == "spreads"
        assert markets["nhl_g1"] == "h2h"

    def test_all_5_sports_simultaneous(self):
        """Arbs from all 5 configured sports detected in one call."""
        rows = [
            # NCAAB h2h
            _price("ncaab_g1", "dk", "Duke", 110),
            _price("ncaab_g1", "fd", "Duke", -130),
            _price("ncaab_g1", "dk", "UNC", -130),
            _price("ncaab_g1", "fd", "UNC", 110),
            # NBA spread
            _price("nba_g1", "dk", "Lakers", 105, "spreads", -6.5),
            _price("nba_g1", "fd", "Lakers", -125, "spreads", -6.5),
            _price("nba_g1", "dk", "Celtics", -125, "spreads", 6.5),
            _price("nba_g1", "fd", "Celtics", 105, "spreads", 6.5),
            # NFL h2h
            _price("nfl_g1", "dk", "Chiefs", 115),
            _price("nfl_g1", "fd", "Chiefs", -135),
            _price("nfl_g1", "dk", "Eagles", -135),
            _price("nfl_g1", "fd", "Eagles", 115),
            # NHL h2h
            _price("nhl_g1", "dk", "Bruins", 120),
            _price("nhl_g1", "fd", "Bruins", -140),
            _price("nhl_g1", "dk", "Rangers", -140),
            _price("nhl_g1", "fd", "Rangers", 120),
            # MLB spread
            _price("mlb_g1", "dk", "Yankees", 108, "spreads", -1.5),
            _price("mlb_g1", "fd", "Yankees", -128, "spreads", -1.5),
            _price("mlb_g1", "dk", "Dodgers", -128, "spreads", 1.5),
            _price("mlb_g1", "fd", "Dodgers", 108, "spreads", 1.5),
        ]
        arbs = find_all_arbs(rows, min_edge=0.0)
        assert len(arbs) == 5

        game_ids = {a.external_game_id for a in arbs}
        assert game_ids == {"ncaab_g1", "nba_g1", "nfl_g1", "nhl_g1", "mlb_g1"}

    def test_sorted_descending_across_sports(self):
        """Arbs from different sports are sorted by arb_percent descending."""
        rows = [
            # Small arb (NBA h2h, ~1.5%)
            _price("nba_g1", "dk", "Lakers", 102),
            _price("nba_g1", "fd", "Lakers", -110),
            _price("nba_g1", "dk", "Celtics", -110),
            _price("nba_g1", "fd", "Celtics", 102),
            # Big arb (NHL h2h, ~4.8%)
            _price("nhl_g1", "dk", "Bruins", 110),
            _price("nhl_g1", "fd", "Bruins", -130),
            _price("nhl_g1", "dk", "Rangers", -130),
            _price("nhl_g1", "fd", "Rangers", 110),
        ]
        arbs = find_all_arbs(rows, min_edge=0.0)
        assert len(arbs) == 2
        assert arbs[0].arb_percent > arbs[1].arb_percent
        assert arbs[0].external_game_id == "nhl_g1"

    def test_stakes_sum_to_100_across_sports_and_markets(self):
        """Verify stake math is correct for every detected arb."""
        rows = [
            _price("nba_g1", "dk", "Lakers", 150),
            _price("nba_g1", "fd", "Lakers", -200),
            _price("nba_g1", "dk", "Celtics", -170),
            _price("nba_g1", "fd", "Celtics", 150),
            _price("nfl_g1", "dk", "Chiefs", 108, "spreads", -3.0),
            _price("nfl_g1", "fd", "Chiefs", -128, "spreads", -3.0),
            _price("nfl_g1", "dk", "Eagles", -128, "spreads", 3.0),
            _price("nfl_g1", "fd", "Eagles", 108, "spreads", 3.0),
        ]
        arbs = find_all_arbs(rows, min_edge=0.0)
        for opp in arbs:
            assert abs(sum(opp.stakes.values()) - 100.0) < 0.02, (
                f"{opp.external_game_id} stakes don't sum to 100: {opp.stakes}"
            )

    def test_no_cross_game_arb_leakage(self):
        """Odds from different games should never be combined into one arb."""
        rows = [
            # Game 1: only one side is +odds
            _price("nba_g1", "dk", "Lakers", 150),
            _price("nba_g1", "dk", "Celtics", -200),
            # Game 2: only one side is +odds (different teams)
            _price("nba_g2", "fd", "Heat", 150),
            _price("nba_g2", "fd", "Bucks", -200),
        ]
        arbs = find_all_arbs(rows, min_edge=0.0)
        # Neither game has an arb on its own (only 1 book each)
        assert len(arbs) == 0
