# Data Dictionary

This document describes all datasets in the FPL platform.

## Data Lake Layers

| Layer | Path | Format | Description |
|-------|------|--------|-------------|
| Raw | `raw/` | JSON | Unmodified API responses |
| Clean | `clean/` | Parquet | Validated and typed data |
| Enriched | `enriched/` | Parquet | LLM-enriched data |
| Curated | `curated/` | Parquet | Analytics-ready datasets |
| DLQ | `dlq/` | JSON | Failed processing records |

## Partitioning

All layers use Hive-style partitioning: `season={season}/gameweek={gw}/`

## Datasets

*To be populated as datasets are created in Phase 1.*
