"""Pytest configuration and database fixtures for provenance-service tests."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

os.environ["DB_NULL_POOL"] = "1"

import pytest
from provenance_service.db.session import dispose_engine, get_engine, init_db


@pytest.fixture(scope="session", autouse=True)
async def _setup_database_session() -> AsyncIterator[None]:
    """Initialize provenance database tables once for the test session."""
    engine = get_engine()
    await init_db(engine)
    yield
    await dispose_engine()
