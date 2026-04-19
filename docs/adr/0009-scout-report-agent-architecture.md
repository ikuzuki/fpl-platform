# ADR-0009: Scout Report Agent Architecture

## Status
Accepted

## Date
2026-04-12

## Context
Phase 2 adds a conversational agent to the platform. Users ask natural language questions about FPL players — "Is Salah worth the price?", "Compare Palmer and Saka", "Best budget midfielders for the next 5 gameweeks?" — and the agent dynamically gathers data and produces a structured analysis.

We needed to decide: what kind of agent, what architecture, which models at which nodes, and how to control costs for a publicly accessible endpoint.

## Options Considered

### Framework choice

ADR-0003 rejected LangChain for the enrichment pipeline and flagged agentic orchestration as the likely exception. This is that exception — worth making the boundary explicit rather than leaving it as a footnote.

**1. Hand-rolled state machine (rejected)**
Implement the 4-node graph directly with a dispatch loop, a state dict, and manual tool-call plumbing against the Anthropic SDK.

Rejected because: rebuilding conditional edges, checkpointing, tool-schema generation, and streaming event emission for no gain over a well-maintained library. The same arguments that made direct SDK calls *right* for batch enrichment (simple request-response, full prompt control) make them *wrong* here — agent execution has non-trivial control flow that a framework expresses better than bespoke code.

**2. Pydantic AI (rejected)**
Type-first agent framework built around Pydantic models and a single-agent execution loop.

Rejected because: at the time of choosing, its graph primitives were less developed than LangGraph's — the multi-node reflection loop with conditional routing is exactly what LangGraph is built for. Pydantic AI is a strong fit for single-agent tool-calling; less natural for this shape.

**3. LangGraph (chosen)**
State machine with typed state, conditional edges, streaming, and tool-calling primitives. Used only for the agent — the enrichment pipeline continues to call the Anthropic SDK directly per ADR-0003.

### Agent framing

**1. Transfer recommender — "give me your team, I'll suggest transfers" (rejected)**
User provides their FPL team ID, agent fetches their squad and budget, recommends optimal transfers.

Rejected because: the FPL API is unreliable from AWS IPs (Cloudflare blocking), and the entire interaction is constrained to one question type. The agent architecture (tool calling, reflection loops, structured outputs) is more impressive when the execution path varies per question.

**2. Gameweek briefing agent — autonomous research report (rejected)**
Given a gameweek number, the agent autonomously investigates the landscape and produces a structured briefing.

Rejected because: the output is pre-deterministic — every user asking about GW30 gets essentially the same report. This is closer to what the pipeline already does (curated data + LLM summaries) and doesn't demonstrate dynamic tool selection.

**3. Scout report agent — conversational, question-driven (chosen)**
User asks any question. Agent plans what data to gather, calls tools, reflects on sufficiency, and produces a tailored analysis. Different questions trigger different tool sequences and different reasoning paths.

Chosen because: most flexible (handles any question), best demonstrates tool calling and reflection (different questions require different tools), and most engaging as a live demo.

### Graph architecture

**1. Simple ReAct loop — reason, act, observe (rejected)**
Standard single-node loop: LLM decides action → execute tool → LLM observes result → repeat.

Rejected because: no separation between planning, execution, and evaluation. A single LLM call handles all three concerns, which makes it harder to use different models at different stages and harder to debug which phase went wrong.

**2. Planner → Tools → Recommender — 3 nodes (rejected)**
Plan what to investigate, gather data, generate response. No reflection.

Rejected because: without a reflection step, the agent can't evaluate whether it gathered enough data. If the planner missed something (e.g. asked about Salah but forgot to check fixture difficulty), the recommender just works with incomplete data. The reflection loop is what makes the agent genuinely agentic rather than a fancy chain.

**3. Planner → Tools → Reflector → Recommender — 4 nodes with loop (chosen)**
Four distinct nodes with a conditional loop between reflector and planner.

## Decision

### 4-node LangGraph state machine

```
START → Planner → Tool Executor → Reflector ─┐
            ↑                                  │
            └──── (needs more data) ───────────┘
                                               │
                                    (sufficient) ↓
                                          Recommender → END
```

**Planner** — receives the user's question and any previously gathered data. Outputs a structured plan: which tools to call and with what arguments. Uses Haiku (planning is a lightweight reasoning task).

**Tool Executor** — no LLM. Dispatches tool calls from the plan, executes concurrently where independent, accumulates results. Tools: `query_player`, `search_similar_players`, `query_players_by_criteria`, `get_fixture_outlook`, `get_injury_signals`. Squad loading is HTTP-layer only (`GET /team` → `UserSquad` echoed back on every `POST /chat`); the agent reads `state["user_squad"]` rather than dispatching a fetch tool — letting the LLM dispatch a cross-service Lambda invoke at planning time would require it to invent a `team_id` it has no source of truth for.

**Tool constraint: no user-controlled URLs.** Every current tool is a parameterised Neon query or an internal Lambda invoke — no tool fetches an arbitrary URL. Any future tool that needs URL fetching (news enrichment, image OCR, link summarisation) must (a) validate the destination IP against a loopback / link-local / RFC1918 blocklist before connecting, (b) resolve-then-connect-by-IP so the check can't be bypassed via DNS rebinding, and (c) be scoped to an explicit domain allowlist. Without this, a prompt-injection attack could coerce the agent into fetching `http://169.254.169.254/latest/meta-data/iam/security-credentials/` and streaming the Lambda's IAM credentials back to the client (the SSRF-to-IMDS pivot behind the 2019 Capital One breach). See [`docs/architecture/security-architecture.md`](../architecture/security-architecture.md).

**Reflector** — evaluates whether the gathered data is sufficient to answer the question. If not, identifies what's missing and sends it back to the planner. Maximum 3 iterations to bound latency and cost. Uses Haiku.

**Recommender** — synthesises all gathered data into a structured `ScoutReport` (analysis, player cards, recommendation, caveats, data sources). This is the only node that uses Sonnet, because it requires deep reasoning across multiple data points.

### Tiered model usage

Same principle as ADR-0004 (model selection by task complexity), applied to agent nodes:

| Node | Model | Why |
|------|-------|-----|
| Planner | claude-haiku-4-5 | Planning is structured and formulaic — "which tools for this question?" |
| Reflector | claude-haiku-4-5 | Binary decision with brief reasoning — "sufficient or not?" |
| Recommender | claude-sonnet-4-6 | Synthesising multiple data sources into coherent analysis needs stronger reasoning |
| Tool Executor | None | Pure function dispatch, no LLM |

This keeps per-query cost to ~$0.03-0.08. Most tokens are spent in the recommender (one call), while the planner and reflector (which may loop 2-3 times) use the cheaper model.

### Cost controls

The agent endpoint is publicly accessible — anyone with the URL can send questions. Without controls, a bad actor (or an enthusiastic interviewer) could exhaust the API budget in minutes.

**Three layers of protection:**

1. **Lambda reserved concurrency + per-session rate limiter** — reserved concurrency caps parallel Lambda invocations (hardware-level backpressure); the in-app `RateLimiter` caps per-session request rate. Replaced API Gateway throttling after ADR-0010 moved the transport to Lambda Function URL. Full security posture documented in `docs/architecture/security-architecture.md`.

2. **DynamoDB budget kill-switch** — tracks cumulative token usage per month. At the start of each request, check if monthly spend exceeds $5. If yes, return 429 with "demo has hit its monthly limit." This is the hard cap — even if rate limiting fails, spend is bounded. Langfuse (ADR-0005) is the observability layer for tracing and post-hoc cost analysis; enforcement stays on DynamoDB because the check is on the hot request path and must not depend on third-party SaaS availability. DynamoDB also gives atomic `UpdateItem ADD` increments, which a batched telemetry pipeline cannot — two concurrent requests would both read stale "before" spend from Langfuse and both proceed past the cap.

3. **Max 3 agent iterations** — the reflector loop is capped. Most queries resolve in 2 iterations. This bounds per-request cost regardless of question complexity.

No authentication required. For a portfolio project, aggressive throttling plus a budget cap is sufficient.

## Consequences
**Easier:**
- Conversational interface handles any question type without separate endpoints per use case
- 4-node separation makes debugging clear — you can see exactly where the agent went wrong
- Tiered models keep cost low while maintaining output quality where it matters
- Budget controls mean the demo can be public without financial risk

**Harder:**
- 4 nodes + tools is more complex than a simple chain — more code to maintain
- Latency is 10-15 seconds per query (3-4 sequential LLM calls) — mitigated by streaming intermediate steps via SSE
- Lambda's 60-second timeout bounds agent execution (up from the 29s API Gateway cliff after ADR-0010); 3-iteration cap keeps typical runs well under that
- DynamoDB budget tracking adds a read + write per request — minor latency and another infrastructure component
- Max 3 iterations means some complex questions may get incomplete analysis — acceptable trade-off for cost control

## Related
- ADR-0003: Direct API over LangChain — the agent is the explicit exception where LangGraph earns its place
- ADR-0004: LLM cost optimisation — same tiered model principle, applied to agent nodes
- ADR-0007: Static dashboard architecture — the agent API coexists with the static dashboard under one CloudFront distribution
- ADR-0008: Neon pgvector — the agent's data retrieval layer
