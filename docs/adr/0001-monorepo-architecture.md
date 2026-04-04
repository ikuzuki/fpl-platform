# ADR-0001: Monorepo Architecture

## Status
Accepted

## Date
2026-04-04

## Context
The FPL platform consists of multiple services (data pipeline, LLM enrichment, recommendation agent, streaming, ETL) plus shared infrastructure, a shared Python library, and web frontends. We needed to decide how to organise the code.

This is a solo portfolio project designed to demonstrate end-to-end data + ML engineering. Hiring managers and reviewers will clone and explore it. The shared library (`fpl_lib`) changes frequently during early development as patterns stabilise.

## Options Considered

### 1. Monorepo (chosen)
Single `fpl-platform` repository with directory separation (`libs/`, `services/`, `infrastructure/`, `web/`). CI uses `dorny/paths-filter` to scope jobs to changed paths.

### 2. Multi-repo (rejected)
Separate repos per service (`fpl-data`, `fpl-enrich`, `fpl-agent`, `fpl-infra`, etc.) with `fpl-lib` published as a private PyPI package.

**Rejected because:**
- Publishing `fpl_lib` as a package adds friction during early development when the shared interface is still evolving — every change requires a version bump, publish, and pin update across consumers
- Reviewers would need to clone 6+ repos to understand the full system
- Cross-repo CI coordination (ensuring compatible versions) adds complexity with no team to justify it

### 3. Polyrepo with git submodules (rejected)
Multiple repos linked via submodules for the shared library.

**Rejected because:** Submodules are notoriously painful for solo development — easy to get into detached HEAD states, and they add git ceremony without solving the versioning problem.

## Decision
Use a single monorepo with clear directory separation. CI path filtering ensures only relevant jobs run on each change.

## Consequences
**Easier:**
- One clone to explore the full system — critical for a portfolio project reviewed by hiring managers
- Shared code (`libs/fpl_lib/`) is directly importable without publishing packages
- Unified commit history showing iterative progress across all components
- Single CI config, single project board, single set of branch protections
- `dorny/paths-filter` pattern is proven (used at Intech) and keeps CI fast despite monorepo scale

**Harder:**
- If this grew into a team project, the monorepo could become unwieldy without tooling (Nx, Turborepo)
- CI path filtering adds configuration complexity vs per-repo triggers
- All services share the same branch protection rules (can't have stricter rules for infra vs data)
