# ADR-0004: LLM Cost Optimisation — Model Selection, Batching, and Input Filtering

## Status
Accepted (updated 2026-04-05)

## Date
2026-04-04

## Context
The enrichment pipeline runs four enrichers per gameweek across 300 players (top by ownership, filtered from ~825 total). LLM API costs scale with token volume, and different tasks have different complexity requirements. We needed a strategy that balances cost, quality, and latency across three dimensions: model selection, batch sizing, and input token efficiency.

## Options Considered

### Model selection

**1. Single model for everything (rejected)**
Use Sonnet for all enrichers. Simpler code, no model-switching logic.

Rejected because: Sonnet at $3/$15 per MTok (in/out) would cost ~$5-8 per gameweek for classification tasks that Haiku handles equally well at $0.25/$1.25 per MTok. Over 38 gameweeks, that's ~$150-300 of unnecessary spend.

**2. Haiku for everything (rejected)**
Use Haiku for all enrichers including fixture outlook.

Rejected because: Fixture outlook requires reasoning about 5-game sequences, team form trends, and schedule difficulty interactions. Testing showed Haiku produced generic recommendations ("moderate difficulty") while Sonnet provided actionable analysis referencing specific fixtures.

**3. Tiered models — Haiku for classification, Sonnet for reasoning (chosen)**
Match model capability to task complexity.

### Input token efficiency

**1. Send full player dict to every enricher (rejected)**
Simple — just serialise the entire player record (~185 tokens, 35+ fields) for every LLM call.

Rejected because: Each enricher only needs 5-17 fields. Sending everything wastes 60-90% of input tokens, increases cost, and adds irrelevant context that can degrade output quality (e.g. sending ICT index data to the sentiment enricher).

**2. Per-enricher `RELEVANT_FIELDS` filter (chosen)**
Each enricher declares which fields it needs via a class variable. The base class filters the player dict before serialising to JSON, sending only relevant data to the LLM.

## Decision

### Model and batch configuration

| Enricher | Model | Batch Size | Input Fields | Tokens/player |
|----------|-------|-----------|--------------|---------------|
| Player Summary | claude-haiku-4-5 | 10 | stats, form, xG/xA (17 fields) | ~70 |
| Injury Signal | claude-haiku-4-5 | 10 | status, news, chance_of_playing, news_articles (7 fields) | ~25 + articles |
| Sentiment | claude-haiku-4-5 | 10 | web_name, team, news_articles (3 fields) | ~10 + articles |
| Fixture Outlook | claude-sonnet-4-6 | 5 | form, team, upcoming_fixtures (6 fields) | ~25 + fixtures |

### Input filtering pattern

```python
class FPLEnricher(ABC):
    RELEVANT_FIELDS: list[str] | None = None  # None = send everything

    def _prepare_item(self, item: dict[str, Any]) -> dict[str, Any]:
        if self.RELEVANT_FIELDS is None:
            return item
        return {k: v for k, v in item.items() if k in self.RELEVANT_FIELDS}
```

Each enricher overrides `RELEVANT_FIELDS` with exactly the fields its prompt references. This is enforced at the base class level so new enrichers get filtering by default.

### Player filtering

Only the top 300 players by `selected_by_percent` are enriched. The remaining ~525 players appear in the final Parquet without enrichment columns. This reduces total API calls from ~350 (700 players) to ~150 (300 players).

## Cost estimate (per gameweek, 300 players)

| Enricher | API Calls | Est. Input Tokens | Est. Output Tokens | Est. Cost |
|----------|-----------|-------------------|--------------------| ----------|
| Player Summary (Haiku) | 30 | ~21K | ~15K | ~$0.02 |
| Injury Signal (Haiku) | 30 | ~8K + articles | ~10K | ~$0.01 |
| Sentiment (Haiku) | 30 | ~3K + articles | ~10K | ~$0.01 |
| Fixture Outlook (Sonnet) | 60 | ~15K + fixtures | ~42K | ~$0.68 |
| **Total** | **~150** | **~50K+** | **~77K** | **~$0.72** |

Fixture outlook on Sonnet still dominates (~94%). Over a full 38-gameweek season: **~$27**.

Previous estimate before input filtering: ~$1.42/GW, ~$54/season. Input filtering saves ~50% on Haiku enrichers.

## Consequences
**Easier:**
- Haiku keeps bulk enrichment cheap (~$0.04/GW for 3 enrichers)
- `RELEVANT_FIELDS` is self-documenting — reading the enricher class tells you exactly what data it uses
- Aggressive batching reduces total API calls from ~1,214 (original) to ~150
- Less input noise improves LLM output quality and consistency
- Cost report per gameweek enables tracking and alerting on spend drift

**Harder:**
- Two models means two pricing tiers to track and two potential points of failure
- Batch size tuning is empirical — too large degrades output quality, too small wastes calls
- `RELEVANT_FIELDS` must be kept in sync with prompt templates — if a prompt references a field not in the list, the LLM won't see it
- Model version pinning (`claude-haiku-4-5-20251001`) means manual updates when new versions release
