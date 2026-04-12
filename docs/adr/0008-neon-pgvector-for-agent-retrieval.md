# ADR-0008: Neon Serverless Postgres + pgvector for Agent Retrieval

## Status
Accepted

## Date
2026-04-12

## Context
The Phase 2 scout report agent needs to query player data in two ways: structured queries ("best defenders under £5.5m") and semantic queries ("find players with similar form to Palmer"). The Phase 1 pipeline writes curated data to S3 as Parquet and JSON. We needed to decide whether to query S3 directly, add a vector database, and if so, where to host it.

Semantic search matters because the agent can't always construct precise SQL filters from a natural language question. "Players similar to Palmer" requires understanding that Palmer's profile — mid-price, high xG, attacking midfielder, improving form — should match players with comparable characteristics, not just players who share a single stat threshold.

## Options Considered

### 1. Direct S3 queries only (rejected)
Read curated Parquet/JSON from S3 in the agent's tools. No new infrastructure.

Rejected because: S3 supports structured lookups (read a specific file by key) but not similarity search. The agent would need to load all 300+ players into memory and implement its own ranking logic per query — pushing complex reasoning into tool code rather than leveraging vector similarity. It also means every query reads the full dataset.

### 2. RDS Postgres with pgvector (rejected)
AWS-managed Postgres on `db.t3.micro` (free tier).

Rejected because: RDS free tier expires after 12 months — the project targets zero ongoing cost. After expiry, the smallest RDS instance costs ~$15/month for a database that handles ~500 rows and sporadic queries. The always-on compute model is a poor fit for a portfolio project with intermittent traffic.

### 3. Supabase (rejected)
Managed Postgres with pgvector, auth, storage, and realtime features. Free tier: 500MB.

Rejected because: Supabase is a backend-as-a-service platform bundling auth, storage, and realtime — features we don't need. It nudges toward their client SDK patterns rather than standard `asyncpg`. Choosing Supabase looks like picking a platform rather than making an architectural decision.

### 4. Neon serverless Postgres + pgvector (chosen)
Serverless Postgres that scales to zero when idle. Free tier: 0.5GB storage, 190 compute hours/month. pgvector extension available.

## Decision
Use Neon as the vector store for the scout report agent.

### How it fits the architecture

```
Weekly pipeline:
  CurateData Lambda → S3 (unchanged)
  SyncEmbeddings Lambda → reads S3 curated data → embeds with sentence-transformers → upserts to Neon

Agent request:
  LangGraph tools → Neon (structured queries + vector similarity)
```

The embedding model is `all-MiniLM-L6-v2` from sentence-transformers — runs locally on CPU, no API key needed, 384-dimension vectors. At ~500 players the full embedding job takes seconds and the quality difference between MiniLM and paid APIs (Voyage, OpenAI embeddings) is negligible at this scale.

### What gets embedded
Each player's enriched profile (stats + LLM summary + fixture outlook + form trend) is concatenated into a text block and embedded as a single 384-dim vector. The `player_embeddings` table stores the vector alongside structured columns (price, position, team, form) so the agent can combine vector similarity with SQL filters in a single query.

### Why Neon specifically
- **Scales to zero** — no compute cost when idle, which is most of the time for a portfolio project
- **Standard Postgres** — connects via `asyncpg` with a connection string, no proprietary SDK
- **pgvector built-in** — `CREATE EXTENSION vector` works out of the box
- **Free forever** — 0.5GB and 190 compute hours/month, well within this project's needs

### What Neon is NOT responsible for
- The dashboard still reads pre-generated JSON from S3/CloudFront (unchanged from ADR-0007)
- The enrichment pipeline still writes to S3 (unchanged)
- Neon is only used by the agent's tools — if Neon is down, the dashboard still works

## Consequences
**Easier:**
- Agent tools can do both structured queries (`WHERE position = 'MID' AND price < 7.0`) and semantic search (`ORDER BY embedding <=> query_vector`) in one database
- Scales to zero = no cost when no one is using the agent
- Standard Postgres means no new query language to learn
- Embedding sync runs once per gameweek (~5 seconds) — trivial compute

**Harder:**
- New external dependency outside AWS — connection string in Secrets Manager, network access from Lambda
- Cold starts on Neon free tier can add 1-2 seconds to first query after idle period
- Embedding model (`all-MiniLM-L6-v2`) adds ~90MB to the Lambda container image
- If Neon's free tier terms change, we'd need to migrate — but the data is small and reproducible from S3
