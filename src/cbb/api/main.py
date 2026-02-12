from fastapi import FastAPI, Depends, Query
from sqlalchemy.orm import Session

from cbb.db.repo import (
    get_latest_captured_at,
    get_latest_prices,
    PriceRow,
)
from cbb.db.session import SessionLocal
from cbb.pricing.arb import find_h2h_arbs

app = FastAPI(title="CBB Betting Bots", version="0.1.0")


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
    game: str | None = Query(None, description="Filter by external_game_id"),
    book: str | None = Query(None, description="Filter by bookmaker"),
    market: str | None = Query(None, description="Filter by market (h2h, spreads, totals)"),
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Return prices from the most recent snapshot."""
    captured_at = get_latest_captured_at(db)
    if captured_at is None:
        return {"captured_at": None, "count": 0, "prices": []}

    rows = get_latest_prices(db)

    # Optional filters
    if game:
        rows = [r for r in rows if r["external_game_id"] == game]
    if book:
        rows = [r for r in rows if r["bookmaker"] == book]
    if market:
        rows = [r for r in rows if r["market"] == market]

    total = len(rows)
    page = rows[offset : offset + limit]

    return {
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
    min_edge: float = Query(0.002, ge=0.0, description="Minimum arb % to include"),
    db: Session = Depends(get_db),
):
    """Run arb detection on the latest snapshot and return results."""
    captured_at = get_latest_captured_at(db)
    if captured_at is None:
        return {"captured_at": None, "count": 0, "arbs": []}

    rows = get_latest_prices(db)
    arbs = find_h2h_arbs(rows, min_edge=min_edge)

    return {
        "captured_at": captured_at.isoformat(),
        "count": len(arbs),
        "arbs": [
            {
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
            }
            for opp in arbs
        ],
    }
