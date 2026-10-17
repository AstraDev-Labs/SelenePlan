from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def init_tracing(service_name: str, otlp_endpoint: str | None = None) -> TracerProvider | None:
    """Initialize OpenTelemetry tracing if an OTLP endpoint is provided or configured.

    If neither otlp_endpoint nor OTEL_EXPORTER_OTLP_ENDPOINT environment variable
    is present, tracing remains an absolute no-op and returns None.
    """
    effective_endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not effective_endpoint:
        return None

    resource = Resource.create(attributes={SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=effective_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return provider


def get_current_trace_id() -> str | None:
    """Extract the active 32-character hex trace_id from OpenTelemetry context, if any."""
    span = trace.get_current_span()
    span_context = span.get_span_context()
    if span_context.is_valid:
        return f"{span_context.trace_id:032x}"
    return None
