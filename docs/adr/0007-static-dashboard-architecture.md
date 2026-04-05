# ADR-0007: Static Dashboard Architecture

## Status
Accepted

## Date
2026-04-05

## Context
The platform needs a web dashboard to visualise curated FPL data — player rankings, fixture difficulty, transfer recommendations, and team strength. The curated data updates once per week (Tuesday pipeline run). A future Phase 2 will add a LangGraph-powered transfer recommendation agent that requires real-time API interaction.

We needed an architecture that serves the dashboard cost-effectively and doesn't conflict with the eventual agent API.

## Options Considered

### 1. Streamlit dashboard (rejected)
Python-based, rapid prototyping, minimal frontend code.

Rejected because: Limited layout control, no component customisation, and slow rendering for larger datasets. I wanted a proper frontend I could extend with interactive features (filters, comparisons, eventually an agent chat UI) — Streamlit hits a wall quickly once you move beyond basic tables and charts.

### 2. React SPA with FastAPI backend (rejected for now)
React frontend calling a FastAPI service that reads curated Parquet from S3 via DuckDB.

Rejected because: The data updates weekly — a persistent API adds infrastructure cost and operational complexity (Lambda cold starts, or always-on ECS/EC2) for no functional benefit. Every dashboard request would query identical data. The API layer is justified when the LangGraph agent arrives in Phase 2, not before.

### 3. React SPA with pre-generated JSON on CloudFront (chosen)
Static React app and pre-computed JSON data files, both served from S3 behind CloudFront.

## Decision

### Architecture

```
Weekly pipeline:
  CurateData Lambda → writes Parquet (analytics) + JSON (dashboard) to S3

Serving:
  CloudFront distribution
    ├── /              → S3: static React app (Vite build output)
    └── /api/v1/*.json → S3: pre-generated JSON data files
```

The `CurateData` Lambda writes JSON alongside its existing Parquet outputs to a public-readable S3 prefix (`public/api/v1/`). The React app fetches these JSON files on load — no compute required at request time.

### Why this works for weekly data

The curated datasets (player dashboard, fixture ticker, transfer picks, team strength) change once per gameweek. Pre-generating JSON at pipeline time means:
- Zero compute cost per dashboard visit (CloudFront edge cache serves everything)
- No cold starts, no API latency, no DuckDB query time
- Total hosting cost ~$0.50/month (S3 storage + CloudFront requests)
- Data is always consistent — a single pipeline run produces all JSON atomically

### Frontend stack

React + TypeScript (Vite) with shadcn/ui and Tailwind — industry-standard stack with polished defaults and zero vendor lock-in (shadcn components are copied into the project, not installed as a dependency). Recharts for data visualisation, TanStack Table for sortable/filterable player tables.

### Coexistence with Phase 2 agent API

The static dashboard and the future agent API serve different purposes and coexist under one CloudFront distribution:

```
CloudFront
  ├── /dashboard/*  → S3 origin (static React app + JSON)
  └── /api/*        → API Gateway origin (FastAPI + Lambda for agent)
```

The dashboard pages (player rankings, fixtures, team comparison) are always static — they show the same curated data to every user. The agent endpoint is conversational and user-specific (takes a squad, returns personalised recommendations). Building the dashboard as static JSON now creates no migration burden when the agent arrives — we add an API Gateway origin to CloudFront and a new React page that calls it.

### JSON output format

The CurateData Lambda writes four JSON files per gameweek:

```
s3://fpl-data-lake-dev/public/api/v1/
  ├── player_dashboard.json
  ├── fixture_ticker.json
  ├── transfer_picks.json
  └── team_strength.json
```

Files are versioned by gameweek but the `latest` path always points to the most recent data. Total payload is ~250 KB — small enough to serve entirely from CloudFront edge cache.

## Consequences

**Easier:**
- Hosting is essentially free (S3 + CloudFront)
- No backend to monitor, scale, or debug for the dashboard
- React + shadcn/ui gives full control over layout and interaction design
- Dashboard and agent API are cleanly separated — can evolve independently
- JSON files are debuggable (curl them directly, inspect in browser)

**Harder:**
- Dashboard can't show real-time data (acceptable — FPL data is inherently weekly)
- Search or complex filtering must be client-side (acceptable at 300 rows)
- Adding user personalisation (e.g. "my team") requires the Phase 2 API — the static dashboard shows the same data to everyone
- Two output formats from CurateData (Parquet for analytics, JSON for dashboard) — minor duplication but keeps each consumer's format optimal
