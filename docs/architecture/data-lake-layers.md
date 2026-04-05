# Data Lake Layer Design

Single S3 bucket (`fpl-data-lake-dev`) with four processing layers and a dead-letter queue. Each layer represents a data quality stage with clear contracts on format, schema, and retention.

For full rationale, see [ADR-0002: S3 Data Lake Design](../adr/0002-s3-data-lake-design.md).

## Layer Flow

```mermaid
graph LR
    subgraph Sources["External APIs"]
        A1["FPL API"]
        A2["Understat"]
        A3["RSS Feeds"]
    end

    subgraph Raw["raw/ · JSON"]
        R1["fpl-api/season=2025-26/<br/>bootstrap/{ts}.json<br/>fixtures/{ts}.json<br/>gameweek-live/{ts}.json"]
        R2["understat/season=2025-26/<br/>players/{id}/{ts}.json"]
        R3["news/date=2026-04-01/<br/>rss_articles.jsonl"]
    end

    subgraph Clean["clean/ · Parquet+zstd"]
        C1["players/season=2025-26/<br/>gameweek=01/players.parquet<br/><i>30+ cols, typed, deduped</i>"]
    end

    subgraph Enriched["enriched/ · Parquet+zstd"]
        E0["player_summaries/<br/>injury_signals/<br/>sentiments/<br/>fixture_outlooks/"]
        E1["player_summaries/season=2025-26/<br/>gameweek=01/summaries.parquet<br/><i>Merged from 4 enrichers</i>"]
    end

    subgraph Curated["curated/ · Parquet+zstd"]
        CU1["dashboard/season=2025-26/<br/>latest.parquet"]
        CU2["transfer_picks/<br/>fixture_ticker/<br/>team_strength/"]
    end

    subgraph DLQ["dlq/ · JSONL"]
        D1["season=2025-26/<br/>gameweek=01/<br/>validation_failures.jsonl"]
    end

    A1 --> R1
    A2 --> R2
    A3 --> R3

    R1 -->|"validate + transform"| C1
    R2 -->|"validate + transform"| C1
    R3 -->|"attach to players"| C1

    R1 -.->|"invalid records"| D1

    C1 -->|"LLM enrichment"| E0
    E0 -->|"merge"| E1
    E1 -->|"curate"| CU1
    E1 -->|"curate"| CU2
```

## Layer Contracts

| Layer | Format | Partitioning | Retention | Purpose |
|-------|--------|-------------|-----------|---------|
| `raw/` | JSON | `season=` / `date=` | 90 days | Preserve API responses exactly as received |
| `clean/` | Parquet (zstd) | `season=` / `gameweek=` | Indefinite | Validated, typed, deduplicated — predictable LLM inputs |
| `enriched/` | Parquet (zstd) | `season=` / `gameweek=` | Indefinite | LLM-augmented data, expensive to regenerate |
| `curated/` | Parquet (zstd) | `season=` | Indefinite | Dashboard-ready aggregations and derived metrics |
| `dlq/` | JSONL | `season=` / `gameweek=` | 30 days | Failed validation records for investigation |

## Partitioning

All layers use Hive-style partition keys, enabling:

- **Query pruning** — Athena, DuckDB, and pandas can skip irrelevant partitions
- **Idempotency** — check if output exists at a prefix before processing; skip if present
- **Lifecycle rules** — S3 lifecycle scoped by prefix (raw/ → Infrequent Access at 30d, expires at 90d)

```
s3://fpl-data-lake-dev/
  raw/fpl-api/season=2025-26/bootstrap/20260401T080000Z.json
  clean/players/season=2025-26/gameweek=01/players.parquet
  enriched/player_summaries/season=2025-26/gameweek=01/summaries.parquet
  curated/dashboard/season=2025-26/latest.parquet
  dlq/season=2025-26/gameweek=01/validation_failures.jsonl
```

## Why Four Layers

Each layer exists because removing it would create a concrete problem:

| Without this layer... | What breaks |
|-----------------------|------------|
| **raw/** | Can't reprocess without re-fetching APIs (rate-limited, may change) |
| **clean/** | LLM enrichment receives unvalidated, untyped data — unpredictable outputs |
| **enriched/** | Dashboard must re-run expensive LLM calls to get summaries |
| **curated/** | Every consumer repeats the same joins and aggregations |

## Idempotency Pattern

Each pipeline step checks whether its output already exists before processing:

```python
if not force and self._output_exists(prefix):
    return CollectionResponse(status="success", records_collected=0, output_path=prefix)
```

This works because each step writes a **single file per invocation**. S3 `PutObject` is atomic — the file either fully exists or doesn't. No partial write scenario is possible with single-file outputs.

The `force=True` parameter overrides the check for backfills and manual reprocessing.
