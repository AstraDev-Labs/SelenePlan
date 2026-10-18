"""Entrypoint for project-service ASGI application."""

from __future__ import annotations

from project_service.api.app import app

__all__ = ["app"]
