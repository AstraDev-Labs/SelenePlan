"""Entrypoint for comms-service ASGI application."""

from __future__ import annotations

from comms_service.api.app import app

__all__ = ["app"]
