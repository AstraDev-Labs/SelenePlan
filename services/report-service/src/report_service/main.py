"""Entrypoint for report-service ASGI application."""

from __future__ import annotations

from report_service.api.app import app

__all__ = ["app"]
