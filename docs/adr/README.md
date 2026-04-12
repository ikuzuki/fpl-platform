# Architecture Decision Records

Decisions that shaped the FPL platform, from infrastructure through to the AI agent layer.

| ADR | Decision | Skill area |
|-----|----------|------------|
| [0001](0001-monorepo-architecture.md) | Monorepo over multi-repo | Software engineering |
| [0002](0002-s3-data-lake-design.md) | S3 data lake with prefix-based layers, Hive partitioning, Parquet+zstd | Data engineering |
| [0003](0003-direct-api-over-langchain.md) | Direct Anthropic SDK over LangChain for enrichment | AI engineering |
| [0004](0004-llm-cost-optimisation.md) | Tiered models, input filtering, and batching to control LLM spend | AI engineering, cost engineering |
| [0005](0005-prompt-versioning-and-llm-observability.md) | Git-based prompt versioning and Langfuse observability | AI engineering, MLOps |
| [0006](0006-parallel-pipeline-design.md) | Parallel Step Functions for collection and enrichment | Data engineering, distributed systems |
| [0007](0007-static-dashboard-architecture.md) | Static React SPA with pre-generated JSON on CloudFront | Software engineering, cloud architecture |
| [0008](0008-neon-pgvector-for-agent-retrieval.md) | Neon serverless Postgres + pgvector for agent retrieval | AI engineering, data engineering |
| [0009](0009-scout-report-agent-architecture.md) | 4-node LangGraph agent with tiered models and budget controls | AI engineering, system design |
