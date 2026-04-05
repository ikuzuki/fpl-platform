# ADR-0011: Parallel Step Functions States for Collection and Enrichment

## Status
Accepted

## Date
2026-04-05

## Context
Two sections of the pipeline were running sequentially where parallelism is both safe and beneficial:

**Data collection:** The 3 collectors (FPL API, Understat, News) hit independent external APIs with no data dependencies between them. Running sequentially added ~30s of unnecessary latency.

**LLM enrichment:** The 4 enrichers ran within a single Lambda. At Tier 1 rate limits (50 RPM, 10K output TPM), processing 300 players takes ~6 minutes — tight against Lambda's 15-minute max timeout. One enricher's failure (e.g. Sonnet 404) would take down all four, and retry logic had to be duplicated in application code rather than leveraging Step Functions' built-in retry.

## Options Considered

### 1. Keep sequential pipeline (rejected)
Simple but wastes time on collection and doesn't solve enricher failure isolation or timeout constraints.

### 2. Move enrichment to ECS Fargate (rejected)
No timeout limit, but adds significant infrastructure complexity (task definitions, VPC, service discovery) for a workload that runs once per week. Overkill at current scale.

### 3. Parallel states for both collection and enrichment (chosen)
Use Step Functions `Parallel` state for independent workloads. Collectors run concurrently since they hit different APIs. Enrichers run as separate Lambdas with a merge step.

## Decision

### Parallel collectors
Replace sequential Collect → Check → Collect → Check chain with:

```
CollectParallel (Parallel) ──┬── CollectFPLData
                             ├── CollectUnderstat
                             └── CollectNews
```

All 3 collectors run concurrently. The Parallel state's Catch block handles any failure. Per-collector Retry blocks handle transient API errors independently.

### Parallel enrichers
Replace the single `EnrichWithLLM` Task with:

```
EnrichParallel (Parallel) ──┬── EnrichPlayerSummary (Haiku, 5 RPM)
                            ├── EnrichInjurySignal (Haiku, 5 RPM)
                            ├── EnrichSentiment (Haiku, 5 RPM)
                            └── EnrichFixtureOutlook (Sonnet, 15 RPM)
                            │
                     MergeEnrichments (Task)
```

All 4 enricher Lambdas share the same ECR image (`fpl-enrich`) but use different handler entry points. Each writes its output to a separate S3 key under `enriched/{enricher_name}/season={season}/gameweek={gw}/`. The merge Lambda reads all 4 outputs and combines them into the final `enriched/player_summaries/` Parquet.

Each enricher uses dual rate control: `asyncio.Semaphore(2)` caps in-flight requests to avoid concurrent connection 429s, and a `RateLimiter` caps RPM. The 3 Haiku Lambdas each target 5 RPM (15 RPM total against the 50 RPM model limit, ~10.5K output TPM against the 10K limit). Sonnet runs alone against its own model limit at 15 RPM.

## Consequences
**Easier:**
- Collection completes in ~15s instead of ~45s (limited by slowest collector)
- Each enricher gets its own 900s timeout — total enrichment can take up to 15 min per enricher
- Step Functions handles retry per collector and per enricher independently
- Failure is isolated — sentiment failing doesn't block player summaries, news failing doesn't block FPL data
- Can independently tune timeout, memory, and concurrency per Lambda

**Harder:**
- 5 enricher Lambda modules instead of 1 (4 enrichers + 1 merger), 11 total Lambdas in the pipeline
- Step Function definition is more complex (2 Parallel states with branches)
- Merge step adds latency (~5-10s) and another failure point
- Rate limits are per-model not per-Lambda, so 3 Haiku Lambdas running simultaneously must collectively stay under 50 RPM / 10K output TPM
