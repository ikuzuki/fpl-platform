# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Architecture docs: system overview, data lake layers, LLM enrichment flow (Mermaid diagrams, render on GitHub)
- Merged `docs/diagrams/` into `docs/architecture/`
- Curate service (`services/curate/`) — derives 4 dashboard-ready datasets from enriched data
- Composite FPL score (0-100) blending form, value, fixtures, xG overperformance, ICT, injury risk, and ownership momentum
- Player dashboard curated table (300 enriched players with derived fields and rankings)
- Fixture ticker curated table (FDR heatmap data for remaining gameweeks)
- Transfer picks curated table (buy/sell/hold/watch recommendations with reasoning)
- Team strength curated table (20-team aggregation with avg FPL score, squad value, top scorer)
- `CurationResult` response model in `fpl_lib.core.responses`
- 46 unit tests for curate service (models, scoring, curators, handler)
- CurateData Lambda in Step Functions pipeline (after MergeEnrichments)
- ECR repository and Lambda module for curate service in Terraform
- Understat xG/xA join in player transformer — matches by normalised name, adds 8 Understat columns (understat_xg, understat_xa, understat_npxg, etc.)
- News articles attached to players for injury/sentiment enrichers via name matching
- Fixture data attached to players for fixture outlook enricher (next 5 GWs with difficulty ratings)
- Premier League keyword filter on RSS news collector (removes non-football content)
- 3 new unit tests for Understat join (match, unmatched, empty)
- Step Functions pipeline: 9-state machine (Collect FPL → Understat → News → Validate → Check → Transform → Enrich → Succeed/Fail)
- 6 Lambda modules in dev environment (fpl-api-collector, understat-collector, news-collector, validator, transform, enricher)
- EventBridge schedule: Tuesday 8am UTC weekly trigger
- Backfill script (`python -m fpl_data.scripts.backfill`) for historical gameweek processing
- Player data transformer (`flatten_player_data`) — selects 30+ key columns from 105 raw fields, casts types, adds metadata
- Deduplication utility for clean data
- Transformation Lambda handler with idempotency (skip if output exists, `force=True` to override)
- Clean Parquet output with zstd compression and `schema_version` metadata at `clean/players/season={season}/gameweek={gw}/`
- New column detection: logs warning when raw API adds unexpected fields
- 10 unit tests for transformer, deduplication, and handler
- Data validation engine with schema-driven checks (column presence, not-null, uniqueness, value ranges)
- Raw-data validation schemas (`PLAYER_EXPECTATIONS`, `FIXTURE_EXPECTATIONS`) using FPL API column names
- Validation Lambda handler with DLQ writing for failed records
- 10 unit tests for validation engine, handler, and DLQ
- News collector (`NewsCollector`) with RSS feed parsing (BBC, Sky Sports, Guardian)
- Date-based filtering for RSS entries using `published_parsed` time struct
- 4 unit tests for news collector with mocked feedparser
- Understat collector (`UnderstatCollector`) using POST API for xG/xA stats — league-level and per-player collection
- Rate limiting (1.5s sleep) for Understat requests
- Season format conversion (`2025-26` → `2025` for Understat API)
- 10 unit tests for Understat collector with mocked httpx
- Langfuse observability: `@observe` decorators on `_call_llm` and enrichment handler for LLM call tracing
- `EnrichSettings` config class extending `FPLSettings` with Langfuse and Anthropic credentials
- Four concrete enrichers: PlayerSummaryEnricher, InjurySignalEnricher, SentimentEnricher, FixtureOutlookEnricher
- Pydantic output models for all enricher outputs (structured validation)
- Enrichment Lambda handler with Secrets Manager integration, cost tracking, and fallback handling
- FPLEnricher abstract base class with batch processing, LLM call, output validation, and token tracking
- Prompt loader utility (`load_prompt()`) for versioned prompt templates
- Four v1 prompt templates: player_summary, injury_signal, sentiment, fixture_outlook
- Dev environment Terraform resources — ECR repo, S3 data lake + cost reports buckets, SNS pipeline alerts, Secrets Manager (Anthropic API key, Langfuse keys), shared Lambda IAM role
- Lambda module: optional `execution_role_arn` for shared external role support
- S3 data lake module: configurable `name` variable for multi-bucket reuse
- Step Functions module: CloudWatch log group with execution logging
- ADR-0002: S3 data lake design (layers, idempotency, container deployment, Hive partitioning, Parquet+zstd)
- ADR-0003: Direct Anthropic API over LangChain
- ADR-0004: LLM cost optimisation (model tiering, input filtering, rate limiting, capacity lock skip)
- ADR-0005: Prompt versioning and LLM observability (directory-based versioning, Langfuse tracing)
- ADR-0006: Parallel pipeline design (Step Functions parallel states for collection and enrichment)

### Changed
- Enricher base class now fully async: `AsyncAnthropic` client, `asyncio.Semaphore` for rate limiting, `asyncio.gather` for concurrent batch processing
- Enrichment handler runs all 4 enrichers in parallel with shared semaphore (max 5 concurrent API calls for Tier 1 limits)
- Structured logging in RunHandler: `[START]`, `[SUCCESS]`, `[ERROR]` with duration and params
- `[ANTHROPIC]`, `[FPL API]`, `[UNDERSTAT]`, `[RSS]` prefixed logging on all external API calls
- Step Functions log level configurable (default `ALL` for full execution tracing)
- Enricher Lambda timeout increased to 900s (Lambda max)
- ADRs consolidated from 11 to 6: merged related decisions (data lake + idempotency + containers, prompt versioning + observability, parallel design), dropped low-signal entries (Terraform over CDK)
- Lambda module: log retention 14d → 30d, default memory 256 → 512 MB
- S3 data lake module: added raw/ prefix expiration at 90 days

### Fixed
- ECR module: tag mutability now configurable (default MUTABLE) — fixes deploy failure where `:latest` push was rejected by IMMUTABLE policy
- S3 data lake lifecycle: transition days (30) now less than expiration days (90) to satisfy AWS API constraint
- S3 data lake lifecycle rules now conditional (`enable_data_lake_lifecycle`) so non-data-lake buckets skip raw/dlq rules
- ECR repo naming order matches deploy.yml convention (`fpl-{name}-{env}` not `fpl-{env}-{name}`)
- Dev environment now creates 3 ECR repos (data, enrich, agent) matching the per-service deploy matrix

## [0.1.0] - 2026-04-04

### Added
- Monorepo structure with 5 service stubs (`data`, `enrich`, `etl`, `agent`, `stream`)
- Shared library (`libs/fpl_lib/`) — `ExceptionCollector`, `FPLSettings`, `RunHandler`, `S3Client`, Pydantic domain models (`Player`, `Fixture`), validators, date utils
- Terraform bootstrap — S3 state bucket, DynamoDB lock table, GitHub OIDC provider, CI/CD IAM role (`FPL-Dev-CICD-Role`), budget alerts
- Terraform modules — `lambda`, `s3-data-lake`, `step-function`, `ecr`
- GitHub Actions CI — path-filtered lint/test on PRs, `terraform plan` on infra changes
- GitHub Actions deploy — `terraform apply` and ECR build/Lambda deploy on merge to main
- Pre-commit hooks — ruff, mypy, terraform fmt
- Makefile with `install`, `lint`, `format`, `test`, `check` targets
- Claude Code config — `CLAUDE.md`, path-specific rules, 4 custom skills, MCP server config
- ADR-0001 (monorepo architecture)
- Data dictionary, runbook, PR/issue templates
- 15 passing unit tests (`ExceptionCollector`, `FPLSettings`, `S3Client`)
