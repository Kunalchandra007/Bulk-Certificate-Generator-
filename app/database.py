"""Database engine, session factory, Base, and get_db dependency."""

from collections.abc import Generator
from typing import Callable

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(
    str(settings.DATABASE_URL),
    # SQLite needs check_same_thread=False for FastAPI's threaded usage
    connect_args=(
        {"check_same_thread": False} if str(settings.DATABASE_URL).startswith("sqlite") else {}
    ),
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session_factory() -> Callable[[], Session]:
    """Dependency for injecting the session factory into background tasks."""
    return SessionLocal
