# === Lambda Web Adapter ===
# Sidecar extension that translates Function URL RESPONSE_STREAM events into
# local HTTP requests. Lets us run an unmodified FastAPI app via uvicorn inside
# the Lambda container. Version-pinned — bump deliberately. See ADR-0010.
FROM public.ecr.aws/awsguru/aws-lambda-adapter:0.9.0 AS lwa

# === Build Stage ===
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

COPY libs/ libs/
RUN pip install --no-cache-dir ./libs

COPY services/agent/pyproject.toml services/agent/
COPY services/agent/src/ services/agent/src/
RUN pip install --no-cache-dir ./services/agent

# === Runtime Stage ===
FROM python:3.11-slim-bookworm

WORKDIR /app

COPY --from=lwa /lambda-adapter /opt/extensions/lambda-adapter
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY --from=builder /app/services/agent/src /app/src

# LWA configuration. response_stream is what makes /chat stream live to
# CloudFront instead of buffering inside the Function URL.
ENV AWS_LWA_INVOKE_MODE=response_stream
ENV AWS_LWA_PORT=8000
ENV AWS_LWA_READINESS_CHECK_PATH=/health
ENV PORT=8000

# uvicorn binds to 0.0.0.0:8000 inside the container; LWA intercepts.
# --no-access-log keeps CloudWatch quiet — Langfuse is our request trace
# source of truth, not uvicorn's stdout.
CMD ["uvicorn", "fpl_agent.api:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--no-access-log"]
