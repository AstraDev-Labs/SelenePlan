FROM python:3.12-slim

WORKDIR /app

# Copy shared libraries and service code
COPY libs /app/libs
COPY contracts /app/contracts
COPY services/audit-service /app/services/audit-service

# 1. Install uvicorn server and database / cloud drivers
RUN pip install --no-cache-dir \
    "uvicorn[standard]==0.32.0" \
    "asyncpg==0.29.0" \
    "sqlalchemy[asyncio]>=2.0.0" \
    "greenlet>=3.0.0" \
    "aiokafka>=0.11.0" \
    "boto3>=1.35.0" \
    "redis>=5.0.0"

# 2. Install locked dependencies with hashes from shared libraries
RUN pip install --no-cache-dir \
    -r /app/libs/selene-observability/requirements-lock.txt \
    -r /app/libs/selene-events/requirements-lock.txt \
    -r /app/libs/selene-auth/requirements-lock.txt

# 3. Install packages in editable mode
RUN pip install --no-cache-dir --no-deps \
    -e /app/libs/selene-observability \
    -e /app/libs/selene-events \
    -e /app/libs/selene-auth \
    -e /app/services/audit-service

EXPOSE 8109

CMD ["python", "-m", "uvicorn", "audit_service.main:app", "--host", "0.0.0.0", "--port", "8109"]
