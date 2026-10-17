from __future__ import annotations

import os

from selene_observability.tracing import get_current_trace_id, init_tracing


def test_init_tracing_no_op_without_endpoint() -> None:
    # Ensure environment is clear
    old_env = os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
    try:
        provider = init_tracing("test-service", otlp_endpoint=None)
        assert provider is None
    finally:
        if old_env is not None:
            os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = old_env


def test_get_current_trace_id_inactive() -> None:
    # Outside active span context, returns None
    trace_id = get_current_trace_id()
    assert trace_id is None


def test_get_current_trace_id_active() -> None:
    from opentelemetry.sdk.trace import TracerProvider

    provider = TracerProvider()
    tracer = provider.get_tracer("test-tracer")
    with tracer.start_as_current_span("test-span"):
        trace_id = get_current_trace_id()
        assert trace_id is not None
        assert len(trace_id) == 32


def test_init_tracing_with_otlp_endpoint() -> None:
    from unittest.mock import MagicMock, patch

    from opentelemetry.sdk.trace import TracerProvider

    mock_exporter = MagicMock()
    with patch(
        "selene_observability.tracing.OTLPSpanExporter", return_value=mock_exporter
    ) as mock_cls:
        provider = init_tracing("test-service", otlp_endpoint="http://otel-collector:4317")
        assert provider is not None
        assert isinstance(provider, TracerProvider)
        mock_cls.assert_called_once_with(endpoint="http://otel-collector:4317")
