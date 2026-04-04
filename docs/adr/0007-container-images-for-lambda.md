# ADR-0007: Container Images for Lambda over Zip Packages

## Status
Accepted

## Context
AWS Lambda supports two deployment models: zip packages (up to 250 MB uncompressed) and container images (up to 10 GB). Our services depend on PyArrow, pandas, numpy, and the Anthropic SDK — heavy packages that push against zip size limits.

## Decision
Deploy all Lambda functions as container images via ECR. Each service has a multi-stage Dockerfile:
1. **Builder stage** — installs dependencies with pip
2. **Runtime stage** — copies installed packages into the AWS Lambda Python base image

```dockerfile
FROM public.ecr.aws/lambda/python:3.11 AS builder
# ... install deps ...

FROM public.ecr.aws/lambda/python:3.11
COPY --from=builder /var/lang/lib/python3.11/site-packages /var/lang/lib/python3.11/site-packages
```

One ECR repository per service (`fpl-data-dev`, `fpl-enrich-dev`, `fpl-agent-dev`), with immutable tags and a lifecycle policy retaining the last 10 images.

## Consequences
**Easier:**
- No size constraints — PyArrow + pandas + numpy alone exceed 250 MB
- Identical local and deployed environments (same Docker image)
- Multi-stage builds keep final image lean
- `docker build && docker push` is simpler than managing Lambda layers
- Immutable tags ensure deployed code is reproducible

**Harder:**
- Cold start is slower (~2-5s) compared to zip (~1-2s) — acceptable for our batch pipeline (not user-facing)
- ECR storage cost (minimal — lifecycle policy keeps only 10 images)
- Local testing requires Docker (vs zip which can run with just `python`)
