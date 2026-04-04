# === Build Stage ===
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

COPY libs/ libs/
RUN pip install --no-cache-dir ./libs

COPY services/agent/pyproject.toml services/agent/
COPY services/agent/src/ services/agent/src/
RUN pip install --no-cache-dir awslambdaric && \
    pip install --no-cache-dir ./services/agent

# === Runtime Stage ===
FROM python:3.11-slim-bookworm

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app/services/agent/src /app/src

ENTRYPOINT ["python", "-m", "awslambdaric"]
