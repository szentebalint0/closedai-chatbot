from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from database.config import get_database_url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(
        get_database_url(),
        pool_pre_ping=True,
        future=True,
    )


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=get_engine(),
)
