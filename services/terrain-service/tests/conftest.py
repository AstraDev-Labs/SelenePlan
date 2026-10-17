"""Pytest fixtures for terrain-service tests."""

import pytest


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Token for authorized mission planner."""
    return {"Authorization": "Bearer planner-proj1"}


@pytest.fixture
def unauthorized_headers() -> dict[str, str]:
    """Token for user in different project."""
    return {"Authorization": "Bearer planner-proj2"}
