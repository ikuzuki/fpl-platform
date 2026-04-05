# System Architecture Overview

The FPL platform is a serverless data pipeline that collects Fantasy Premier League data, enriches it with LLM analysis, and serves dashboard-ready datasets. Everything runs on AWS, orchestrated by Step Functions, triggered weekly by EventBridge.

## Architecture Diagram

```mermaid
graph TB
    subgraph External["External Data Sources"]
        FPL["FPL API<br/><i>Players, fixtures, teams</i>"]
        US["Understat API<br/><i>xG, xA, npxG</i>"]
        NEWS["RSS Feeds<br/><i>BBC, Sky, Guardian</i>"]
    end

    subgraph Orchestration["Orchestration"]
        EB["EventBridge<br/><i>Tuesday 8am UTC</i>"]
        SF["Step Functions<br/><i>fpl-collection-pipeline</i>"]
    end

    subgraph Collection["Data Collection · Parallel"]
        L1["FPL Collector<br/><i>Lambda · 300s · 512MB</i>"]
        L2["Understat Collector<br/><i>Lambda · 300s · 512MB</i>"]
        L3["News Collector<br/><i>Lambda · 300s · 512MB</i>"]
    end

    subgraph Processing["Validation & Transformation"]
        L4["Validator<br/><i>Lambda · 300s · 512MB</i>"]
        L5["Transformer<br/><i>Lambda · 300s · 1024MB</i>"]
    end

    subgraph Enrichment["LLM Enrichment · Parallel"]
        L6["Player Summary<br/><i>Haiku · 5 RPM</i>"]
        L7["Injury Signal<br/><i>Haiku · 5 RPM</i>"]
        L8["Sentiment<br/><i>Haiku · 5 RPM</i>"]
        L9["Fixture Outlook<br/><i>Sonnet · 15 RPM</i>"]
        L10["Merge<br/><i>Lambda · 120s</i>"]
    end

    subgraph Curation["Curation"]
        L11["Curate Data<br/><i>Lambda · 120s · 512MB</i>"]
    end

    subgraph Storage["S3 Data Lake · fpl-data-lake-dev"]
        RAW["raw/<br/><i>JSON · 90d retention</i>"]
        CLEAN["clean/<br/><i>Parquet · zstd</i>"]
        ENRICHED["enriched/<br/><i>Parquet · zstd</i>"]
        CURATED["curated/<br/><i>Parquet · zstd</i>"]
        DLQ["dlq/<br/><i>JSONL · 30d retention</i>"]
    end

    subgraph Observability["Observability"]
        LF["Langfuse<br/><i>LLM traces, cost, quality</i>"]
        CW["CloudWatch<br/><i>Logs, metrics</i>"]
        SNS["SNS<br/><i>Pipeline alerts</i>"]
    end

    subgraph Consumers["Downstream Consumers"]
        DASH["Streamlit Dashboard"]
        AGENT["LangGraph Agent<br/><i>Transfer recommendations</i>"]
    end

    EB -->|"weekly cron"| SF
    SF --> Collection
    SF --> Processing
    SF --> Enrichment
    SF --> Curation

    FPL --> L1
    US --> L2
    NEWS --> L3

    L1 --> RAW
    L2 --> RAW
    L3 --> RAW

    RAW --> L4
    L4 -->|"invalid"| DLQ
    L4 --> L5
    L5 --> CLEAN

    CLEAN --> L6
    CLEAN --> L7
    CLEAN --> L8
    CLEAN --> L9
    L6 --> L10
    L7 --> L10
    L8 --> L10
    L9 --> L10
    L10 --> ENRICHED

    L6 -.->|"traces"| LF
    L7 -.->|"traces"| LF
    L8 -.->|"traces"| LF
    L9 -.->|"traces"| LF

    ENRICHED --> L11
    L11 --> CURATED

    CURATED --> DASH
    CURATED --> AGENT

    SF -.->|"failure"| SNS
    Collection -.-> CW
    Processing -.-> CW
    Enrichment -.-> CW
```

## Component Summary

| Layer | Components | Key Technology |
|-------|-----------|----------------|
| Orchestration | EventBridge, Step Functions | Weekly cron, parallel states, retry/catch |
| Collection | 3 Lambda collectors + gameweek resolver | httpx, feedparser, asyncio |
| Processing | Validator + Transformer | Great Expectations, PyArrow, pandas |
| Enrichment | 4 enricher Lambdas + merger | Anthropic SDK, asyncio.Semaphore, Langfuse |
| Curation | Curate Lambda (6 curators) | pandas, PyArrow |
| Storage | Single S3 bucket, 4 layers + DLQ | Hive partitioning, Parquet + zstd |
| Infrastructure | Terraform modules (Lambda, ECR, S3, Step Functions) | HCL, S3 backend |
| CI/CD | GitHub Actions (path-filtered) | dorny/paths-filter, ECR push |

## Key Design Decisions

- **Serverless-only** — no EC2, no ECS, no VPC. Lambda + Step Functions keeps costs near-zero when idle (pipeline runs once per week).
- **Single S3 bucket** with prefix-based layers rather than separate buckets per stage. See [ADR-0002](../adr/0002-s3-data-lake-design.md).
- **Container images** for all Lambdas (PyArrow + pandas exceed the 250MB zip limit). Multi-stage Dockerfiles, one ECR repo per service.
- **Direct Anthropic SDK** instead of LangChain — simpler dependency tree, full prompt control. See [ADR-0003](../adr/0003-direct-api-over-langchain.md).
- **Shared IAM role** across all Lambdas (acceptable at current scale; per-Lambda roles are the next step).
