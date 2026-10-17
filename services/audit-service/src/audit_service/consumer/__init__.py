"""Consumer package for audit service."""

from audit_service.consumer.audit_consumer import ALLOWED_ACTIONS, AuditEventConsumer

__all__ = ["ALLOWED_ACTIONS", "AuditEventConsumer"]
