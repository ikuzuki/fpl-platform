# === Build Stage ===
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

COPY libs/ libs/
RUN pip install --no-cache-dir ./libs

COPY services/enrich/pyproject.toml services/enrich/
COPY services/enrich/src/ services/enrich/src/
RUN pip install --no-cache-dir awslambdaric && \
    pip install --no-cache-dir ./services/enrich

# === Runtime Stage ===
FROM python:3.11-slim-bookworm

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app/services/enrich/src /app/src

ENTRYPOINT ["python", "-m", "awslambdaric"]
