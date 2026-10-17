from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from selene_observability.scrubbing import scrub_data
from selene_observability.tracing import get_current_trace_id


class JsonFormatter(logging.Formatter):
    """JSON log formatter adhering to structured logging standards and trace propagation."""

    def __init__(self, service_name: str) -> None:
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        # Check for trace_id from OpenTelemetry context or record attribute
        trace_id = getattr(record, "trace_id", None) or get_current_trace_id() or ""

        # Format message safely
        message = record.getMessage()

        log_payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": message,
            "trace_id": trace_id,
        }

        # Include exception info if present
        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        # Include extra attributes from record (e.g. extra={"event_id": ...})
        for key, val in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "trace_id",
            }:
                log_payload[key] = val

        # Sanitize sensitive fields recursively
        scrubbed = scrub_data(log_payload)
        return json.dumps(scrubbed)


def configure_logging(service_name: str, log_level: str = "INFO") -> None:
    """Configure the root logger with the standard JSON formatter and scrubbing."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service_name=service_name))

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root_logger.handlers = [handler]
