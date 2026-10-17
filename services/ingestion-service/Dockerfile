FROM python:3.12-slim

WORKDIR /app

# Copy shared libraries and service code
COPY libs /app/libs
COPY contracts /app/contracts
COPY services/ingestion-service /app/services/ingestion-service

# 1. Install server and cloud/database drivers
RUN pip install --no-cache-dir \
    "uvicorn[standard]==0.32.0" \
    "fastapi>=0.115.0" \
    "asyncpg==0.29.0" \
    "sqlalchemy[asyncio]>=2.0.0" \
    "greenlet>=3.0.0" \
    "aiokafka>=0.11.0" \
    "boto3>=1.35.0" \
    "httpx>=0.28.0" \
    "pyyaml>=6.0.0" \
    "pillow>=10.0.0" \
    "numpy>=1.26.0" \
    "python-multipart>=0.0.9"

# 2. Install shared libraries
RUN pip install --no-cache-dir --no-deps \
    -e /app/libs/selene-observability \
    -e /app/libs/selene-events \
    -e /app/libs/selene-auth \
    -e /app/libs/selene-geo \
    -e /app/libs/selene-testing \
    -e /app/services/ingestion-service

EXPOSE 8102

CMD ["python", "-m", "uvicorn", "ingestion_service.main:app", "--host", "0.0.0.0", "--port", "8102"]
