# ADR-0011: Parallel Enricher Lambdas via Step Functions

## Status
Accepted

## Date
2026-04-05

## Context
The enrichment step runs 4 LLM enrichers (player summary, injury signal, sentiment, fixture outlook) sequentially within a single Lambda. At Tier 1 rate limits (50 RPM, 10K output TPM), processing 300 players takes ~6 minutes. This is tight against Lambda's 15-minute max timeout and leaves no room for retries, rate limit backoffs, or scaling up the player count.

The single-Lambda design also means one enricher's failure (e.g. Sonnet 404) takes down all four, and retry logic must be duplicated in application code rather than leveraging Step Functions' built-in retry.

## Options Considered

### 1. Keep single Lambda, lower player count (rejected)
Reduce to 200 players to stay under timeout. Simple but sacrifices coverage and doesn't solve the failure isolation problem.

### 2. Move to ECS Fargate (rejected)
No timeout limit, but adds significant infrastructure complexity (task definitions, VPC, service discovery) for a workload that runs once per week for ~6 minutes. Overkill at current scale.

### 3. Split into parallel Lambdas via Step Functions Parallel state (chosen)
Each enricher runs as its own Lambda invocation within a Step Functions `Parallel` state. A final merge Lambda combines the outputs.

## Decision
Replace the single `EnrichWithLLM` Task with:

```
EnrichParallel (Parallel) ──┬── EnrichPlayerSummary (Task)
                            ├── EnrichInjurySignal (Task)
                            ├── EnrichSentiment (Task)
                            └── EnrichFixtureOutlook (Task)
                            │
                     MergeEnrichments (Task)
```

All 4 enricher Lambdas share the same ECR image (`fpl-enrich`) but use different handler entry points. Each writes its output to a separate S3 key under `enriched/{enricher_name}/season={season}/gameweek={gw}/`. The merge Lambda reads all 4 outputs and combines them into the final `enriched/player_summaries/` Parquet.

Each enricher gets its own rate limiter instance (no longer shared), so they can each sustain ~20 RPM independently — the rate limits are per-model, and 3 Haiku enrichers sharing 50 RPM still works since Step Functions staggers their start times slightly.

## Consequences
**Easier:**
- Each enricher gets its own 900s timeout — total enrichment can take up to 15 min per enricher
- Step Functions handles retry per enricher (e.g. fixture outlook can retry without re-running summaries)
- Failure is isolated — sentiment failing doesn't block player summaries
- Can independently tune timeout, memory, and concurrency per enricher
- Natural path to scaling: can increase player count per enricher independently

**Harder:**
- 5 Lambda modules instead of 1 (4 enrichers + 1 merger)
- Step Function definition is more complex (Parallel state with branches)
- Merge step adds latency (~5-10s) and another failure point
- Rate limits are per-model not per-Lambda, so 3 Haiku Lambdas running simultaneously could collectively exceed 50 RPM — each should target ~15 RPM
