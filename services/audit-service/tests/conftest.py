"""Pytest configuration and database fixtures for audit-service tests."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

os.environ["DB_NULL_POOL"] = "1"
os.environ.setdefault("MOCK_S3", "1")

import pytest
from audit_service.anchor.anchorer import get_in_memory_s3_client
from audit_service.db.session import dispose_engine, get_engine, init_db


@pytest.fixture(autouse=True)
def _reset_in_memory_s3() -> None:
    get_in_memory_s3_client().reset()


@pytest.fixture(scope="session", autouse=True)
async def _setup_database_session() -> AsyncIterator[None]:
    """Initialize audit database schema and tables once for the test session."""
    engine = get_engine()
    await init_db(engine)
    yield
    await dispose_engine()
