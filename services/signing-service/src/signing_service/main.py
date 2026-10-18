"""Entrypoint for signing-service ASGI application."""

from __future__ import annotations

from signing_service.api.app import app

__all__ = ["app"]
