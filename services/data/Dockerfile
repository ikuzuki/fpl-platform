# === Build Stage ===
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

# Install shared lib first (changes less often — better layer caching)
COPY libs/ libs/
RUN pip install --no-cache-dir ./libs

# Install service
COPY services/data/pyproject.toml services/data/
COPY services/data/src/ services/data/src/
RUN pip install --no-cache-dir awslambdaric && \
    pip install --no-cache-dir ./services/data

# === Runtime Stage ===
FROM python:3.11-slim-bookworm

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app/services/data/src /app/src

ENTRYPOINT ["python", "-m", "awslambdaric"]
