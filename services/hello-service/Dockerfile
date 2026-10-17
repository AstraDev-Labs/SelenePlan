FROM python:3.12-slim

WORKDIR /app

# Copy shared libraries and service code
COPY libs /app/libs
COPY services/hello-service /app/services/hello-service

# 1. Install uvicorn server
RUN pip install --no-cache-dir "uvicorn[standard]==0.32.0"

# 2. Install locked dependencies with hashes from shared libraries
RUN pip install --no-cache-dir \
    -r /app/libs/selene-observability/requirements-lock.txt \
    -r /app/libs/selene-auth/requirements-lock.txt

# 3. Install packages in editable mode
RUN pip install --no-cache-dir --no-deps \
    -e /app/libs/selene-observability \
    -e /app/libs/selene-auth \
    -e /app/services/hello-service

EXPOSE 8100

CMD ["python", "-m", "uvicorn", "hello_service.main:app", "--host", "0.0.0.0", "--port", "8100"]
