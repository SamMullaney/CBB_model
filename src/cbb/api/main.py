from fastapi import FastAPI, Depends, Query
from sqlalchemy.orm import Session

from cbb.config.sports import SPORTS
from cbb.db.repo import (
    get_latest_captured_at,
    get_latest_prices,
    PriceRow,
)
from cbb.db.session import SessionLocal
from cbb.pricing.arb import find_all_arbs

app = FastAPI(title="Arb Betting Bot", version="0.2.0")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/odds/latest")
def odds_latest(
    sport: str = Query(..., description="Sport key (e.g. basketball_ncaab)"),
    game: str | None = Query(None, description="Filter by external_game_id"),
    book: str | None = Query(None, description="Filter by bookmaker"),
    market: str | None = Query(None, description="Filter by market (h2h, spreads)"),
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Return prices from the most recent snapshot for a sport."""
    captured_at = get_latest_captured_at(db, sport)
    if captured_at is None:
        return {"sport": sport, "captured_at": None, "count": 0, "prices": []}

    rows = get_latest_prices(db, sport)

    if game:
        rows = [r for r in rows if r["external_game_id"] == game]
    if book:
        rows = [r for r in rows if r["bookmaker"] == book]
    if market:
        rows = [r for r in rows if r["market"] == market]

    total = len(rows)
    page = rows[offset : offset + limit]

    return {
        "sport": sport,
        "captured_at": captured_at.isoformat(),
        "total": total,
        "count": len(page),
        "prices": [
            {
                "game_id": r["external_game_id"],
                "bookmaker": r["bookmaker"],
                "market": r["market"],
                "outcome": r["outcome"],
                "line": float(r["line"]) if r["line"] is not None else None,
                "odds_american": r["odds_american"],
            }
            for r in page
        ],
    }


@app.get("/arbs/latest")
def arbs_latest(
    sport: str | None = Query(None, description="Sport key. Omit to scan all sports."),
    market: str | None = Query(None, description="Filter by market (h2h, spreads)"),
    min_edge: float = Query(0.002, ge=0.0, description="Minimum arb % to include"),
    db: Session = Depends(get_db),
):
    """Run arb detection on the latest snapshot and return results."""
    sports_to_scan = [sport] if sport else SPORTS
    all_arbs = []

    for s in sports_to_scan:
        captured_at = get_latest_captured_at(db, s)
        if captured_at is None:
            continue

        rows = get_latest_prices(db, s)
        arbs = find_all_arbs(rows, min_edge=min_edge)

        if market:
            arbs = [a for a in arbs if a.market == market]

        for opp in arbs:
            all_arbs.append({
                "sport": s,
                "game_id": opp.external_game_id,
                "market": opp.market,
                "arb_percent": round(opp.arb_percent * 100, 2),
                "guaranteed_profit_per_100": round(opp.arb_percent * 100, 2),
                "leg_a": {
                    "outcome": opp.leg_a.outcome,
                    "bookmaker": opp.leg_a.bookmaker,
                    "odds_american": opp.leg_a.odds_american,
                    "implied_prob": opp.leg_a.implied_prob,
                },
                "leg_b": {
                    "outcome": opp.leg_b.outcome,
                    "bookmaker": opp.leg_b.bookmaker,
                    "odds_american": opp.leg_b.odds_american,
                    "implied_prob": opp.leg_b.implied_prob,
                },
                "stakes_100": opp.stakes,
            })

    all_arbs.sort(key=lambda a: a["arb_percent"], reverse=True)

    return {
        "count": len(all_arbs),
        "arbs": all_arbs,
    }
