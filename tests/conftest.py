"""Shared test fixtures.

Uses SQLite in-memory with StaticPool so every test gets a fresh DB.
Overrides get_db so the app uses the test session.
STORAGE_DIR points to pytest tmp_path.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, get_db
from app.main import create_app


@pytest.fixture()
def db_session() -> Session:
    """Create a fresh in-memory SQLite DB and return a session."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session: Session, tmp_path) -> TestClient:
    """TestClient wired to the test DB and a temp storage directory."""
    app = create_app()

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    def _override_get_session_factory():
        from sqlalchemy.orm import sessionmaker

        return sessionmaker(bind=db_session.get_bind(), autocommit=False, autoflush=False)

    from app.database import get_session_factory

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_session_factory] = _override_get_session_factory

    # Patch storage dir for tests
    from app.config import settings

    original_storage = settings.STORAGE_DIR
    settings.STORAGE_DIR = tmp_path

    with TestClient(app) as c:
        yield c

    settings.STORAGE_DIR = original_storage
    app.dependency_overrides.clear()
