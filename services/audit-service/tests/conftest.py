"""Pytest configuration and database fixtures for audit-service tests."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

os.environ["DB_NULL_POOL"] = "1"

import pytest
from audit_service.db.session import dispose_engine, get_engine, init_db


@pytest.fixture(scope="session", autouse=True)
async def _setup_database_session() -> AsyncIterator[None]:
    """Initialize audit database schema and tables once for the test session."""
    engine = get_engine()
    await init_db(engine)
    yield
    await dispose_engine()
