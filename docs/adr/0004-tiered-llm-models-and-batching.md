# ADR-0004: Tiered LLM Model Selection and Batch Processing

## Status
Accepted (updated 2026-04-05)

## Date
2026-04-04

## Context
The enrichment pipeline runs four enrichers per gameweek across ~700 players. LLM API costs scale with token volume, and different tasks have different complexity requirements. We needed a model selection and batching strategy that balances cost, quality, and latency.

## Options Considered

### 1. Single model for everything (rejected)
Use Sonnet for all enrichers. Simpler code, no model-switching logic.

**Rejected because:** Sonnet at $3/$15 per MTok (in/out) would cost ~$5-8 per gameweek for classification tasks that Haiku handles equally well at $0.25/$1.25 per MTok. Over 38 gameweeks, that's ~$150-300 of unnecessary spend.

### 2. Haiku for everything (rejected)
Use Haiku for all enrichers including fixture outlook.

**Rejected because:** Fixture outlook requires reasoning about 5-game sequences, team form trends, and schedule difficulty interactions. Testing showed Haiku produced generic recommendations ("moderate difficulty") while Sonnet provided actionable analysis referencing specific fixtures.

### 3. Tiered models with task-appropriate batch sizes (chosen)
Match model capability to task complexity. Batch simple tasks aggressively, keep complex tasks isolated.

## Decision
Use Haiku for classification/summarisation and Sonnet for multi-step reasoning. Batch sizes tuned per enricher, favouring larger batches for cost efficiency.

| Enricher | Model | Batch Size | Reasoning |
|----------|-------|-----------|-----------|
| Player Summary | claude-haiku-4-5 | 10 | Form summarisation is templated; Haiku handles 10 players per call comfortably |
| Injury Signal | claude-haiku-4-5 | 10 | Binary classification (risk score 0-10); minimal per-item context |
| Sentiment | claude-haiku-4-5 | 10 | Simple sentiment scoring from media mentions; bulk-friendly |
| Fixture Outlook | claude-sonnet-4-6 | 5 | Requires reasoning about fixture runs — batching 5 balances context size with efficiency |

All enrichers run concurrently via `asyncio.gather` with a shared `asyncio.Semaphore(5)` to stay within Tier 1 rate limits (50 RPM per model). All calls use `max_tokens=4096` and return structured JSON arrays validated with Pydantic.

## Rate limits (Tier 1)

| Model | Requests/min | Input tokens/min | Output tokens/min |
|-------|-------------|-------------------|-------------------|
| Haiku | 50 | 50K | 10K |
| Sonnet | 50 | 30K | 8K |

With 350 total API calls per gameweek and 5 max concurrent, the pipeline completes in ~4-5 minutes — well within the 900s Lambda timeout.

## Cost estimate (per gameweek, ~700 players)

Based on v1 prompt templates (~200-250 tokens each) and average player data payload (~150 tokens per item):

| Enricher | API Calls | Est. Input Tokens | Est. Output Tokens | Est. Cost |
|----------|-----------|-------------------|--------------------| ----------|
| Player Summary (Haiku) | ~70 | ~105K | ~50K | ~$0.09 |
| Injury Signal (Haiku) | ~70 | ~95K | ~35K | ~$0.07 |
| Sentiment (Haiku) | ~70 | ~95K | ~35K | ~$0.07 |
| Fixture Outlook (Sonnet) | ~140 | ~175K | ~70K | ~$1.58 |
| **Total** | **~350** | **~470K** | **~190K** | **~$1.81** |

Fixture outlook dominates cost (~87%). Over a full 38-gameweek season: ~$69. If cost becomes an issue, the first lever is reducing fixture outlook to top-200 players by ownership.

## Consequences
**Easier:**
- Haiku keeps bulk enrichment cheap (~$0.23 per gameweek for 3 enrichers)
- Aggressive batching reduces total API calls from ~1,214 (original) to ~350
- Async concurrency with shared semaphore keeps runtime under 5 minutes
- Cost report per gameweek enables tracking and alerting on spend drift
- Langfuse tracing attributes cost to each enricher type

**Harder:**
- Two models means two pricing tiers to track and two potential points of failure
- Batch size tuning is empirical — too large degrades output quality, too small wastes calls
- Model version pinning (`claude-haiku-4-5-20251001`) means manual updates when new versions release
- Shared semaphore means one slow enricher can partially block others
