# ADR-0007: Container Images for Lambda over Zip Packages

## Status
Accepted

## Date
2026-04-04

## Context
AWS Lambda supports two deployment models: zip packages (up to 250 MB uncompressed) and container images (up to 10 GB). Our services depend on PyArrow (~180 MB), pandas (~60 MB), numpy (~30 MB), and the Anthropic SDK — these alone exceed the zip size limit.

## Options Considered

### 1. Zip packages with Lambda layers (rejected)
Split dependencies into layers (e.g., a "data science" layer with pandas/pyarrow, a "core" layer with boto3/pydantic). Application code as a thin zip.

**Rejected because:**
- Layer management adds operational overhead — layers must be versioned, published, and compatible across services
- Total uncompressed size (layers + code) still has a 250 MB limit, which our deps exceed
- Layers are region-specific and must be rebuilt per architecture (x86 vs ARM)

### 2. Container images via ECR (chosen)
Multi-stage Dockerfile per service. Builder stage installs dependencies, runtime stage copies only what's needed into the AWS Lambda Python base image.

### 3. Zip packages with stripped/compiled deps (rejected)
Strip debug symbols, compile `.py` to `.pyc`, remove tests from packages to fit under 250 MB.

**Rejected because:** Fragile — each dependency update risks breaking the size budget. PyArrow alone is ~180 MB and can't be meaningfully stripped.

## Decision
Deploy all Lambda functions as container images via ECR. Each service has a multi-stage Dockerfile.

One ECR repository per service (`fpl-data-dev`, `fpl-enrich-dev`, `fpl-agent-dev`), with immutable tags and a lifecycle policy retaining the last 10 images.

## Consequences
**Easier:**
- No size constraints — 10 GB limit is effectively unlimited for Python services
- Identical local and deployed environments (same Docker image)
- Multi-stage builds keep final image lean (~300 MB vs installing everything from scratch)
- `docker build && docker push` is simpler than managing Lambda layers
- CI pipeline is straightforward: build, tag with commit SHA, push to ECR, update Lambda

**Harder:**
- Cold start is slower (~2-5s) compared to zip (~1-2s) — acceptable for a batch pipeline that runs weekly, not user-facing
- ECR storage cost (minimal — lifecycle policy keeps only 10 images per repo)
- Local testing requires Docker (vs zip which can run with just `python`)
- Image builds are slower than zip packaging (~30-60s vs ~5s in CI)
