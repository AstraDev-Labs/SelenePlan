from __future__ import annotations

import json
import logging
import sys

from selene_observability.logging import JsonFormatter, configure_logging


def test_json_formatter_formats_and_scrubs() -> None:
    formatter = JsonFormatter(service_name="test-service")
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="User authenticated successfully",
        args=(),
        exc_info=None,
    )
    record.trace_id = "0123456789abcdef0123456789abcdef"
    record.password = "super-secret"
    record.user_id = "user-42"

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["service"] == "test-service"
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "User authenticated successfully"
    assert parsed["trace_id"] == "0123456789abcdef0123456789abcdef"
    assert parsed["user_id"] == "user-42"
    assert parsed["password"] == "[REDACTED]"
    assert "timestamp" in parsed


def test_configure_logging_sets_root_handler() -> None:
    configure_logging(service_name="configured-service", log_level="DEBUG")
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert len(root.handlers) >= 1
    assert isinstance(root.handlers[0].formatter, JsonFormatter)


def test_json_formatter_with_exception() -> None:
    formatter = JsonFormatter(service_name="error-service")
    try:
        raise ValueError("Something went wrong")
    except ValueError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="test.err",
        level=logging.ERROR,
        pathname="test.py",
        lineno=25,
        msg="Error encountered",
        args=(),
        exc_info=exc_info,
    )
    formatted = formatter.format(record)
    parsed = json.loads(formatted)
    assert parsed["level"] == "ERROR"
    assert "exception" in parsed
    assert "ValueError: Something went wrong" in parsed["exception"]
