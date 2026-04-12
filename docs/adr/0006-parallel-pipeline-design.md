# ADR-0006: Parallel Pipeline Design

## Status
Accepted

## Date
2026-04-05

## Context
The enrichment pipeline originally ran four enrichers within a single Lambda. At Tier 1 rate limits (50 RPM, 10K output TPM), processing 300 players took ~6 minutes — tight against Lambda's 15-minute max timeout. One enricher's failure (e.g. Sonnet 404) took down all four, and retry logic had to be duplicated in application code rather than leveraging Step Functions' built-in retry.

Data collection had a similar problem: 3 collectors (FPL API, Understat, News) hit independent APIs sequentially, adding ~30s of unnecessary latency.

## Options Considered

### 1. Keep sequential pipeline (rejected)
Simple but doesn't solve enricher failure isolation or timeout risk.

### 2. Move enrichment to ECS Fargate (rejected)
No timeout limit, but adds significant infrastructure complexity (task definitions, VPC, service discovery) for a workload that runs once per week.

### 3. Parallel Step Functions states (chosen)
Use `Parallel` state for independent workloads. Step Functions handles retry and failure isolation per branch.

## Decision

### Parallel enrichment (the important part)
Replace the single `EnrichWithLLM` Task with separate Lambdas per enricher:

```
EnrichParallel (Parallel) ──┬── EnrichPlayerSummary (Haiku, 5 RPM)
                            ├── EnrichInjurySignal (Haiku, 5 RPM)
                            ├── EnrichSentiment (Haiku, 5 RPM)
                            └── EnrichFixtureOutlook (Sonnet, 15 RPM)
                            │
                     MergeEnrichments (Task)
```

All 4 Lambdas share the same ECR image (`fpl-enrich`) but use different handler entry points. Each writes to `enriched/{enricher_name}/season={season}/gameweek={gw}/`. A merge Lambda combines the 4 outputs into the final `enriched/player_summaries/` Parquet.

### Rate control

Each enricher runs as a separate Lambda, so rate limiting is per-Lambda rather than centralised. Rate control uses dual mechanisms:
- `asyncio.Semaphore(2)` — caps in-flight requests to avoid concurrent connection 429s
- `RateLimiter(rpm)` — caps request rate to stay within RPM and output TPM limits

| Lambda | Model | RPM | Rationale |
|--------|-------|-----|-----------|
| PlayerSummary | Haiku | 5 | 3 Haiku Lambdas share 50 RPM / 10K output TPM |
| InjurySignal | Haiku | 5 | |
| Sentiment | Haiku | 5 | |
| FixtureOutlook | Sonnet | 15 | Runs alone against its own model limit |

**Why not a DynamoDB capacity lock?** At current scale (one weekly pipeline, ~150 API calls), a distributed lock adds a DynamoDB table, a capacity_manager Lambda, 3 additional Step Function states, and deadlock prevention logic — infrastructure sitting idle 99.99% of the time. The enrichment handler already catches `anthropic.RateLimitError` and falls back to cached data.

### Parallel collection
The 3 collectors hit independent APIs with no data dependencies. Parallel execution reduces collection from ~45s to ~15s (limited by slowest collector). Per-collector Retry blocks handle transient API errors independently.

## Consequences
**Easier:**
- Each enricher gets its own 900s timeout — total enrichment can take up to 15 min per enricher
- Failure is isolated — sentiment failing doesn't block player summaries
- Step Functions handles retry per enricher independently
- Can independently tune timeout, memory, and concurrency per Lambda

**Harder:**
- 5 enricher modules instead of 1 (4 enrichers + 1 merger), 11 total Lambdas in the pipeline
- Step Function definition is more complex (2 Parallel states with branches)
- Merge step adds latency (~5-10s) and another failure point
- Rate limits are per-model not per-Lambda — 3 Haiku Lambdas running simultaneously must collectively stay under 50 RPM / 10K output TPM
