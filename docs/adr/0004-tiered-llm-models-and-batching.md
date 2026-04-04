# ADR-0004: Tiered LLM Model Selection and Batch Processing

## Status
Accepted

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
Use Haiku for classification/summarisation and Sonnet for multi-step reasoning. Batch sizes tuned per enricher.

| Enricher | Model | Batch Size | Reasoning |
|----------|-------|-----------|-----------|
| Player Summary | claude-haiku-4-5 | 3 | Form summarisation is templated; 3 players per call keeps summaries focused |
| Injury Signal | claude-haiku-4-5 | 5 | Binary classification (risk score 0-10); minimal per-item context |
| Sentiment | claude-haiku-4-5 | 5 | Simple sentiment scoring from media mentions; bulk-friendly |
| Fixture Outlook | claude-sonnet-4-6 | 1 | Requires reasoning about fixture runs and team strength — context isolation needed |

All calls use `max_tokens=4096` and return structured JSON arrays validated with Pydantic.

## Cost estimate (per gameweek, ~700 players)

Based on v1 prompt templates (~200-250 tokens each) and average player data payload (~150 tokens per item):

| Enricher | API Calls | Est. Input Tokens | Est. Output Tokens | Est. Cost |
|----------|-----------|-------------------|--------------------| ----------|
| Player Summary (Haiku) | ~234 | ~140K | ~70K | ~$0.12 |
| Injury Signal (Haiku) | ~140 | ~95K | ~35K | ~$0.07 |
| Sentiment (Haiku) | ~140 | ~95K | ~35K | ~$0.07 |
| Fixture Outlook (Sonnet) | ~700 | ~265K | ~140K | ~$2.90 |
| **Total** | **~1,214** | **~595K** | **~280K** | **~$3.16** |

Fixture outlook dominates cost (~92%). Over a full 38-gameweek season: ~$120. If cost becomes an issue, the first lever is reducing fixture outlook to top-200 players by ownership.

## Consequences
**Easier:**
- Haiku keeps bulk enrichment cheap (~$0.26 per gameweek for 3 enrichers)
- Batching reduces total API calls by 3-5x vs one-per-player
- Cost report per gameweek enables tracking and alerting on spend drift
- Langfuse tracing attributes cost to each enricher type

**Harder:**
- Two models means two pricing tiers to track and two potential points of failure
- Batch size tuning is empirical — too large degrades output quality, too small wastes calls
- Model version pinning (`claude-haiku-4-5-20251001`) means manual updates when new versions release
