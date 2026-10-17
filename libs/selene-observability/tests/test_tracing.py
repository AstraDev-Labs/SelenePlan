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
