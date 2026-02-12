"""Apply raw SQL files against DATABASE_URL using SQLAlchemy (no extra deps).

Usage:
    python scripts/apply_sql.py               # applies infra/sql/010_tables.sql
    python scripts/apply_sql.py path/to.sql   # applies a specific file
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

# project imports — works when the package is pip-installed in editable mode
from cbb.db.session import engine

DEFAULT_SQL = Path(__file__).resolve().parent.parent / "infra" / "sql" / "010_tables.sql"


def apply(sql_path: Path) -> None:
    sql = sql_path.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.execute(text(sql))
    print(f"Applied {sql_path}")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SQL
    if not target.exists():
        print(f"File not found: {target}")
        sys.exit(1)
    apply(target)
