# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Infra: `infrastructure/environments/prod/` Terraform stub.** Declares the prod root — backend config (`fpl-prod-tf-state` + `fpl-prod-tf-lock-table`), provider, tags, variables, and the foundational module calls (`data_lake` + `cost_reports`) — mirroring [`../dev/main.tf`](infrastructure/environments/dev/main.tf) with `environment = "prod"`. Not applied on any AWS account: the platform runs dev-only and standing up a second account is a provisioning task, not engineering work. The stub exists to prove that every module under `../../modules/` is environment-parameterised via `var.environment`, so the lift to a real prod deployment is mechanical (create state backend → copy dev's service-level .tf files → fill tfvars → `terraform plan`) rather than a refactor. Service-level .tf files (`agent.tf`, `lambda.tf`, `ecr.tf`, etc.) are deliberately not duplicated here — maintaining an unapplied second copy would drift silently. `README.md` in the new directory documents the status and lift-to-prod steps; `terraform.tfvars.example` kept as `.example` so a stray `terraform apply` errors on the missing variable rather than running with placeholder input.

### Changed
- **Docs: `CLAUDE.md` no longer promises an E2E pipeline test** (`tests/integration/test_pipeline_e2e.py`). The file was referenced in both the Build & Test Commands list and the Testing section but never actually written; contract tests in `tests/contracts/` cover cross-stage schema compatibility, and each service has integration tests against moto S3 for its own stage. Promising a file that doesn't exist is worse than acknowledging the gap — the section is trimmed to reflect what is actually shipped.

### Changed
- **Infra: agent Lambda memory bumped from 1024 MB to 3008 MB** in `infrastructure/environments/dev/lambda.tf`. CloudWatch on the already-deployed `#128` image showed cold-start at ~27 seconds — Lambda's 10 s init cap tripped, the container was force-restarted, and LWA's `/health` probe only went green ~28 s in. That's outside CloudFront's 30 s origin-response window, so browser-side cold hits presented as `FPL is unreachable` on `/team` and `Stream ended before a final report` on `/chat`. The 27 s was dominated by Python imports (LangGraph + pgvector + asyncpg + langfuse + anthropic + FastAPI) on a 1024 MB Lambda's ~0.57 vCPU; Lambda scales CPU linearly with memory, so 3008 MB (~1.7 vCPU) cuts that roughly threefold into the 8–12 s range. Max observed memory usage stays under 300 MB — the knob is bought for CPU, not RAM.

### Fixed
- **Infra: agent Lambda Function URL temporarily reverted from AWS_IAM + CloudFront OAC back to `AuthType = NONE` + `principal = "*"`** in `infrastructure/environments/dev/agent.tf`. Every CloudFront→Function URL origin request was getting rejected at the SigV4 layer (`Url4xxCount = UrlRequestCount` on the Lambda metrics; 100% 4xx; Lambda never invoked), and CloudFront's `custom_error_response` for 403 masked that with the SPA `/index.html` fallback — so the dashboard saw HTML instead of JSON/SSE and surfaced "FPL is unreachable" / "Stream ended before a final report". Investigation showed OAC config, attached-origin ID, resource-policy SourceArn, and the `lambda:FunctionUrlAuthType` condition key all matching live state, yet every request was still rejected. Suspected stuck OAC signing identity or an interaction between the `RESPONSE_STREAM` invoke mode and OAC that needs more time to pin down. This revert restores the state between #123 and #125 (Function URL publicly reachable, resource policy allows `principal = "*"`) to unblock the dashboard; re-hardening remains tracked in `docs/architecture/security-architecture.md`.
- **Agent: cold-start now defers the first Neon connection** via `NeonClient(min_size=0, ...)` in `services/agent/src/fpl_agent/api.py` so `asyncpg.create_pool` builds the pool struct without opening a socket. Follow-up to the Secrets Manager resolution fix (#126): that change correctly populated `NEON_DATABASE_URL` for the first time, which in turn made `lifespan` actually hit Neon — and Neon's scale-to-zero serverless compute takes 5–10s to wake, which blew past Lambda's 10s init phase. Symptom: `INIT_REPORT ... Status: timeout` in CloudWatch, LWA `/health` probe never going green, every Function URL request returning 502 "app is not ready". With `min_size=0` lifespan completes in milliseconds; the first `/chat` or `/team` request acquires the connection on demand, `init=register_vector` still runs on that first connection, and warm invocations inherit the open pool. Trade-off: the first user request after a cold start is ~5s slower, which is the right place to pay that cost (health probes stay green, budget/rate-limit deps still work).
- **Agent: cold-start left Anthropic + Neon credentials unresolved** because only `init_langfuse` had a Secrets Manager fetch — Anthropic and Neon didn't, so `ANTHROPIC_API_KEY` and `NEON_DATABASE_URL` were never populated from the secrets the Lambda had access to. Symptom in the dashboard: `/team` 502 with zero log streams on `fpl-dev-team-fetcher` (the boto3 invoke fires from a graph that never started), and `/chat` ending without a terminal SSE event because `get_graph` kept returning 503 from a `None` graph. Fixed by introducing a shared resolver (see the "Added" entry below) and calling it for both secrets at the top of the agent's `lifespan`, before `AsyncAnthropic()` and the Neon pool connect. Anthropic is treated as required (exception propagates so cold-start dies loudly); Neon is tolerated (fetch wrapped in try/except so the health endpoint boots even without Postgres — `/chat` and `/team` then return 503).
- **Infra: agent Lambda env var renamed `USAGE_TABLE_NAME` → `AGENT_USAGE_TABLE`** in `infrastructure/environments/dev/lambda.tf` so it matches what `api.py:62` reads. Previously the env var was dead code — the DynamoDB table name happened to resolve via the `f"fpl-agent-usage-{ENVIRONMENT}"` fallback, so dev worked by accident, but a future environment with a non-default table name would have silently written usage to a nonexistent table.
- **Agent: `ENVIRONMENT` module-level constant now reads the `ENV` env var** instead of `ENVIRONMENT`, matching the repo-wide Terraform convention (every other Lambda's `environment_variables` block sets `ENV = var.environment`). Before this, the agent's `"dev"` default happened to match the actual deployed env so nothing broke visibly, but `prod` would have silently initialised Langfuse/budget tables with the wrong suffix.

### Added
- **Shared `fpl_lib.secrets.resolve_secret_to_env`** — one helper, one convention (`{prefix}/{env}/{name}`), used by every service that needs to populate an env var from Secrets Manager at cold-start. Replaces the bespoke Secrets Manager block previously inlined in `init_langfuse` and the stopgap ARN-based wrapper that briefly lived in the agent's `api.py`. Propagates exceptions — callers decide whether a missing secret is fatal (Anthropic) or tolerable (Neon on a health-only boot, Langfuse when tracing is optional). Four unit tests cover the conventional-path fetch, the already-set short-circuit, the propagation semantics, and the custom prefix/region overrides.

### Changed
- **Infra: removed `NEON_SECRET_ARN`, `ANTHROPIC_SECRET_ARN`, `LANGFUSE_PUBLIC_KEY_SECRET_ARN`, `LANGFUSE_SECRET_KEY_SECRET_ARN` from the agent Lambda's `environment_variables`** in `infrastructure/environments/dev/lambda.tf`. With the path-based resolver convention (`/fpl-platform/{env}/<name>`) the code derives every SecretId from `ENV` alone, and the `lambda_role` IAM policy already scopes `GetSecretValue` to that prefix — adding a new secret is now a pure Terraform + resolver-call change, no per-Lambda env-var wiring.
- **`fpl_lib.observability.init_langfuse` delegates its Secrets Manager fetches to `resolve_secret_to_env`** instead of hand-rolling the boto3 call. Same public behaviour (idempotent, returns `False` on AWS failure, never raises), just one convention and one implementation for every secret on the platform.
- **Infra: agent Lambda Function URL was returning 403 to every request** because the function had no resource-based policy granting `lambda:InvokeFunctionUrl`. Function URLs gate invokes by *both* the URL's `authorization_type` and the function's resource policy AND'd together — `authorization_type = "NONE"` only skips the SigV4 signature check, it does not grant principals the right to invoke. Symptom in the dashboard: CloudFront masked the 403 with the SPA `/index.html` fallback (HTTP 200), so the React client received HTML instead of JSON and `response.json()` threw `SyntaxError: Unexpected token '<'`. Added `aws_lambda_permission.agent_function_url_public` with `principal = "*"` and `function_url_auth_type = "NONE"` so the URL is reachable. The eventual hardening (CloudFront OAC + `AWS_IAM`) remains as documented in `docs/architecture/security-architecture.md`.

### Changed
- **Infra: agent Lambda Function URL hardened to CloudFront-only access (#123).** `authorization_type` flipped from `NONE` to `AWS_IAM`, and the `principal = "*"` resource policy (the immediate-fix from the earlier 403 incident) replaced with a permission scoped to `principal = "cloudfront.amazonaws.com"` + `aws:SourceArn = <distribution ARN>`. Pairs with a new `aws_cloudfront_origin_access_control.agent` (`origin_access_control_origin_type = "lambda"`, `signing_behavior = "always"`) attached to the `agent_api` origin, so CloudFront SigV4-signs every origin request and the Function URL rejects anything else. Net effect: `curl https://<host>.lambda-url.eu-west-2.on.aws/` now returns 403 "signature missing"; the only path to the agent is through the CloudFront distribution, which means any future edge defence (WAF, geo-block, rate-based rule, edge logging) is unbypassable. Function URL RESPONSE_STREAM mode is preserved — OAC signs the origin request only and does not interfere with streaming the response back. Required a new `cloudfront_distribution_arn` output on the web-hosting module; the agent permission reaches into the module for it. Docs updated: `docs/architecture/security-architecture.md` now describes the hardened posture as current state (OAC row removed from the deferred table), `docs/architecture/frontend-backend-wiring.md` + the companion Drawio replace the old "⚠ auth gotcha" with the two-gate model explanation, stale "API Gateway" comments left over from ADR-0010 cleaned up in `infrastructure/modules/web-hosting/main.tf`.
- **Infra: agent Lambda `reserved_concurrent_executions = 10` restored** in `infrastructure/environments/dev/lambda.tf` now that the `fpl-dev` account-wide Lambda concurrency quota has been raised from the new-account default of 10 to the AWS standard of 1000. Re-establishes the infrastructure-level cap on concurrent invocations (Lambda returns 429 before executing the function past 10 in-flight requests), restoring the full layered defence described in `docs/architecture/security-architecture.md`. Architecture docs updated to remove the "temporarily disabled" notes.

### Added
- **Docs: `docs/architecture/frontend-backend-wiring.md` + companion `.drawio` diagram** — end-to-end walkthrough of the dashboard ↔ agent path: the relative-URL pattern that makes the same React bundle work in Vite dev (proxy) and prod (same-origin CloudFront), CloudFront's three origins with the agent behaviour's non-negotiable settings (`compress=false`, `CachingDisabled`, `AllViewerExceptHostHeader`, viewer-request path-rewrite function), Lambda Function URL + LWA + uvicorn + FastAPI dependency chain, SSE-over-POST (why `EventSource` is out, what hand-parsing `ReadableStream` buys), and the layered auth story (`X-Session-Id` UUID, per-session rate limiter, DynamoDB budget cap, CORS-only-in-dev). Mermaid diagram in the doc; layered Drawio with stage bands + legend alongside. Cross-linked from ADR-0007, ADR-0010, and `agent-architecture.md` so the "why" lives in the ADRs and the doc stays focused on the wiring.
- **Dashboard: chat panel polish from manual review** — empty-state copy now explains Scout's scope (data inputs + question types) so first-time visitors don't have to guess what's in-scope; "New chat" button (clears the conversation + cancels in-flight stream); Retry button on error bubbles re-dispatches the last user message; live character counter on the 500-char input that turns red at 90%; `aria-busy`/`aria-live` on the messages container so screen readers announce streaming state; explicit "Cancel this run" tooltip on the Stop button. Step pills get hover descriptions explaining what the agent is actually doing at each stage. Player fixture-outlook badges now carry a ✓/⚠/✗ glyph alongside the green/amber/red colour so the signal survives colourblindness or a monochrome screenshot.
- **Dashboard: `/chat` Scout Agent page** — full-page chat surface that streams agent SSE events (`step` → `result`/`error`), renders the `ScoutReport` as a structured card with player mini-cards, comparison block, recommendation, caveats, and data sources. Uses `useReducer` over a discriminated-union `ChatAction` (pure, fully unit-tested) and an `AbortController` so navigation away mid-stream tears down the fetch cleanly. Suggested questions tier by squad state — three general prompts in the empty state, three squad-aware prompts once a team is loaded.
- **Dashboard: optional team-ID flow** — `TeamIdInput` posts to `GET /api/agent/team`, persists the ID in `localStorage["fpl.teamId"]`, and renders the enriched `UserSquad` via `SquadCard` (XI grouped by position, captain/vice badges, bench row, bank + total value). Loaded squad is echoed onto every `POST /chat` so the recommender can personalise advice. The chat input is always live — squad is optional, not gating.
- **Dashboard: `Ask Scout` global header CTA + slide-out drawer** — promoted out of the regular nav into an accent-tinted button next to the dark-mode toggle (visible from every page) and a floating `Sparkles` FAB that opens a 420px right-side drawer hosting the same `ChatPanel` in compact mode. Drawer skips squad rendering and links back to `/chat` for the full layout. FAB hides itself on `/chat` to avoid covering the page's own send button. ESC closes; focus returns to the FAB on close.
- **Dashboard: Scout API client** — `src/lib/agentApi.ts` with `streamChat()` (async generator over `fetch` + `ReadableStream`, hand-parses SSE frames since `EventSource` only does GET), `chatSync()`, and `fetchTeam()`. All calls attach `X-Session-Id` from `getSessionId()` (`localStorage["fpl.sessionId"]` + `crypto.randomUUID()`), and surface `AgentApiError` with status + `Retry-After` for 429 handling.
- **Dashboard: agent type definitions** — `UserSquad`, `SquadPick`, `ScoutReport`, `PlayerAnalysis`, `ComparisonResult`, `AgentResponse`, `AgentEvent` (discriminated union), `ChatRequest` mirror the backend Pydantic models in `services/agent/src/fpl_agent/models/responses.py`.
- **Dashboard: Vite dev proxy** — `vite.config.ts` reads `VITE_AGENT_PROXY_TARGET` from `.env.development.local` and proxies `/api/agent/*` so the same code path (`fetch("/api/agent/chat")`) works in dev (proxied to CloudFront) and prod (same-origin via CloudFront fronting both surfaces). Example file at `web/dashboard/.env.example`.
- **Dashboard: test infra hardening** — `src/test/setup.ts` installs an in-memory `localStorage` shim and a `crypto.randomUUID` fallback because vitest 4 + jsdom 29 don't reliably expose either; clears storage between tests.

- **Agent: `GET /team` endpoint** that fetches a user's FPL squad and returns it pre-enriched. Two-step under the hood — invoke the team-fetcher Lambda (raw FPL passthrough), then join against Neon `player_embeddings` for `web_name` / `team_name` / `price` so consumers don't need a separate name-resolution step. Returns `UserSquad` with money fields converted from FPL's tenths-of-millions wire format to whole pounds. Errors map to: 404 for unknown team_id, 502 for upstream failure (Lambda/FPL/Neon), 503 if `TEAM_FETCHER_FUNCTION_NAME` is unset. Wrapped with `@observe(name="get_team")` so squad-load failures land next to chat traces in the same Langfuse timeline.
- **Agent: `UserSquad` + `SquadPick` Pydantic response models** (`models/responses.py`). Enriched shape with names + team + price; money in `float` £m, not the FPL API's tenths-of-millions integers. Conversion happens once at the loader boundary so both the agent's recommender and the dashboard read natural units.
- **Agent: `squad` field on `ChatRequest`** so the dashboard can echo a pre-loaded squad on every chat turn — the agent reads it from `state["user_squad"]` instead of re-fetching. `ChatRequest` now rejects the legacy `team_id` and `session_id` body fields with 422 (`extra="forbid"`); session identity is the `X-Session-Id` header (canonical since PR #93).
- **Agent: `user_squad` field on `AgentState`** with `initial_state(question, squad=None)` accepting an optional squad. Lives on its own typed field rather than inside `gathered_data` so the `tool_success_rate` quality score isn't inflated by a guaranteed-success seeded entry.
- Agent: `squad_loader.load_user_squad()` in `services/agent/src/fpl_agent/squad_loader.py` — single async entry point that handles the Lambda invoke + Neon enrichment, raising `SquadNotFoundError` / `SquadFetchError` for the route layer to map onto HTTP. boto3 wrapped via `asyncio.to_thread` to keep the event loop responsive during the 1–2s FPL round-trip.
- Agent: planner prompt now contains a `{user_squad_block}` slot — one-line summary when loaded (`captain={name}, bank=£X.Ym, value=£Z.Wm`), or "no squad provided" when absent.
- Agent: recommender prompt now also receives the squad as a `{user_squad_block}` (full JSON dump). Previously the recommender never saw `state["user_squad"]` so personalised "my team" answers couldn't quote actual picks.
- Agent: chat trace metadata now includes `team_id` + `gameweek` when a squad is present on the request, so Langfuse can filter by team for "why did the agent recommend X for team 12345" debugging.
- Infra: `lambda_team_fetcher` module instantiation in `infrastructure/environments/dev/lambda.tf` (256MB / 30s, runs `fpl_data.handlers.team_fetcher.lambda_handler` from the data ECR image). The Lambda existed in source since PR #115 but was never wired into Terraform — both the legacy `fetch_user_squad` tool (now removed) and the new `/team` endpoint depended on it.
- Infra: scoped IAM grant `fpl-{env}-agent-invoke-team-fetcher` so the agent role can `lambda:InvokeFunction` on the team-fetcher ARN. Scoped to the one function rather than `*` so future invokeable Lambdas have to be granted explicitly. Used by `squad_loader.py` from the API handler — the agent graph itself has no Lambda-invoking code path.

### Removed
- **Scaffold cleanup: `services/etl/` and `services/stream/` removed.** `services/etl/` was empty dbt scaffolding (`dbt_project.yml` + `.gitkeep` stubs) from an earlier plan; transformation is handled by `services/curate/` (Python curator classes writing JSON) and by DuckDB/pandas inside enrichment — dbt's compile/test/orchestration overhead wasn't justified for ~700 players × 38 gameweeks. `services/stream/` was a Kafka producer/processor stub (`docker-compose.yml` + 1–2 line modules) for a streaming demo; an FPL platform is inherently batch (gameweeks are weekly), so the streaming pattern didn't fit the workload. `CLAUDE.md` Repository Structure + Build Order and `README.md` repo-structure tree updated to match the actual service set (`data`, `enrich`, `curate`, `agent`).
- **Agent: `fetch_user_squad` tool removed from the planner's tool registry.** Squad loading is now strictly an HTTP-layer concern (dashboard → `GET /team` → echoed on every `POST /chat` → seeded onto `state["user_squad"]`). Letting the LLM dispatch a cross-service Lambda invoke at planning time would have required it to invent a `team_id` it has no source of truth for, and the planner-gating + executor short-circuit added in this PR's first cut were the smell that confirmed this should not be a tool. `ToolName` literal goes from 6 entries to 5; `make_tools` returns 5 keys; the executor short-circuit is gone; the dead `boto3`/`json`/`os` imports come out of `player_tools.py`. ADR-0009, agent-architecture.md, and the langgraph walkthrough are updated to match.
- **lib: `fpl_lib.observability` — shared Langfuse wiring module.** Consolidates the three pieces every LLM-using service needs: `init_langfuse()` (Secrets Manager → env vars, graceful on failure), `record_llm_usage()` (pushes model + tokens to the current generation span so Langfuse computes cost), and `flush()` (drains events before Lambda freeze). Re-exports `Langfuse`, `observe`, and `propagate_attributes` so service code imports from one surface. Replaces three near-identical `_init_langfuse` local functions across enrich + curate handlers.
- Agent: Langfuse runtime observability wired up end-to-end. `init_langfuse()` runs in `lifespan()` at cold-start; `POST /chat` and `POST /chat/sync` wrap the graph invocation with `@observe(name="agent_chat_request")` + `propagate_attributes(session_id, user_id, tags, metadata)` so every request becomes one root trace grouped by `X-Session-Id`. Three request-level quality scores are attached to each trace: `output_valid` (1.0 iff a `ScoutReport` was produced without `state["error"]`), `iterations_used` (raw count), and `tool_success_rate` (fraction of `gathered_data` entries without an `error` key). `langfuse_flush()` runs before every response — for SSE this is inside the generator's final block so client disconnects still upload accumulated spans.
- Agent: `@observe(as_type="generation")` on all three LLM-calling nodes (`planner`, `reflector`, `recommender`) and `@observe(as_type="tool")` on all six player tools. Generation spans now carry model + `usage_details` via `record_llm_usage`, so the Langfuse UI surfaces latency and cost per node / per tool.
- ADR-0009: documented the "no user-controlled URLs in agent tools" constraint. Every current tool is a Neon query or internal Lambda invoke, so there's no SSRF surface today; the note pins a guardrail for any future URL-fetching tool (IP blocklist + resolve-then-connect + domain allowlist) to close the SSRF-to-IMDS pivot (`169.254.169.254` credential exfiltration).
- **ADR-0010 — Agent HTTP Transport: Lambda Function URL with Response Streaming.** Documents the migration from API Gateway v2 HTTP API to Lambda Function URL + AWS Lambda Web Adapter. Captures the 29s / response-buffering rationale, the four alternatives considered, and the security-posture consequences (loss of API Gateway throttling, layered replacement).
- **`docs/architecture/security-architecture.md`** — new document describing the threat model (primary risk: cost runaway on the public agent endpoint), layered defences (Shield Standard → CloudFront → Lambda reserved concurrency → in-app RateLimiter → BudgetTracker → graph iteration cap), secrets + IAM posture, and explicit non-goals (WAF / authentication / VPC isolation) with triggers for adoption.
- Agent: FastAPI endpoints for the scout agent — `POST /chat` (SSE stream of intermediate `step` events + final `result`), `POST /chat/sync` (blocking JSON fallback), and `GET /budget` (current-month spend snapshot). Replaces the Wave 2 health-only stub.
- Agent: `BudgetTracker` (middleware/budget.py) — DynamoDB-backed monthly spend tracker with "never overspend" policy. Checks before every chat request, blocks with 429 when the cap (`AGENT_MONTHLY_BUDGET_USD`, default $5) is reached, and records per-call token usage + USD cost to `fpl-agent-usage-{env}` atomically. Lazy-creates the month row on first touch so new calendar months work without a deploy.
- Agent: `RateLimiter` (middleware/rate_limit.py) — in-memory sliding-window per-session limiter (5 req/min, 20 req/hour). Keyed by `X-Session-Id` header with client-IP fallback. Returns 429 + `Retry-After`. Note: per-container state, so effective limit scales with warm Lambda count; good enough for dev/demo, Redis or a CloudFront WAF rate-based rule needed for true distributed limits. See `docs/architecture/security-architecture.md` for the layered security posture and upgrade triggers.
- Agent: `ChatRequest` Pydantic model (`models/requests.py`) — validates `question` (1–500 chars) and optional `session_id`, with `extra="forbid"` so body typos surface as 422 rather than silently ignoring.
- Agent: `llm_usage` reducer field on `AgentState` (`Annotated[list, operator.add]`). LLM nodes now attach their own usage record (`{node, model, input_tokens, output_tokens}`) to state on every call, which the API handler tallies via `BudgetTracker.record_batch` after the graph completes — decouples cost tracking from log scraping.
- Agent: `sse-starlette` dependency for `EventSourceResponse`.

### Changed
- **Agent transport migrated from API Gateway v2 HTTP API to Lambda Function URL + AWS Lambda Web Adapter (LWA).** Per ADR-0010. Unlocks real SSE streaming (API Gateway v2 buffers responses) and replaces the 29s integration-timeout cliff with the 60s Lambda budget. Dockerfile now copies the LWA extension from `public.ecr.aws/awsguru/aws-lambda-adapter:0.9.0` and runs `uvicorn fpl_agent.api:app` as CMD; the `api_handler.py` Mangum shim is removed. Terraform: `module "api_gateway"` in `agent.tf` replaced with `aws_lambda_function_url` (`invoke_mode = RESPONSE_STREAM`, `authorization_type = NONE` because CloudFront fronts everything). Lambda module gains `reserved_concurrent_executions` variable; agent sets it to `10` as hardware-level backpressure replacing API Gateway's 10rps/20-burst throttling.
- **CloudFront `/api/agent/*` behaviour: `compress = false`.** Compression requires knowing the full response length and therefore buffers — which would silently defeat SSE on the way back to the browser. Combined with the existing `CachingDisabled` cache policy and `AllViewerExceptHostHeader` origin-request policy, this lets Function URL RESPONSE_STREAM chunks pass through to the client unbuffered.
- Agent: CORS moved from API Gateway config into `fastapi.middleware.cors.CORSMiddleware`. Origins from `AGENT_CORS_EXTRA_ORIGINS` env var (comma-separated) in addition to `localhost:5173` for Vite dev.
- Agent: `_log_usage` renamed to `_record_usage` and now returns a dict suitable for the `llm_usage` state field in addition to logging. Model name is also logged per call for cost attribution.
- **Enrich: every LLM enricher now uses Anthropic tool-use for structured output instead of text + JSON parsing.** `FPLEnricher._call_llm` builds a fake `record_enrichments` tool whose `input_schema` is derived from each subclass's `OUTPUT_MODEL` (Pydantic) and forces `tool_choice` so Anthropic's decoder constrains sampling to the schema. Eliminates the markdown-fence stripping, `json.JSONDecodeError` branch, and prompt-level "return a JSON array" instruction. `minItems`/`maxItems` on the schema pin the output count to the batch size, so per-item count mismatch can't silently drift. Pydantic `_validate_output` is retained as a belt-and-braces semantic check (catches constraints Anthropic's decoder can't enforce, e.g. cross-field rules).
- Enrich: all four output Pydantic models (`PlayerSummaryOutput`, `InjurySignalOutput`, `SentimentOutput`, `FixtureOutlookOutput`) now set `extra="forbid"`, emitting `additionalProperties: false` in the wire schema so unknown fields are rejected at sampling time.
- **lib: `NeonClient` now wraps `asyncpg.create_pool` instead of a single `Connection`.** asyncpg forbids concurrent queries on one connection; the agent's tool executor runs queries in parallel via `asyncio.gather`, so shared-connection usage would have raised `InterfaceError` in production. Each `fetch`/`fetch_one`/`execute` now acquires a connection from the pool. Connection setup (e.g. `pgvector.asyncpg.register_vector`) is passed via a new `init` parameter so it runs on every pooled connection.
- Agent: `tool_executor` keys `gathered_data` entries by `f"{name}({arg1=val,arg2=val})"` instead of bare tool name — `[query_player(Salah), query_player(Palmer)]` in one plan now produces two distinct entries. Fixes comparison questions (a first-class ADR-0009 use case) that previously saw only the last tool call's result.
- Agent: `planner_node` now clears `plan` and `tool_calls_made` on error, preventing the tool executor from re-running the previous iteration's plan.
- Agent: `recommender_node` short-circuits when `state["error"]` is set and returns a minimal error `ScoutReport` without calling Sonnet — saves cost + avoids feeding broken data into the most expensive LLM call in the graph.
- Agent: All response models now set `extra="forbid"`, emitting `additionalProperties: false` in the tool-use `input_schema`. Anthropic's decoder rejects unknown fields at sampling time rather than letting them through to Pydantic.
- Agent: `_log_usage` now also records `stop_reason` and warns when it's `"max_tokens"` (signals output truncation — useful for debugging phantom Pydantic failures).
- Enrich: `FPLEnricher._call_llm` is now `@observe(as_type="generation")` and calls `record_llm_usage()` after the Anthropic response. Previously the span was a generic span and tokens were only logged to CloudWatch — Langfuse UI had no cost/latency view for any enrich trace. The per-service `COST_RATES` tables stay as the source of truth for the S3 cost report; Langfuse now has a parallel signal computed from its published rate table.
- Enrich + Curate: handlers import `init_langfuse` / `propagate_attributes` / `flush` from `fpl_lib.observability` instead of declaring local `_init_langfuse` helpers. Behaviour-preserving refactor; removes three duplicate implementations.

### Fixed
- Agent: Prompt `.md` files now ship with the Lambda wheel. `pyproject.toml` declares `[tool.setuptools.package-data]` so setuptools includes them, and `_load_prompt` uses `importlib.resources.files` for path-independent loading (editable install, wheel install, and source tree all work).
- Agent: Removed dead `user_squad` state field. Squad data from `fetch_user_squad` lives in `gathered_data` like every other tool result; previously the recommender prompt always received `null` while the real squad sat un-rendered in gathered_data.

### Added
- Agent: 4-node LangGraph state machine (`planner` → `tool_executor` → `reflector` → `recommender`) with a conditional loop capped at 3 iterations — replaces the Wave 2 stub handler for /chat
- Agent: `AgentState` TypedDict with per-field reducers (`operator.add` for `tool_calls_made`, `merge_dicts` for `gathered_data`); Pydantic response models `ScoutReport`, `PlayerAnalysis`, `ComparisonResult`, `ReflectionResult`, `AgentResponse`
- Agent: Six async tools over Neon pgvector (`query_player`, `search_similar_players`, `query_players_by_criteria`, `get_fixture_outlook`, `get_injury_signals`) plus `fetch_user_squad` via boto3 invoke of the team-fetcher Lambda
- Agent: Versioned prompt templates under `services/agent/src/fpl_agent/graph/prompts/v1/` (planner, reflector, recommender)
- Agent: Anthropic tool-use for structured output at every LLM node — schemas derive from Pydantic so malformed JSON can't reach the parser
- Agent: Langfuse `@observe()` decorators on all nodes and tools (runtime client init lands in #93)
- Infra: `modules/api-gateway/` — HTTP API v2 with Lambda proxy integration, CORS, throttling (10 req/s, 20 burst), CloudWatch access logs
- Infra: Agent Lambda (`fpl-agent-dev`) wired to agent ECR image and shared Lambda role (1024 MB, 60s timeout)
- Infra: DynamoDB table `fpl-agent-usage-dev` for monthly token/cost tracking and budget kill-switch
- Infra: Neon database URL Secrets Manager shell (`/fpl-platform/dev/neon-database-url`) — populated manually post-apply
- Infra: CloudFront `/api/agent/*` behaviour routing to API Gateway (CachingDisabled, AllViewerExceptHostHeader) — gated on `agent_api_domain` input
- Agent: Stub `api_handler` returning 200 on `/health` and 501 elsewhere — lets Wave 2 provision infra end-to-end ahead of Wave 3 agent logic
- ADR README (`docs/adr/README.md`) — skill area mapping table for portfolio readers

### Changed
- Infra: Lambda module now sets `lifecycle.ignore_changes = [image_uri]` — hands image tag ownership to CI (which pushes commit-SHA tags via `aws lambda update-function-code`). Prevents Terraform from resetting all Lambdas to `:latest` on every apply.

### Fixed
- Infra: CloudFront Function strips `/api/agent` prefix before forwarding to API Gateway — without this, the agent route returned the dashboard SPA HTML via the 404 fallback (API Gateway has no `/api/agent/*` routes, only `/chat` and `/health`).
- Data: `FPLAPICollector.collect_bootstrap` and `collect_fixtures` no longer skip when prior output exists under the S3 prefix. Their source data (prices, player status, news, kickoff times, per-match stats) changes throughout the season, so every weekly pipeline run now writes a fresh timestamped snapshot. Downstream consumers already pick the latest via `sorted(list_objects(prefix))[-1]`. Gameweek-live and player-history keep their skip (both are frozen once captured).
- Web: Briefing and Captain Picker pages now label themselves with the *upcoming* gameweek instead of the finished gameweek the underlying data was collected from. Curator writes a new `advice_gameweek` field (`gameweek + 1`, capped at 38) into `gameweek_briefing.json` and each `player_dashboard.json` row; the UI prefers that field and falls back to `gameweek + 1` when reading older JSON. Processed-GW stays in the `gameweek` field for Parquet analytics.

### Changed
- ADR-0003: Expanded LiteLLM rejection with proxy latency concern and when-to-revisit criteria
- ADR-0004: Moved rate limiting section to ADR-0006 (keeps cost ADR focused on cost)
- ADR-0005: Replaced inline code blocks with file references to actual implementations; condensed SDK version note
- ADR-0006: Absorbed rate limiting table and rationale from ADR-0004; condensed collection parallelism section
- ADR-0007: Trimmed SSR rejection; added justification for React over Astro/plain HTML

### Added
- Data: `TeamFetcher` class for fetching FPL manager squads with Chrome TLS impersonation (curl_cffi)
- Data: Lambda handler for team fetching, invokable by the agent service via boto3
- Data: Custom exceptions `TeamNotFoundError` and `FPLAccessError` for FPL API error handling
- Agent: `NeonClient` async Postgres wrapper in shared lib (`fpl_lib.clients.neon`) for Neon pgvector operations
- Agent: `PlayerEmbedder` class using sentence-transformers all-MiniLM-L6-v2 for 384-dim player profile embeddings
- Agent: `sync_embeddings` function to read curated S3 data, generate embeddings, and upsert into Neon pgvector
- Agent: Lambda handler (`sync_handler`) for triggering embedding sync via Step Functions
- Agent: `player_embeddings` schema with IVFFlat vector index and structured filtering indexes

### Changed
- Data: Extract shared `fpl_fetch` function into `collectors/http.py` — single FPL API fetch implementation with Cloudflare bypass used by all collectors
- Data: Refactor `FPLAPICollector`, `GameweekResolver`, and `TeamFetcher` to use shared `fpl_fetch` instead of duplicated retry logic

### Changed
- Infra: Split monolithic `environments/dev/main.tf` (645 lines) into domain files: ecr.tf, iam.tf, lambda.tf, secrets.tf, pipeline.tf, notifications.tf, web.tf
- Infra: Extracted `versions.tf` for both dev and bootstrap environments (separates version constraints from backend config)
- Infra: Standardised `tags.tf` with `local.common_tags` pattern across dev and bootstrap; deleted orphaned root `infrastructure/tags.tf`
- Infra: Bootstrap `main.tf` now references `local.common_tags` instead of inline tag map

### Added
- Infra: `modules/lambda-role/` — reusable IAM execution role module for pipeline Lambdas (S3, Secrets Manager, CloudWatch Logs, SNS policies)
- Infra: Comment on Secrets Manager resources documenting manual console population workflow
- `.gitignore`: Stopped ignoring `.terraform.lock.hcl` — lock files should be committed to pin provider versions

### Fixed
- Step Function: Added `CheckResolveStatus` guard before `CheckShouldRun` — prevents execution crash when `ResolveGameweek` Lambda returns a non-200 status (e.g. Cloudflare 403)
- Gameweek resolver: Added 403 retry with exponential backoff (matching `fpl_api_collector` pattern) — single-attempt fetch was failing on intermittent Cloudflare challenges

### Added
- Pipeline email notifications via EventBridge → SNS — sends email on pipeline success, failure, timeout, or abort
- Langfuse session IDs (`{season}-gw{gameweek}`) on all enrichment and curation traces — enables grouping all traces for a gameweek run in a single Langfuse session view
- Langfuse metadata (enricher name, prompt version, model, batch size) on every `enricher_batch_call` observation — enables filtering and comparing traces by enricher or prompt version
- Langfuse `output_count_valid` score on each LLM batch call — flags when the model returns fewer items than requested
- Langfuse `validation_pass_rate` score on each enricher trace — tracks what percentage of LLM outputs pass Pydantic validation
- Root conftest disables Langfuse tracing during tests (`LANGFUSE_TRACING_ENABLED=false`) to prevent polluting production dashboard with test data

### Changed
- ADR-0007: Added SSR (Next.js/Remix) as explicitly rejected option — documents why server-side rendering is unnecessary for a weekly-refresh personal dashboard

### Fixed
- Dashboard: Trends page — removed flat-line metrics (price, ownership, form, pts/m) that showed identical values across gameweeks due to bootstrap snapshot reuse; chart now tracks FPL Score only
- Dashboard: xG Efficiency scatter — axis labels showed corrupted numbers; capped domain to 99th percentile and added tick formatting
- Dashboard: Differential Radar scatter — player name missing from hover tooltip; replaced default tooltip with custom content renderer

### Changed
- Dashboard: Moved xG Efficiency, Ownership vs Value, and Momentum Heatmap charts above the player rankings table for better visibility

### Added
- Langfuse observability for curation service — `@observe(name="curate_gameweek")` tracing on the handler, matching the enrichment layer pattern
- Bootstrap infra comment documenting rationale for `AdministratorAccess` policy with OIDC-scoped trust
- CloudFront cache invalidation: EventBridge rule triggers a Lambda to invalidate `/api/v1/*` when the pipeline succeeds, so the dashboard serves fresh data immediately
- Dashboard v4: Captain Picker Decision Matrix page with weighted composite captaincy score
- Dashboard v4: Differential Radar page — scatter plot + card grid for low-ownership high-value players with sparklines
- Dashboard v4: Transfer Planner page — side-by-side player comparison with budget simulation, score pyramid, and form sparklines
- Dashboard v4: Gameweek Momentum Heatmap — FPL Score by player per gameweek (top 50 players)
- Dashboard v4: FDR number overlay in fixture grid cells for colour-blind accessibility
- Dashboard v4: Scatter outlier labels on xG Efficiency and Ownership vs Value charts (top 5 by distance)
- Dashboard v4: Position colour legend under scatter charts
- Dashboard v4: Team labels on Teams scatter chart
- Dashboard v4: Vitest + React Testing Library setup with 38 tests (utils + useApi hook)

### Changed
- Dashboard v4: Extracted PlayersPage into 5 focused sub-components (PlayerDetail, ScoreWaterfall, XgScatter, OwnershipBubble, MomentumHeatmap)
- Dashboard v4: Extracted TrendsPage into dedicated directory structure
- Dashboard v4: Created reusable useApi hook — replaced 6 duplicated useState+useEffect fetch patterns across all pages
- Dashboard v4: Moved chart colours, position colours, and score component colours into CSS custom properties (design system tokens)
- Dashboard v4: Added useSearchParams URL state sync for all page filters (position, search, sort, metric, player selection)
- Dashboard v4: Added mobile hamburger menu (md: breakpoint nav collapse)
- Dashboard v4: Added skip-to-content link, aria-sort on sortable headers, search labels, aria-pressed on filter buttons, keyboard navigation on expandable rows
- Dashboard v4: Added ErrorCard component with proper error states on all pages (replaces silent error swallowing)
- Dashboard v4: Added expand animation (CSS grid-template-rows transition) for player detail and transfer card expansion
- Dashboard v4: Footer now shows actual gameweek/season from briefing data instead of static text
- Dashboard v4: Expanded navigation to include Captain, Differentials, and Planner pages
- Dashboard v4: Shared TOOLTIP_STYLE constant for consistent Recharts tooltip styling

- Dashboard v3: Gameweek Briefing home page (top picks, injury alerts, fixture spotlight, form watch)
- Dashboard v3: Score Breakdown Waterfall in player detail panel (7 weighted components)
- Dashboard v3: xG Efficiency Scatter (Goals vs xG with diagonal reference)
- Dashboard v3: Ownership vs Value Bubble Chart (quadrant: differentials vs traps)
- Dashboard v3: Fixture Swing Chart (rolling 3-GW FDR with best-run callout)
- Dashboard v3: Expandable "Why Buy/Sell" AI cards on Transfers page (LLM summary, injury, sentiment, fixtures)
- Dashboard v3: Sentiment Timeline heatmap on Trends page
- Dashboard v3: Teams page quadrant labels and legend cleanup
- Dashboard v3: Error boundary with retry button
- Curate: score component outputs (score_form, score_value, etc.) exposed from scoring.py
- Curate: gameweek_briefing.json output with aggregated weekly signals (6 new tests)
- Dashboard v2: hero summary strip with AI Pick of the Week and KPI cards
- Dashboard v2: player table visual hierarchy (score bars, tier dividers, expand chevrons, heatmap cells)
- Dashboard v2: radar chart and styled AI analysis card in player detail panel
- Dashboard v2: dark mode with toggle and localStorage persistence
- Dashboard v2: transfer cards with coloured borders and sort controls
- Dashboard v2: teams page scatter plot (Score vs FDR quadrant analysis)
- Dashboard v2: fixture grid with team focus, FDR sum column, sort by difficulty
- Dashboard v2: skeleton loaders and empty states
- React dashboard (`web/dashboard/`) with 4 pages: Player Rankings, Fixture Ticker, Transfer Hub, Team Strength
- Static JSON output from CurateData Lambda for dashboard consumption (`public/api/v1/*.json`)
- ADR-0007: Static dashboard architecture (React SPA + pre-generated JSON on CloudFront)
- Architecture docs: system overview, data lake layers, LLM enrichment flow (Mermaid diagrams, render on GitHub)
- Merged `docs/diagrams/` into `docs/architecture/`
- Curate service (`services/curate/`) — derives 4 dashboard-ready datasets from enriched data
- Composite FPL score (0-100) blending form, value, fixtures, xG overperformance, ICT, injury risk, and ownership momentum
- Player dashboard curated table (300 enriched players with derived fields and rankings)
- Fixture ticker curated table (FDR heatmap data for remaining gameweeks)
- Transfer picks curated table (buy/sell/hold/watch recommendations with reasoning)
- Team strength curated table (20-team aggregation with avg FPL score, squad value, top scorer)
- `CurationResult` response model in `fpl_lib.core.responses`
- 46 unit tests for curate service (models, scoring, curators, handler)
- CurateData Lambda in Step Functions pipeline (after MergeEnrichments)
- ECR repository and Lambda module for curate service in Terraform
- Understat xG/xA join in player transformer — matches by normalised name, adds 8 Understat columns (understat_xg, understat_xa, understat_npxg, etc.)
- News articles attached to players for injury/sentiment enrichers via name matching
- Fixture data attached to players for fixture outlook enricher (next 5 GWs with difficulty ratings)
- Premier League keyword filter on RSS news collector (removes non-football content)
- 3 new unit tests for Understat join (match, unmatched, empty)
- Step Functions pipeline: 9-state machine (Collect FPL → Understat → News → Validate → Check → Transform → Enrich → Succeed/Fail)
- 6 Lambda modules in dev environment (fpl-api-collector, understat-collector, news-collector, validator, transform, enricher)
- EventBridge schedule: Tuesday 8am UTC weekly trigger
- Backfill script (`python -m fpl_data.scripts.backfill`) for historical gameweek processing
- Player data transformer (`flatten_player_data`) — selects 30+ key columns from 105 raw fields, casts types, adds metadata
- Deduplication utility for clean data
- Transformation Lambda handler with idempotency (skip if output exists, `force=True` to override)
- Clean Parquet output with zstd compression and `schema_version` metadata at `clean/players/season={season}/gameweek={gw}/`
- New column detection: logs warning when raw API adds unexpected fields
- 10 unit tests for transformer, deduplication, and handler
- Data validation engine with schema-driven checks (column presence, not-null, uniqueness, value ranges)
- Raw-data validation schemas (`PLAYER_EXPECTATIONS`, `FIXTURE_EXPECTATIONS`) using FPL API column names
- Validation Lambda handler with DLQ writing for failed records
- 10 unit tests for validation engine, handler, and DLQ
- News collector (`NewsCollector`) with RSS feed parsing (BBC, Sky Sports, Guardian)
- Date-based filtering for RSS entries using `published_parsed` time struct
- 4 unit tests for news collector with mocked feedparser
- Understat collector (`UnderstatCollector`) using POST API for xG/xA stats — league-level and per-player collection
- Rate limiting (1.5s sleep) for Understat requests
- Season format conversion (`2025-26` → `2025` for Understat API)
- 10 unit tests for Understat collector with mocked httpx
- Langfuse observability: `@observe` decorators on `_call_llm` and enrichment handler for LLM call tracing
- `EnrichSettings` config class extending `FPLSettings` with Langfuse and Anthropic credentials
- Four concrete enrichers: PlayerSummaryEnricher, InjurySignalEnricher, SentimentEnricher, FixtureOutlookEnricher
- Pydantic output models for all enricher outputs (structured validation)
- Enrichment Lambda handler with Secrets Manager integration, cost tracking, and fallback handling
- FPLEnricher abstract base class with batch processing, LLM call, output validation, and token tracking
- Prompt loader utility (`load_prompt()`) for versioned prompt templates
- Four v1 prompt templates: player_summary, injury_signal, sentiment, fixture_outlook
- Dev environment Terraform resources — ECR repo, S3 data lake + cost reports buckets, SNS pipeline alerts, Secrets Manager (Anthropic API key, Langfuse keys), shared Lambda IAM role
- Lambda module: optional `execution_role_arn` for shared external role support
- S3 data lake module: configurable `name` variable for multi-bucket reuse
- Step Functions module: CloudWatch log group with execution logging
- ADR-0002: S3 data lake design (layers, idempotency, container deployment, Hive partitioning, Parquet+zstd)
- ADR-0003: Direct Anthropic API over LangChain
- ADR-0004: LLM cost optimisation (model tiering, input filtering, rate limiting, capacity lock skip)
- ADR-0005: Prompt versioning and LLM observability (directory-based versioning, Langfuse tracing)
- ADR-0006: Parallel pipeline design (Step Functions parallel states for collection and enrichment)

### Changed
- Enricher base class now fully async: `AsyncAnthropic` client, `asyncio.Semaphore` for rate limiting, `asyncio.gather` for concurrent batch processing
- Enrichment handler runs all 4 enrichers in parallel with shared semaphore (max 5 concurrent API calls for Tier 1 limits)
- Structured logging in RunHandler: `[START]`, `[SUCCESS]`, `[ERROR]` with duration and params
- `[ANTHROPIC]`, `[FPL API]`, `[UNDERSTAT]`, `[RSS]` prefixed logging on all external API calls
- Step Functions log level configurable (default `ALL` for full execution tracing)
- Enricher Lambda timeout increased to 900s (Lambda max)
- ADRs consolidated from 11 to 6: merged related decisions (data lake + idempotency + containers, prompt versioning + observability, parallel design), dropped low-signal entries (Terraform over CDK)
- Lambda module: log retention 14d → 30d, default memory 256 → 512 MB
- S3 data lake module: added raw/ prefix expiration at 90 days

### Fixed
- ECR module: tag mutability now configurable (default MUTABLE) — fixes deploy failure where `:latest` push was rejected by IMMUTABLE policy
- S3 data lake lifecycle: transition days (30) now less than expiration days (90) to satisfy AWS API constraint
- S3 data lake lifecycle rules now conditional (`enable_data_lake_lifecycle`) so non-data-lake buckets skip raw/dlq rules
- ECR repo naming order matches deploy.yml convention (`fpl-{name}-{env}` not `fpl-{env}-{name}`)
- Dev environment now creates 3 ECR repos (data, enrich, agent) matching the per-service deploy matrix

## [0.1.0] - 2026-04-04

### Added
- Monorepo structure with 5 service stubs (`data`, `enrich`, `etl`, `agent`, `stream`)
- Shared library (`libs/fpl_lib/`) — `ExceptionCollector`, `FPLSettings`, `RunHandler`, `S3Client`, Pydantic domain models (`Player`, `Fixture`), validators, date utils
- Terraform bootstrap — S3 state bucket, DynamoDB lock table, GitHub OIDC provider, CI/CD IAM role (`FPL-Dev-CICD-Role`), budget alerts
- Terraform modules — `lambda`, `s3-data-lake`, `step-function`, `ecr`
- GitHub Actions CI — path-filtered lint/test on PRs, `terraform plan` on infra changes
- GitHub Actions deploy — `terraform apply` and ECR build/Lambda deploy on merge to main
- Pre-commit hooks — ruff, mypy, terraform fmt
- Makefile with `install`, `lint`, `format`, `test`, `check` targets
- Claude Code config — `CLAUDE.md`, path-specific rules, 4 custom skills, MCP server config
- ADR-0001 (monorepo architecture)
- Data dictionary, runbook, PR/issue templates
- 15 passing unit tests (`ExceptionCollector`, `FPLSettings`, `S3Client`)
