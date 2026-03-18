from sqlalchemy import text

from database import get_engine


def main() -> None:
    engine = get_engine()
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1 AS ok"))
        print(result.scalar_one())


if __name__ == "__main__":
    main()
