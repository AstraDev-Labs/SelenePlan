# Multi-stage minimal non-root Dockerfile for report-service (port 8108)
FROM python:3.12-slim AS builder

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

COPY libs /build/libs
COPY services/report-service /build/services/report-service

RUN pip install --no-cache-dir --prefix=/install \
    fastapi uvicorn pydantic jinja2 markupsafe httpx \
    /build/libs/selene-events /build/libs/selene-auth /build/libs/selene-observability \
    /build/services/report-service

FROM python:3.12-slim AS runner

WORKDIR /app
RUN groupadd -g 10001 selene && useradd -u 10001 -g selene -s /bin/sh selene && \
    apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
USER 10001

EXPOSE 8108

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8108/healthz || exit 1

CMD ["python", "-m", "uvicorn", "report_service.api.app:app", "--host", "0.0.0.0", "--port", "8108"]
