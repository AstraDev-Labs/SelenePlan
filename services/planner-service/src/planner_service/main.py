"""Entrypoint for planner-service ASGI application."""

from __future__ import annotations

from planner_service.api.app import app

__all__ = ["app"]
