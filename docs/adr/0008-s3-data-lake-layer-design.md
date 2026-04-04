# ADR-0008: S3 Data Lake Layer Design

## Status
Accepted

## Date
2026-04-04

## Context
The pipeline collects data from multiple sources (FPL API, Understat, news), validates it, transforms it, enriches it with LLMs, and serves it to a dashboard. We needed a storage layout that supports this multi-stage processing while keeping data discoverable and preventing raw/processed data from mixing.

## Options Considered

### 1. Flat structure with naming conventions (rejected)
All data in one S3 prefix, distinguished by file naming: `fpl_bootstrap_raw_2025-26_gw01.json`, `fpl_bootstrap_clean_2025-26_gw01.parquet`.

**Rejected because:** No structural enforcement of data quality stages. Easy to accidentally read raw data where clean is expected. IAM can't scope permissions by processing stage.

### 2. Separate S3 buckets per layer (rejected)
`fpl-raw-dev`, `fpl-clean-dev`, `fpl-enriched-dev`, `fpl-curated-dev` — one bucket per quality tier.

**Rejected because:** Multiplies infrastructure (4 buckets, 4 lifecycle configs, 4 IAM statements). Cross-bucket operations (e.g., reading raw and writing clean) require broader S3 permissions. AWS account limits on buckets are generous but this doesn't scale well to multiple datasets.

### 3. Single bucket with prefix-based layers and Hive partitioning (chosen)
One `fpl-data-lake-dev` bucket with top-level prefixes defining data quality stages and Hive-style partition keys for discovery.

## Decision
Single S3 bucket with four data layers plus a dead-letter queue, using Hive-style partitioning:

```
s3://fpl-data-lake-dev/
  raw/              <- API responses as-is (JSON)
    fpl-api/season=2025-26/bootstrap/{timestamp}.json
    understat/season=2025-26/players/{id}/{timestamp}.json
    news/date=2026-04-01/rss_articles.jsonl
  clean/            <- Validated, typed, deduplicated (Parquet)
    players/season=2025-26/gameweek=01/players.parquet
  enriched/         <- LLM-augmented data (Parquet)
    player_summaries/season=2025-26/gameweek=01/summaries.parquet
  curated/          <- Dashboard-ready aggregations (Parquet)
    dashboard/season=2025-26/latest.parquet
  dlq/              <- Failed records for investigation
    season=2025-26/gameweek=01/validation_failures.jsonl
```

### Format choices
- **Raw**: JSON — preserve original API response exactly as received
- **Clean/Enriched/Curated**: Parquet with zstd compression — columnar, compact, schema-enforced, fast for analytics
- **DLQ**: JSONL — human-readable for debugging, one record per line

### Partitioning
Hive-style keys (`season=`, `gameweek=`, `date=`) enable:
- Partition pruning in queries (Athena, DuckDB)
- Natural S3 prefix-based idempotency checks (see ADR-0006)
- Lifecycle rules scoped by prefix (raw/ expires at 90 days, dlq/ at 30 days)

## Why four layers (not three or five)
- **Raw** exists to preserve source data for reprocessing without re-fetching APIs
- **Clean** exists because validation and type-casting must happen before enrichment — LLM inputs must be predictable
- **Enriched** is separate from clean because LLM enrichment is expensive and may fail — clean data should be usable independently
- **Curated** exists for dashboard-specific aggregations that join across sources — downstream consumers shouldn't repeat this joining logic
- A fifth "staging" layer was considered and rejected — clean serves this purpose

## Why Parquet with zstd (not Delta Lake, Iceberg, or CSV)
- **Delta Lake / Iceberg**: Excellent for ACID transactions and time-travel, but require a metastore (Glue Catalog) and add complexity. Our pipeline is append-only per gameweek with no concurrent writers — ACID is overkill.
- **CSV**: No schema enforcement, no compression, slow to read. Only advantage is human readability, which JSONL in the DLQ handles for debugging.
- **Parquet + zstd**: Industry standard for columnar analytics. zstd gives better compression ratios than snappy at comparable speed. PyArrow reads/writes Parquet natively, and Athena/DuckDB query it directly.

## Consequences
**Easier:**
- One bucket to manage, one set of lifecycle rules, one IAM policy
- Hive partitioning is universally supported (Athena, Spark, DuckDB, pandas)
- Each layer has a clear contract: raw=JSON, clean/enriched/curated=Parquet
- Lifecycle rules naturally scope by prefix (raw/ transitions to IA, dlq/ expires)
- Easy to add new data sources — just create a new prefix under raw/

**Harder:**
- No ACID transactions — if the transform Lambda fails mid-write, a partial Parquet could exist (mitigated by atomic S3 PUT — see ADR-0006)
- No schema registry — schema evolution must be managed manually via `schema_version` in Parquet metadata
- Single bucket means a compromised Lambda could read/write any layer (mitigated: IAM scoping by prefix is possible but not implemented yet)
