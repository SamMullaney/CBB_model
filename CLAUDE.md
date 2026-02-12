# CLAUDE.md — Arbitragte Betting Bot

## Project Goal
Build arb bot:

1) Bot: ingest odds from The Odds API, compute no-vig prices, detect arbitrage + best-price opportunities, and alert.


This repo is Python-first and deploys as:
- FastAPI service (read/query)
- Worker service (ingestion + scanning + alerts)
- Postgres for storage

## Tech Stack
- Python 3.12
- FastAPI + Uvicorn
- Postgres 16
- SQLAlchemy + psycopg
- httpx (Odds API)
- tenacity (retries/backoff)
- numpy, pandas
- pytest + ruff
- Docker + docker-compose
- Discord webhooks for alerts

## Codebase Rules
- clients/ only talks to external APIs
- ingestion/ coordinates fetching + normalization + saving
- pricing/ is pure math (easy to test, no DB, no web calls)
- alerts/ only sends notifications
- api/ only serves data (doesn’t fetch odds itself)

## Non-Negotiables (Be Very Careful)
- NEVER hardcode secrets (API keys, DB creds, webhooks). Use env vars + Settings.
- NEVER commit or print full secrets in logs.
- NEVER change public function signatures without updating all call sites + tests.
- Prefer small, reviewable commits: implement one vertical slice at a time.
- If uncertain about an assumption, write it down in a comment and implement it behind a config flag.

## Coding Standards
- Python 3.12, type hints required for new functions.
- Use pydantic Settings for config (src/cbb/config/settings.py).
- Add docstrings for non-trivial functions (math, edge logic).
- Logging: structured logs, no secrets, include request ids when possible.

## Testing Requirements
- Every new math function gets unit tests under /tests.
- Every Odds API response parsing path gets a minimal fixture-based test.
- Use deterministic tests (no real network calls).
- Add "contract tests" that validate schemas for normalized odds rows.

## When You Propose Changes
Before coding, briefly list:
- Files you will touch
- New functions/classes to add
- New DB tables or migrations
- Tests you will add

Then implement. Keep changes minimal.