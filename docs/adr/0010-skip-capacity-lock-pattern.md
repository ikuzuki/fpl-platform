# ADR-0010: Skip DynamoDB Capacity Lock for Enrichment Pipeline

## Status
Accepted

## Context
A DynamoDB-based semaphore pattern (AcquireEnrichmentLock / ReleaseEnrichmentLock in Step Functions) is a best practice for preventing concurrent pipeline executions from overwhelming shared LLM API rate limits. This was considered for the FPL enrichment pipeline.

## Decision
We will **not** implement the capacity lock pattern for the FPL pipeline at this stage.

## Rationale

**Scale doesn't justify the complexity:**
- One pipeline, one weekly trigger (Tuesday 8am UTC), ~200 API calls per run
- Claude Haiku handles thousands of requests/minute — our weekly run is a rounding error
- Even overlapping a backfill with a scheduled run is well within limits

**Existing fallback is sufficient:**
- The enrichment handler already catches `anthropic.RateLimitError` and falls back to cached previous-gameweek data
- This provides graceful degradation without additional infrastructure

**Complexity cost:**
- A capacity lock requires: DynamoDB table, capacity_manager Lambda, 3 additional Step Function states (Acquire, Release, ReleaseOnFailure), deadlock prevention logic
- This infrastructure would sit idle 99.99% of the time

## Consequences
- If we later add concurrent pipelines or significantly increase call volume, we should implement the lock pattern
- The `RateLimitError` fallback in the enricher handler is the safety net
- No DynamoDB table or capacity_manager Lambda needed at this scale
