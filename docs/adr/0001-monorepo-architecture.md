# ADR-0001: Monorepo Architecture

## Status
Accepted

## Context
The FPL platform consists of 4 projects (data pipeline, recommendation agent, historical processing, live streaming) plus shared infrastructure, a shared Python library, and web frontends. We needed to decide between a single monorepo or multiple separate repositories.

## Decision
Use a single `fpl-platform` monorepo with clear directory separation:
- `libs/` for shared Python code
- `services/` for each service (data, enrich, etl, agent, stream)
- `infrastructure/` for all Terraform
- `web/` for frontend applications
- `docs/` for documentation

CI uses `dorny/paths-filter` to only run jobs when relevant paths change.

## Consequences
**Easier:**
- One place to clone and explore — simpler for anyone reviewing the project
- Unified commit history showing iterative progress across all components
- Shared code (`libs/`) directly importable without publishing packages
- Single CI config, single project board, single set of branch protections
- No cross-repo version pinning or dependency management

**Harder:**
- If this grew into a team project, the monorepo could become unwieldy
- CI needs path filtering to avoid running all jobs on every change
- A completely unrelated project (different domain) would warrant its own repo
