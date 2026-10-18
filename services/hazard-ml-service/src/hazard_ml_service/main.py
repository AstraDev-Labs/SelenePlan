"""Entrypoint for hazard-ml-service ASGI application."""

from __future__ import annotations

from hazard_ml_service.api.app import app

__all__ = ["app"]
