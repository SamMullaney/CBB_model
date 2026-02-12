from sqlalchemy import text

from cbb.db.session import SessionLocal

def main() -> None:
    with SessionLocal() as db:
        result = db.execute(text("SELECT 1")).scalar_one()
        print("DB OK:", result)

if __name__ == "__main__":
    main()
