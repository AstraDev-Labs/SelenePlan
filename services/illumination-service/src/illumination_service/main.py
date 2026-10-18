"""Entrypoint for illumination-service ASGI application."""

from __future__ import annotations

from illumination_service.api.app import app

__all__ = ["app"]
