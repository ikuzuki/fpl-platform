# ADR-0004: Tiered LLM Model Selection and Batch Processing

## Status
Accepted

## Context
The enrichment pipeline runs four enrichers per gameweek across ~700 players. LLM API costs scale with token volume, and different tasks have different complexity requirements. We needed to decide which models to use and how to batch items to optimise cost vs quality.

## Decision
Use Haiku for simple classification tasks and Sonnet for complex reasoning. Batch multiple items per LLM call where quality allows.

| Enricher | Model | Batch Size | Reasoning |
|----------|-------|-----------|-----------|
| Player Summary | claude-haiku-4-5 | 3 | Form summarisation is templated; moderate context per player |
| Injury Signal | claude-haiku-4-5 | 5 | Binary classification (injured/not); minimal reasoning needed |
| Sentiment | claude-haiku-4-5 | 5 | Simple sentiment scoring; bulk-friendly |
| Fixture Outlook | claude-sonnet-4-6 | 1 | Requires reasoning about fixture runs, team strength, and schedule — needs deeper analysis |

All calls use `max_tokens=4096` and return structured JSON arrays validated with Pydantic.

## Cost estimate (per gameweek, ~700 players)
- Haiku calls: ~234 batched calls (3 enrichers) at ~$0.25/MTok in, $1.25/MTok out
- Sonnet calls: ~700 individual calls at ~$3/MTok in, $15/MTok out
- Fixture outlook dominates cost — batch size of 1 is the tradeoff for reasoning quality

## Consequences
**Easier:**
- Haiku keeps bulk enrichment cheap (~$0.10-0.30 per gameweek for 3 enrichers)
- Batching amortises per-call overhead and reduces total API calls by 3-5x
- Cost report per gameweek enables tracking and alerting on spend drift
- Langfuse tracing attributes cost to each enricher type

**Harder:**
- Fixture outlook is expensive relative to others — may need caching or reducing to top-N players
- Batch size tuning is empirical — too large degrades output quality, too small wastes API calls
- Model version pinning means manual updates when new model versions release
