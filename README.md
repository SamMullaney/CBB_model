README - Sam Mullaney CBB Prediction Model

Skeleton Repo Structure:
cbb-betting-bots/
├─ README.md
├─ CLAUDE.md
├─ pyproject.toml
├─ .gitignore
├─ .env.example
├─ docker-compose.yml
├─ Makefile
│
├─ infra/
│  └─ sql/
│     └─ 010_tables.sql
│
├─ scripts/
│  ├─ run_api.py
│  ├─ run_arb_worker.py
│  └─ run_edge_worker.py
│
├─ src/
│  └─ cbb/
│     ├─ __init__.py
│     │
│     ├─ config/
│     │  ├─ __init__.py
│     │  ├─ settings.py
│     │  └─ logging.py
│     │
│     ├─ clients/
│     │  ├─ __init__.py
│     │  └─ odds_api.py              # placeholder for later
│     │
│     ├─ ingestion/
│     │  ├─ __init__.py
│     │  └─ odds_ingest.py           # placeholder for later
│     │
│     ├─ pricing/
│     │  ├─ __init__.py
│     │  ├─ implied_prob.py          # placeholder for later
│     │  ├─ devig.py                 # placeholder for later
│     │  ├─ arb.py                   # placeholder for later
│     │  ├─ ev.py                    # placeholder for later
│     │  └─ kelly.py                 # placeholder for later
│     │
│     ├─ modeling/
│     │  ├─ __init__.py
│     │  └─ margin_model.py          # placeholder for later
│     │
│     ├─ alerts/
│     │  ├─ __init__.py
│     │  └─ discord.py               # placeholder for later
│     │
│     ├─ db/
│     │  ├─ __init__.py
│     │  ├─ session.py
│     │  └─ repo.py
│     │
│     ├─ bots/
│     │  ├─ __init__.py
│     │  ├─ arb_bot.py               # orchestrates arb pipeline
│     │  └─ edge_bot.py              # orchestrates edge pipeline
│     │
│     ├─ api/
│     │  ├─ __init__.py
│     │  └─ main.py
│     │
│     └─ utils/
│        ├─ __init__.py
│        └─ time.py                  # placeholder for later
│
└─ tests/
   ├─ __init__.py
   └─ test_smoke.py


   Step-by-step build order (clean + industry standard)
Phase 1 — Repo “boots” (no Odds API yet)

Goal: pytest passes, FastAPI runs, Postgres runs.

Create the directory skeleton

Yes: create the directories now, even if files are placeholders.

This locks in the architecture and makes Claude’s edits safer.

Add these root files first:

pyproject.toml (dependencies + tooling)

.gitignore (ignore .venv, .env, caches)

.env.example (template vars)

docker-compose.yml (postgres)

README.md (how to run)

CLAUDE.md (rules)

Add minimal “boot files”:

src/cbb/config/settings.py

src/cbb/api/main.py with /health

tests/test_smoke.py

Verify boot:

Create .venv and install

docker compose up -d (postgres)

pytest

uvicorn cbb.api.main:app --reload

Stop here only when all 3 work.

Why this order works:

If uvicorn + imports + tests aren’t stable, Odds API code will be painful.