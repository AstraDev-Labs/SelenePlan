"""API package for audit service."""

from audit_service.api.integrity import router as integrity_router
from audit_service.api.internal import router as internal_router
from audit_service.api.query import router as query_router

__all__ = ["integrity_router", "internal_router", "query_router"]
