"""Shared pytest fixtures.

The test suite uses an in-memory SQLite database for speed and isolation.
Postgres-specific features (e.g. ON CONFLICT DO UPDATE) are guarded in
the production code so behaviour stays equivalent under SQLite, with
the trade-off of a row-by-row merge in tests.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.cache as cache_module
from app.db import Base, get_db
from app.main import app


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def db_session(engine) -> Iterator[Session]:
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(engine, monkeypatch) -> Iterator[TestClient]:
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)

    def override_get_db() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(cache_module, "get_client", lambda: None)

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)
