# FPL Pulse

Fantasy Premier League analytics platform that collects weekly player data, enriches it with AI-generated insights, and serves transfer recommendations.

**[See it live](https://dxz2mzo798tf9.cloudfront.net/)** · Built with Python, Terraform, React, and Claude.

## Why this project exists

I built FPL Pulse to go beyond tutorial-level projects and demonstrate production thinking across the full stack — Terraform infrastructure, Python data pipelines, LLM enrichment, and a live React dashboard. It runs on a fully automated weekly pipeline with CI/CD, tests, and monitoring.

## Repo structure

```
fpl-platform/
├── infrastructure/             # Terraform IaC
│   ├── modules/                # 5 modules: S3, Lambda, ECR, Step Functions, CloudFront
│   └── environments/           # dev / prod tfvars
│
├── libs/fpl_lib/               # Shared Python library
│   ├── clients/                # S3, DynamoDB, API clients
│   ├── core/                   # RunHandler pattern, response models
│   ├── models/                 # Pydantic v2 domain models
│   ├── utils/                  # Helpers
│   └── validators/             # Data validation
│
├── services/
│   ├── data/                   # Collection Lambdas (FPL API, Understat, news)
│   ├── enrich/                 # LLM enrichment Lambdas (summaries, sentiment)
│   ├── curate/                 # Curator classes that synthesise enriched data into dashboard/agent-ready JSON
│   └── agent/                  # LangGraph transfer recommendation agent
│
├── web/
│   ├── dashboard/              # React 19 + TypeScript + Tailwind v4
│   └── portfolio/              # Static portfolio site
│
├── scripts/                    # Backfill and utility scripts
├── docs/adr/                   # Architecture Decision Records (7 ADRs)
└── .github/workflows/          # CI + deploy pipelines
```

## Getting started

**Prerequisites:** Python 3.11+, Node 20+, Terraform 1.5+, Make, Git.

```bash
# Clone
git clone https://github.com/ikuzuki/fpl-platform.git
cd fpl-platform

# Python — backend services and shared lib
python -m venv venv
source venv/Scripts/activate   # Windows Git Bash
make install                   # installs libs + services in editable mode

# Dashboard — React frontend
cd web/dashboard
npm install
npm run dev                    # http://localhost:5173
```

**Environment variables:** Copy `.env.example` to `.env` and fill in AWS credentials and API keys. Never commit `.env`.

## Development workflow

```bash
# Lint & type-check
make lint                      # ruff check + mypy

# Format
make format                    # ruff fix + ruff format

# Test
make test                      # all tests
make test-unit                 # unit tests only
make test-service SERVICE=data # single service

# Dashboard
cd web/dashboard
npm run lint                   # eslint
npm run test                   # vitest
npm run build                  # production build
```

**Branching:** `{type}/{short-description}` — e.g. `feat/fpl-api-collector`, `fix/s3-client-timeout`.

**Commits:** [Conventional Commits](https://www.conventionalcommits.org/) — `feat:`, `fix:`, `docs:`, `test:`, `chore:`, `refactor:`, `ci:`.

**PRs:** All changes go through pull requests. CI runs lint + tests on every push.

## For the full picture

The README gets you running. For the thinking behind the system:

- **[About Page](https://dxz2mzo798tf9.cloudfront.net/about)** — Architecture, design decisions, tech stack breakdown, and roadmap
- **[Architecture Decision Records](docs/adr/)** — The "why" behind key technical choices (monorepo structure, S3 data lake design, direct API over LangChain, LLM cost optimisation, and more)

## License

[MIT](LICENSE)
