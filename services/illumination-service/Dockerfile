# Multi-stage minimal non-root Dockerfile for illumination-service (port 8105)
FROM python:3.12-slim AS builder

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

COPY libs /build/libs
COPY services/illumination-service /build/services/illumination-service

RUN pip install --no-cache-dir --prefix=/install \
    fastapi uvicorn pydantic numpy numba scipy zarr spiceypy \
    /build/libs/selene-events /build/libs/selene-auth /build/libs/selene-observability /build/libs/selene-geo \
    /build/services/illumination-service

FROM python:3.12-slim AS runner

WORKDIR /app
RUN groupadd -g 10001 selene && useradd -u 10001 -g selene -s /bin/sh selene && \
    apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
USER 10001

EXPOSE 8105

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8105/healthz || exit 1

CMD ["python", "-m", "uvicorn", "illumination_service.api.app:app", "--host", "0.0.0.0", "--port", "8105"]
