# ADR-0002: S3 Data Lake Design

## Status
Accepted

## Date
2026-04-04

## Context
The pipeline collects data from multiple sources (FPL API, Understat, news), validates it, transforms it, enriches it with LLMs, and serves it to a dashboard. We needed a storage layout that supports multi-stage processing while keeping data discoverable and preventing raw/processed data from mixing. The design also needed to address idempotency (Step Functions retries can produce duplicates) and Lambda deployment packaging (our dependencies exceed the 250 MB zip limit).

## Options Considered

### Storage layout

**1. Flat structure with naming conventions (rejected)**
All data in one S3 prefix, distinguished by file naming: `fpl_bootstrap_raw_2025-26_gw01.json`.

Rejected because: No structural enforcement of data quality stages. Easy to accidentally read raw data where clean is expected. IAM can't scope permissions by processing stage.

**2. Separate S3 buckets per layer (rejected)**
`fpl-raw-dev`, `fpl-clean-dev`, `fpl-enriched-dev`, `fpl-curated-dev`.

Rejected because: Multiplies infrastructure (4 buckets, 4 lifecycle configs, 4 IAM statements). Cross-bucket operations require broader S3 permissions.

**3. Single bucket with prefix-based layers and Hive partitioning (chosen)**
One `fpl-data-lake-dev` bucket with top-level prefixes defining data quality stages and Hive-style partition keys for discovery.

### Idempotency

**1. DynamoDB state table (rejected)**
Write a completion record on success, check before starting.

Rejected because: Adds a DynamoDB table that duplicates information already implicit in S3 — if the file exists, the work is done.

**2. S3 prefix existence check (chosen)**
Call `s3_client.list_objects(bucket, prefix)` before each operation. If files exist under the output prefix, skip. A `force=True` parameter overrides the check for backfills.

## Decision

### Layer structure

Single S3 bucket with four data layers plus a dead-letter queue:

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

### Why four layers (not three or five)
- **Raw** preserves source data for reprocessing without re-fetching APIs
- **Clean** ensures validated, type-cast inputs before enrichment — LLM inputs must be predictable
- **Enriched** is separate because LLM enrichment is expensive and may fail — clean data should be usable independently
- **Curated** holds dashboard-specific aggregations that join across sources — downstream consumers shouldn't repeat this joining logic
- A fifth "staging" layer was considered and rejected — clean serves this purpose

### Format choices
- **Raw**: JSON — preserve original API response exactly as received
- **Clean/Enriched/Curated**: Parquet with zstd compression — columnar, compact, schema-enforced, fast for analytics
- **DLQ**: JSONL — human-readable for debugging, one record per line

**Why Parquet with zstd (not Delta Lake, Iceberg, or CSV):**
- Delta Lake / Iceberg require a metastore (Glue Catalog) and add complexity. Our pipeline is append-only per gameweek with no concurrent writers — ACID is overkill.
- CSV has no schema enforcement, no compression, slow to read.
- zstd gives better compression ratios than snappy at comparable speed. PyArrow reads/writes Parquet natively, and Athena/DuckDB query it directly.

### Partitioning and idempotency
Hive-style keys (`season=`, `gameweek=`, `date=`) enable:
- Partition pruning in queries (Athena, DuckDB)
- Prefix-based idempotency — before each collect/transform/enrich step, check if output exists at the target prefix; if so, skip
- Lifecycle rules scoped by prefix (raw/ expires at 90 days, dlq/ at 30 days)

Each collector writes a **single JSON file per invocation**. S3 `PutObject` is atomic — the object either fully exists or doesn't. If the Lambda crashes before the write, nothing exists and retry correctly sees empty. If after, the file exists and retry correctly skips. The `force=True` parameter exists for backfills and manual re-processing.

### Lambda deployment
Services depend on PyArrow (~180 MB), pandas (~60 MB), numpy (~30 MB) — together exceeding the 250 MB Lambda zip limit. All Lambdas are deployed as container images via ECR with multi-stage Dockerfiles. Cold start is ~2-5s (vs ~1-2s for zip), acceptable for a batch pipeline that runs weekly.

## Consequences
**Easier:**
- One bucket to manage, one set of lifecycle rules, one IAM policy
- Hive partitioning is universally supported (Athena, Spark, DuckDB, pandas)
- Each layer has a clear contract: raw=JSON, clean/enriched/curated=Parquet
- Idempotency requires no additional infrastructure — S3 is the data store and source of truth
- Easy to add new data sources — just create a new prefix under raw/

**Harder:**
- No ACID transactions — mitigated by atomic S3 PUT and single-file-per-invocation pattern
- No schema registry — schema evolution managed manually via `schema_version` in Parquet metadata
- Single bucket means a compromised Lambda could read/write any layer (mitigated: IAM scoping by prefix is possible but not yet implemented)
- If output format changes to multiple files per invocation, the single-file atomicity assumption breaks
