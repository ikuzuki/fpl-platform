# === Build Stage ===
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

COPY libs/ libs/
RUN pip install --no-cache-dir ./libs

COPY services/curate/pyproject.toml services/curate/
COPY services/curate/src/ services/curate/src/
RUN pip install --no-cache-dir awslambdaric && \
    pip install --no-cache-dir ./services/curate

# === Runtime Stage ===
FROM python:3.11-slim-bookworm

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app/services/curate/src /app/src

ENTRYPOINT ["python", "-m", "awslambdaric"]
