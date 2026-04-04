# FPL Platform — Claude Code Context

## Project Overview
FPL analytics platform: data collection → LLM enrichment → agentic recommendations.
Monorepo with shared lib, multiple services, and Terraform infrastructure.

## Repository Structure
- `libs/fpl_lib/` — Shared Python library (models, clients, utils, validators)
- `services/data/` — Data collection Lambdas (FPL API, Understat, news)
- `services/enrich/` — LLM enrichment Lambdas (summaries, injury, sentiment)
- `services/etl/` — dbt models + DuckDB processing scripts
- `services/agent/` — LangGraph transfer recommendation agent
- `services/stream/` — Kafka streaming pipeline
- `infrastructure/` — Terraform modules and environment configs
- `web/` — Portfolio site + Streamlit dashboard
- `docs/adr/` — Architecture Decision Records

## Build & Test Commands
- Install all deps: `make install`
- Lint: `make lint` (runs ruff check + mypy)
- Format: `make format` (runs ruff fix + ruff format)
- Test all: `make test`
- Test single service: `make test-service SERVICE=data`
- Test unit only: `make test-unit`
- Terraform plan: `cd infrastructure/environments/dev && terraform plan`
- Terraform format: `terraform fmt -recursive infrastructure/`

## Code Style
- Python 3.11+, strict type hints on all public functions
- Ruff for linting (rules: E, W, F, I, N, UP, B, SIM), 100 char line length
- Pydantic v2 for all data models
- Google-style docstrings on all public functions
- Conventional Commits required (feat/fix/docs/chore/test/refactor/ci)

## Architecture Patterns
- Lambda handlers use RunHandler pattern from `fpl_lib.core.run_handler`
- All Lambda responses use `fpl_lib.core.responses` models
- S3 data lake: raw/ → clean/ → enriched/ → curated/ layers
- Hive-style partitioning: season={season}/gameweek={gw}/
- Parquet for all processed data (zstd compression)
- Great Expectations for data validation at each layer
- DLQ pattern: failed records → s3://fpl-data-lake-dev/dlq/

## LLM Integration
- Claude API via anthropic Python SDK
- Haiku for bulk enrichment, Sonnet for complex reasoning
- Prompts versioned in services/enrich/src/fpl_enrich/prompts/v{N}/
- Langfuse for observability (all LLM calls must be traced)
- Structured JSON outputs validated with Pydantic

## AWS
- Profile: fpl-dev (eu-west-2)
- Terraform state: s3://fpl-dev-tf-state
- All resources tagged with: Project=fpl-platform, ManagedBy=terraform

## Testing
- pytest with markers: @pytest.mark.unit, @pytest.mark.integration, @pytest.mark.slow
- Mock external services (S3, APIs, LLMs) in unit tests
- Integration tests hit real APIs (marked slow, not run in CI by default)

## Git Workflow
- **Always branch off main** — never commit directly to main (branch protection is enforced)
- **Branch naming:** `{type}/{short-description}` — e.g. `feat/fpl-api-collector`, `fix/s3-client-timeout`, `chore/update-deps`
- Types mirror Conventional Commits: `feat`, `fix`, `docs`, `chore`, `test`, `refactor`, `ci`
- Open a PR, wait for CI to pass, then merge — no direct pushes to main

## Important: Don't...
- Hardcode credentials anywhere (use AWS Secrets Manager)
- Skip type hints on public functions
- Merge to main without PR + passing checks
- Push directly to main (branch protection will flag it)
- Use LangChain for the pipeline (direct API calls — see ADR-0003)
