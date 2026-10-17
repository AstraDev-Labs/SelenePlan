from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests received",
    labelnames=["method", "route", "status_code"],
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    labelnames=["method", "route", "status_code"],
)


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    """ASGI middleware measuring request count and duration using route templates."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start_time = time.perf_counter()
        response: Response | None = None
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration = time.perf_counter() - start_time

            # Extract parameterized route template (e.g. /v1/projects/{id})
            route_obj = request.scope.get("route")
            if route_obj and hasattr(route_obj, "path"):
                route_template = str(route_obj.path)
            elif status_code == 404:
                route_template = "not_found"
            else:
                route_template = "unmatched"

            REQUEST_COUNT.labels(
                method=request.method,
                route=route_template,
                status_code=str(status_code),
            ).inc()

            REQUEST_DURATION.labels(
                method=request.method,
                route=route_template,
                status_code=str(status_code),
            ).observe(duration)
