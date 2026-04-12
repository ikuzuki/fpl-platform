# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Step Function: Added `CheckResolveStatus` guard before `CheckShouldRun` — prevents execution crash when `ResolveGameweek` Lambda returns a non-200 status (e.g. Cloudflare 403)
- Gameweek resolver: Added 403 retry with exponential backoff (matching `fpl_api_collector` pattern) — single-attempt fetch was failing on intermittent Cloudflare challenges

### Added
- Pipeline email notifications via EventBridge → SNS — sends email on pipeline success, failure, timeout, or abort
- Langfuse session IDs (`{season}-gw{gameweek}`) on all enrichment and curation traces — enables grouping all traces for a gameweek run in a single Langfuse session view
- Langfuse metadata (enricher name, prompt version, model, batch size) on every `enricher_batch_call` observation — enables filtering and comparing traces by enricher or prompt version
- Langfuse `output_count_valid` score on each LLM batch call — flags when the model returns fewer items than requested
- Langfuse `validation_pass_rate` score on each enricher trace — tracks what percentage of LLM outputs pass Pydantic validation
- Root conftest disables Langfuse tracing during tests (`LANGFUSE_TRACING_ENABLED=false`) to prevent polluting production dashboard with test data

### Changed
- ADR-0007: Added SSR (Next.js/Remix) as explicitly rejected option — documents why server-side rendering is unnecessary for a weekly-refresh personal dashboard

### Fixed
- Dashboard: Trends page — removed flat-line metrics (price, ownership, form, pts/m) that showed identical values across gameweeks due to bootstrap snapshot reuse; chart now tracks FPL Score only
- Dashboard: xG Efficiency scatter — axis labels showed corrupted numbers; capped domain to 99th percentile and added tick formatting
- Dashboard: Differential Radar scatter — player name missing from hover tooltip; replaced default tooltip with custom content renderer

### Changed
- Dashboard: Moved xG Efficiency, Ownership vs Value, and Momentum Heatmap charts above the player rankings table for better visibility

### Added
- Langfuse observability for curation service — `@observe(name="curate_gameweek")` tracing on the handler, matching the enrichment layer pattern
- Bootstrap infra comment documenting rationale for `AdministratorAccess` policy with OIDC-scoped trust
- CloudFront cache invalidation: EventBridge rule triggers a Lambda to invalidate `/api/v1/*` when the pipeline succeeds, so the dashboard serves fresh data immediately
- Dashboard v4: Captain Picker Decision Matrix page with weighted composite captaincy score
- Dashboard v4: Differential Radar page — scatter plot + card grid for low-ownership high-value players with sparklines
- Dashboard v4: Transfer Planner page — side-by-side player comparison with budget simulation, score pyramid, and form sparklines
- Dashboard v4: Gameweek Momentum Heatmap — FPL Score by player per gameweek (top 50 players)
- Dashboard v4: FDR number overlay in fixture grid cells for colour-blind accessibility
- Dashboard v4: Scatter outlier labels on xG Efficiency and Ownership vs Value charts (top 5 by distance)
- Dashboard v4: Position colour legend under scatter charts
- Dashboard v4: Team labels on Teams scatter chart
- Dashboard v4: Vitest + React Testing Library setup with 38 tests (utils + useApi hook)

### Changed
- Dashboard v4: Extracted PlayersPage into 5 focused sub-components (PlayerDetail, ScoreWaterfall, XgScatter, OwnershipBubble, MomentumHeatmap)
- Dashboard v4: Extracted TrendsPage into dedicated directory structure
- Dashboard v4: Created reusable useApi hook — replaced 6 duplicated useState+useEffect fetch patterns across all pages
- Dashboard v4: Moved chart colours, position colours, and score component colours into CSS custom properties (design system tokens)
- Dashboard v4: Added useSearchParams URL state sync for all page filters (position, search, sort, metric, player selection)
- Dashboard v4: Added mobile hamburger menu (md: breakpoint nav collapse)
- Dashboard v4: Added skip-to-content link, aria-sort on sortable headers, search labels, aria-pressed on filter buttons, keyboard navigation on expandable rows
- Dashboard v4: Added ErrorCard component with proper error states on all pages (replaces silent error swallowing)
- Dashboard v4: Added expand animation (CSS grid-template-rows transition) for player detail and transfer card expansion
- Dashboard v4: Footer now shows actual gameweek/season from briefing data instead of static text
- Dashboard v4: Expanded navigation to include Captain, Differentials, and Planner pages
- Dashboard v4: Shared TOOLTIP_STYLE constant for consistent Recharts tooltip styling

- Dashboard v3: Gameweek Briefing home page (top picks, injury alerts, fixture spotlight, form watch)
- Dashboard v3: Score Breakdown Waterfall in player detail panel (7 weighted components)
- Dashboard v3: xG Efficiency Scatter (Goals vs xG with diagonal reference)
- Dashboard v3: Ownership vs Value Bubble Chart (quadrant: differentials vs traps)
- Dashboard v3: Fixture Swing Chart (rolling 3-GW FDR with best-run callout)
- Dashboard v3: Expandable "Why Buy/Sell" AI cards on Transfers page (LLM summary, injury, sentiment, fixtures)
- Dashboard v3: Sentiment Timeline heatmap on Trends page
- Dashboard v3: Teams page quadrant labels and legend cleanup
- Dashboard v3: Error boundary with retry button
- Curate: score component outputs (score_form, score_value, etc.) exposed from scoring.py
- Curate: gameweek_briefing.json output with aggregated weekly signals (6 new tests)
- Dashboard v2: hero summary strip with AI Pick of the Week and KPI cards
- Dashboard v2: player table visual hierarchy (score bars, tier dividers, expand chevrons, heatmap cells)
- Dashboard v2: radar chart and styled AI analysis card in player detail panel
- Dashboard v2: dark mode with toggle and localStorage persistence
- Dashboard v2: transfer cards with coloured borders and sort controls
- Dashboard v2: teams page scatter plot (Score vs FDR quadrant analysis)
- Dashboard v2: fixture grid with team focus, FDR sum column, sort by difficulty
- Dashboard v2: skeleton loaders and empty states
- React dashboard (`web/dashboard/`) with 4 pages: Player Rankings, Fixture Ticker, Transfer Hub, Team Strength
- Static JSON output from CurateData Lambda for dashboard consumption (`public/api/v1/*.json`)
- ADR-0007: Static dashboard architecture (React SPA + pre-generated JSON on CloudFront)
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
