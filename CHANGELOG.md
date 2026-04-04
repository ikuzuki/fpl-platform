# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
- ADR-0003: Direct Anthropic API over LangChain
- ADR-0004: Tiered LLM model selection and batch processing (Haiku vs Sonnet, batch sizes)
- ADR-0005: Prompt versioning by directory
- ADR-0006: S3 prefix-based idempotency
- ADR-0007: Container images for Lambda over zip packages

### Changed
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
- ADR-0001 (monorepo architecture), ADR-0002 (Terraform over CDK)
- Data dictionary, runbook, PR/issue templates
- 15 passing unit tests (`ExceptionCollector`, `FPLSettings`, `S3Client`)
