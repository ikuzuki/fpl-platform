# ADR-0009: Scout Report Agent Architecture

## Status
Accepted

## Date
2026-04-12

## Context
Phase 2 adds a conversational agent to the platform. Users ask natural language questions about FPL players — "Is Salah worth the price?", "Compare Palmer and Saka", "Best budget midfielders for the next 5 gameweeks?" — and the agent dynamically gathers data and produces a structured analysis.

We needed to decide: what kind of agent, what architecture, which models at which nodes, and how to control costs for a publicly accessible endpoint.

## Options Considered

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

**Tool Executor** — no LLM. Dispatches tool calls from the plan, executes concurrently where independent, accumulates results. Tools include: `query_player`, `search_similar_players`, `query_players_by_criteria`, `get_fixture_outlook`, `get_injury_signals`, `fetch_user_squad`.

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

1. **API Gateway throttling** — 10 requests/second, 20 burst. First line of defence, zero code, configured in Terraform.

2. **DynamoDB budget kill-switch** — tracks cumulative token usage per month. At the start of each request, check if monthly spend exceeds $5. If yes, return 429 with "demo has hit its monthly limit." This is the hard cap — even if rate limiting fails, spend is bounded.

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
- Lambda's 29-second API Gateway timeout constrains agent execution time — acceptable given the 3-iteration cap
- DynamoDB budget tracking adds a read + write per request — minor latency and another infrastructure component
- Max 3 iterations means some complex questions may get incomplete analysis — acceptable trade-off for cost control

## Related
- ADR-0003: Direct API over LangChain — the agent is the explicit exception where LangGraph earns its place
- ADR-0004: LLM cost optimisation — same tiered model principle, applied to agent nodes
- ADR-0007: Static dashboard architecture — the agent API coexists with the static dashboard under one CloudFront distribution
- ADR-0008: Neon pgvector — the agent's data retrieval layer
