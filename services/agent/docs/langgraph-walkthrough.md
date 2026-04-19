# Scout Report Agent — LangGraph Walkthrough

> Reference doc. Originated as the implementation plan for PR #91 (Wave 3 PR 1 of 3). Preserved here because the design decisions and learning notes (LangGraph state, reducers, tool-use structured output, factory closures) are the kind of thing a future reader benefits from having in one place.
>
> **For the architectural overview / cost model / runbook, see [docs/architecture/agent-architecture.md](../../../docs/architecture/agent-architecture.md).**
>
> **For the accepted design decisions, see [ADR-0009](../../../docs/adr/0009-scout-report-agent-architecture.md).**

---

## LangGraph primer

LangGraph is the one escape-hatch from [ADR-0003](../../../docs/adr/0003-no-langchain.md) ("no LangChain"). It earns its place because the agent needs a **stateful loop with conditional branching**, and rolling that by hand would be more code than it's worth. Core concepts:

| Concept | What it is | Analogy (for a backend eng) |
|---|---|---|
| `StateGraph` | The graph builder. You add nodes, add edges, then `.compile()`. | A state machine definition — like a Step Functions ASL, but in Python. |
| **State** | A `TypedDict` passed to every node. Each node returns a *partial* dict — LangGraph merges it into the running state. | Immutable-ish context object. Like a Lambda event that accretes fields as it flows through steps. |
| **Node** | A function `(state) -> dict`. Pure in shape; may be sync or async. | A handler in a Step Functions state. |
| **Edge** | `graph.add_edge("a", "b")` — after node `a`, run node `b`. | Static transition. |
| **Conditional edge** | `graph.add_conditional_edges("reflector", route_fn, {"continue": "planner", "done": "recommender"})`. `route_fn(state)` returns a string; LangGraph looks it up in the mapping. | `Choice` state in Step Functions — the routing function inspects state and picks the next node. |
| `START` / `END` | Sentinel nodes marking graph entry/exit. | `StartAt` / terminal state in ASL. |
| `.invoke(state)` / `.astream(state)` | Run the graph. `astream` yields intermediate states for UI updates. | Synchronous vs streaming execution. |

### State mutation model — the core LangGraph mental model

A node does NOT mutate state in place. It returns a *partial* dict of what changed, and LangGraph merges it using a **reducer** per field.

Conceptually, after every node:

```python
for key, value in node_return_dict.items():
    state[key] = reducer[key](state[key], value)
```

**What's a reducer?** A function `(old_value, new_value) → combined_value`. Same concept as Redux reducers or `functools.reduce`. LangGraph uses them to decide *how* to combine old state with a node's update. You declare the reducer once in the state `TypedDict` via `Annotated[Type, reducer_fn]` — every future update to that key goes through it automatically.

Three reducers in this agent:

| Field | Reducer | Behaviour | Why |
|---|---|---|---|
| `plan` | default (overwrite) | `state["plan"] = new_plan` | Each iteration's plan replaces the previous one |
| `tool_calls_made` | `operator.add` | `state["tool_calls_made"] = old + new` | Audit trail — accumulate across iterations |
| `gathered_data` | `merge_dicts` (custom) | `state["gathered_data"] = {**old, **new}` | Iteration 2's tool results add to iteration 1's, not replace |

Worked example across a 2-iteration run:

```
Iteration 1:
  planner returns {"plan": [query_player("Salah")], "tool_calls_made": ["query_player"]}
    → state["plan"] = [query_player("Salah")]               (overwrite — no prior plan)
    → state["tool_calls_made"] = [] + ["query_player"]      (operator.add)
  tool_executor returns {"gathered_data": {"query_player": {...Salah data...}}}
    → state["gathered_data"] = {**{}, **{"query_player": ...}}  (merge_dicts)
  reflector returns {"should_continue": True, "iteration_count": 1}
    → overwrite both (defaults)

Iteration 2:
  planner returns {"plan": [get_fixture_outlook("Salah")], "tool_calls_made": ["get_fixture_outlook"]}
    → state["plan"] = [get_fixture_outlook(...)]            (overwrite — old plan gone)
    → state["tool_calls_made"] = ["query_player"] + ["get_fixture_outlook"]
                                                            (accumulated via operator.add)
  tool_executor returns {"gathered_data": {"get_fixture_outlook": {...}}}
    → state["gathered_data"] = {"query_player": ..., "get_fixture_outlook": ...}
                                                            (merged — iter 1 data preserved)
```

The recommender at the end sees the full `gathered_data` from both iterations. If we'd used the default overwrite reducer on `gathered_data`, iteration 2 would wipe iteration 1 and the recommender would only see fixture outlook, not the Salah player data.

### "Anthropic's native tool-use API" comparison

Both options below use the Anthropic API. The difference is **how the LLM drives tool calling**:

**Option A — native agentic tool-use (rejected):**

```
Turn 1: LLM → "call query_player"   [API call 1]
        Our code runs query_player, appends result to messages
Turn 2: LLM → "call search_similar"  [API call 2]
        Our code runs it, appends result
Turn 3: LLM → final text answer       [API call 3]
```

Sequential. The LLM controls the loop. Each tool is a real function Anthropic knows about.

**Option B — planner-first (chosen):**

```
API call 1 (planner):    LLM → plan = [query_player, search_similar]  (single shot)
                         Our code runs BOTH in parallel via asyncio.gather
API call 2 (reflector):  LLM → sufficient? yes/no
API call 3 (recommender): LLM → final ScoutReport
```

Fixed 3-call structure. Tools run concurrently. Our Python controls the loop. The LLM outputs a *plan* via a fake `record_plan` tool — tool-use here is a structured-output mechanism, not an agentic loop.

**Why Option B wins:**

- **Concurrent dispatch** — parallel `asyncio.gather`. Option A is sequential.
- **Bounded cost** — fixed 3 API calls × 3 iterations max = 9. Option A has no natural bound.
- **Easier to trace** — one plan object to log per iteration. Option A interleaves calls and tool results in message history.

Trade-off: if the planner picks a bad tool-arg, we only find out at execution. Executor records the error in `gathered_data`, reflector sees it and can re-plan.

---

## Architecture

```
              ┌────────────────────────────────────────┐
              │                                        │
START → planner → tool_executor → reflector ──needs more──┘
         │  Haiku      (no LLM)        │  Haiku
         │                             │
         │                             sufficient
         │                             ↓
         └─────────────────────→ recommender → END
                                    Sonnet
```

**State (`AgentState`):**

```python
class AgentState(TypedDict):
    question: str                              # user's input, immutable after START
    user_squad: UserSquad | None               # input context, seeded from ChatRequest.squad (see PR #119)
    plan: list[ToolCall]                       # planner output for current iteration
    gathered_data: Annotated[dict, merge_dicts] # accumulates across iterations
    tool_calls_made: Annotated[list[str], operator.add]  # audit trail
    iteration_count: int                       # incremented by reflector
    should_continue: bool                      # set by reflector; read by conditional edge
    final_response: ScoutReport | None         # populated by recommender
    error: str | None                          # short-circuit on fatal failure
```

The `merge_dicts` reducer lets tools from iteration 2 add keys without wiping iteration 1's data.

---

## Files

### `services/agent/src/fpl_agent/models/state.py` — state definition

- `ToolCall` — Pydantic: `name: Literal[<5 tool names>]`, `args: dict[str, Any]`
- `AgentState` — `TypedDict` as shown above
- `merge_dicts(a, b)` — helper reducer: returns `{**a, **b}`

**Learning note:** we use `TypedDict` for state (not Pydantic) because LangGraph's reducers only work on TypedDicts. But `ToolCall` and response models use Pydantic v2 for validation — LangGraph doesn't touch those.

### `services/agent/src/fpl_agent/models/responses.py` — output schemas

Pydantic v2 models the recommender generates:

- `PlayerAnalysis` — `player_name`, `position`, `price`, `form`, `fixture_outlook: Literal["green","amber","red"]`, `verdict: str`, `confidence: float`
- `ComparisonResult` — `players: list[PlayerAnalysis]`, `winner: str | None`, `reasoning: str`
- `ScoutReport` — `question: str`, `analysis: str`, `players: list[PlayerAnalysis]`, `comparison: ComparisonResult | None`, `recommendation: str`, `caveats: list[str]`, `data_sources: list[str]`
- `AgentResponse` — thin envelope: `report: ScoutReport`, `iterations_used: int`, `tool_calls_made: list[str]`

**Why Pydantic v2 here but TypedDict for state?** State needs reducers (LangGraph requirement). Responses need strict validation at the API boundary (client contract). Different jobs, different tools.

### `services/agent/src/fpl_agent/tools/player_tools.py` — 5 async tools

All tools:

- Are `async def`
- Take a `NeonClient` (passed via closure — see "Tool factory pattern" below)
- Return `dict[str, Any]` (raw data; recommender does the shaping)
- Decorated with `@observe(name="tool.<name>")` for Langfuse spans
- Raise `ToolError` on fatal failure — executor catches and records

| Tool | SQL / call | Returns |
|---|---|---|
| `query_player(name: str)` | `SELECT ... FROM player_embeddings WHERE web_name ILIKE $1 LIMIT 1` | full player row (all columns, no vector) |
| `search_similar_players(player_name, k=5)` | Look up target's embedding, then `ORDER BY embedding <=> $1 LIMIT $2` (cosine distance) | list of k similar players with similarity scores |
| `query_players_by_criteria(position=None, max_price=None, min_form=None, team=None, limit=20)` | Dynamic WHERE clause on structured columns | list of matching player rows |
| `get_fixture_outlook(player_name)` | For now: returns `fixture_difficulty` column from the stored row. *Note:* richer fixture data is a future enrichment — flagged in caveats. | `{player, difficulty, note}` |
| `get_injury_signals(player_name)` | Returns `injury_risk_score`, `form_trend`, and `summary` fields from the stored enrichment | injury signal dict |

**Squad loading is not a tool.** PR #119 moved it from the tool registry into the HTTP layer (`GET /team` → `UserSquad` echoed back on every `POST /chat` → seeded onto `state["user_squad"]`). Letting the LLM dispatch a cross-service Lambda invoke at planning time would have required it to invent a `team_id` it has no source of truth for. See `services/agent/src/fpl_agent/squad_loader.py` for the loader and `docs/architecture/agent-architecture.md` for the rationale.

**Tool factory pattern — what and why.** A "factory" is just a function that creates things. Here, `make_tools(neon)` creates 5 callable tools, each with the `NeonClient` captured in its closure:

```python
def make_tools(neon: NeonClient) -> dict[str, Callable]:
    async def query_player(name: str) -> dict:
        # `neon` captured from enclosing scope — no need to pass it in
        row = await neon.fetch_one("SELECT ... WHERE web_name ILIKE $1", name)
        return dict(row)

    async def search_similar_players(player_name: str, k: int = 5) -> list[dict]:
        # same closure, same `neon`
        ...

    return {"query_player": query_player, "search_similar_players": search_similar_players, ...}
```

The `tool_executor_node` calls `make_tools(neon)` once per graph run, gets back a dict, and dispatches by name: `tools[plan_item.name](**plan_item.args)`.

**Why this pattern:**

- **Can't put `NeonClient` in state** — LangGraph tries to merge/serialise state on every node transition. A live DB connection doesn't merge.
- **Don't want a module-level global client** — makes tests messy, complicates Lambda cold starts (connection would be held across invocations).
- **Don't want a class hierarchy** — 6 tools with one shared dep doesn't justify `class PlayerTools: def __init__(self, neon): ...`.

Closures are the lightweight answer: functional dependency injection. To test, just pass a `MagicMock(spec=NeonClient)` to `make_tools` and assert on the returned functions.

### `services/agent/src/fpl_agent/graph/config.py` — constants

```python
PLANNER_MODEL = "claude-haiku-4-5"
REFLECTOR_MODEL = "claude-haiku-4-5"
RECOMMENDER_MODEL = "claude-sonnet-4-6"
MAX_ITERATIONS = 3
TOOL_TIMEOUT_SECONDS = 10
PLANNER_MAX_TOKENS = 1024
REFLECTOR_MAX_TOKENS = 512
RECOMMENDER_MAX_TOKENS = 4096
```

Models pulled from ADR-0009. Timeouts per tool so a slow Neon query can't blow the Lambda's 60s ceiling.

### `services/agent/src/fpl_agent/graph/prompts/v1/` — prompt templates

Per `.claude/rules/llm-enrichment.md`: prompts live in versioned directories, never inline. Three files:

- `planner.md` — describes the 6 available tools and when to use each. The LLM is forced to emit a `record_plan` tool-use, so the prompt focuses on *which tools to choose* rather than *JSON syntax*.
- `reflector.md` — describes the sufficiency criteria. The LLM is forced to emit a `record_reflection` tool-use.
- `recommender.md` — describes `ScoutReport` structure at a conceptual level (what each field means). The LLM is forced to emit a `record_scout_report` tool-use; the full JSON schema is supplied programmatically via `input_schema`, not copy-pasted into the prompt.

**Prompts don't ship the schema** — because tool-use carries it over the wire. This keeps the prompts readable and means a schema change (new field on `ScoutReport`) doesn't require editing the prompt.

### `services/agent/src/fpl_agent/graph/nodes.py` — 4 nodes

Each node:

- `async def` (so tools and LLM calls can use native async)
- Takes `state: AgentState`, returns `dict` (partial state update)
- Decorated `@observe(name="node.<name>")` if it calls an LLM
- Uses the `anthropic.AsyncAnthropic` client
- Records `input_tokens` + `output_tokens` from the response for cost tracking

**All LLM nodes use Anthropic tool-use for structured output.** See "Structured output via tool-use" below for the full rationale. Each node declares a fake tool whose `input_schema` matches its expected Pydantic output, passes `tool_choice={"type": "tool", "name": <name>}`, and reads `response.content[0].input` as a dict → feeds straight into Pydantic. Anthropic enforces JSON validity server-side, so no retry-on-bad-JSON is needed.

**planner_node**

1. Render planner prompt with `state["question"]` + `state["gathered_data"]`
2. Call Haiku with `tools=[plan_tool]`, `tool_choice={"type": "tool", "name": "record_plan"}`
3. Read `response.content[0].input["plan"]` → Pydantic-validate as `list[ToolCall]`
4. Return `{"plan": plan, "tool_calls_made": [tc.name for tc in plan]}`

**tool_executor_node** (no LLM)

1. Get tool registry (injected via `functools.partial` at build time)
2. For each `ToolCall` in `state["plan"]`: wrap in `asyncio.wait_for(tool(**tc.args), TOOL_TIMEOUT_SECONDS)`
3. `results = await asyncio.gather(*coros, return_exceptions=True)` — concurrent dispatch, failures don't cancel siblings
4. Build `{tool_name: result_or_error_dict}`; return `{"gathered_data": results_dict}`

**reflector_node**

1. If `state["iteration_count"] + 1 >= MAX_ITERATIONS`: force `should_continue=False` (hard cap, don't call the LLM)
2. Otherwise render reflector prompt with gathered data
3. Call Haiku with `tools=[reflection_tool]`, `tool_choice` forced to it
4. Read structured result → Pydantic-validate as `ReflectionResult`
5. Return `{"should_continue": not result.sufficient, "iteration_count": <incremented>}`

**recommender_node**

1. Render recommender prompt with all context
2. Call Sonnet with `tools=[scout_report_tool]`, `tool_choice` forced to it
3. Read structured result → Pydantic-validate as `ScoutReport`
4. Return `{"final_response": report}`

**Learning note:** each node returns *only the keys it changes*. LangGraph merges. This makes nodes composable and testable — you can unit-test `reflector_node` by passing a state dict with fake `gathered_data` and asserting on the returned dict.

### `services/agent/src/fpl_agent/graph/builder.py` — graph assembly

```python
def build_agent_graph(*, client, tools) -> CompiledStateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("planner", partial(planner_node, client=client))
    graph.add_node("tool_executor", partial(tool_executor_node, tools=tools))
    graph.add_node("reflector", partial(reflector_node, client=client))
    graph.add_node("recommender", partial(recommender_node, client=client))

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "tool_executor")
    graph.add_edge("tool_executor", "reflector")
    graph.add_conditional_edges(
        "reflector",
        route_after_reflector,
        {"continue": "planner", "done": "recommender"},
    )
    graph.add_edge("recommender", END)

    return graph.compile()
```

**Learning note:** `StateGraph(AgentState)` types every node's state parameter. The conditional edge function is a plain Python function — no magic, just returns a string key that LangGraph looks up in the mapping. `functools.partial` is how we inject the Anthropic client and tool registry: it produces a new callable with those kwargs pre-bound so LangGraph (which calls each node as `node(state)`) still sees a one-arg function.

---

## Structured output via tool-use

**The problem.** LLMs produce text one token at a time. Asking "respond with JSON" is a *soft* constraint — the model usually obliges but can drift: wrap output in ` ```json ``` ` fences, add a preamble ("Here's the plan:"), miss a closing brace on long outputs, hallucinate a field. Downstream Pydantic then raises `ValidationError` and the node fails.

**The fix.** Anthropic's tool-use API doubles as a structured-output mechanism. You define a *fake tool* whose `input_schema` is your Pydantic schema, force the model to "call" it, and Anthropic's server-side decoder constrains token sampling to only produce JSON that matches the schema. You read `response.content[0].input` as a dict and hand it to Pydantic.

```python
plan_tool = {
    "name": "record_plan",
    "description": "Record the tools to call for this iteration.",
    "input_schema": {
        "type": "object",
        "properties": {
            "plan": TypeAdapter(list[ToolCall]).json_schema(),
        },
        "required": ["plan"],
    },
}

response = await client.messages.create(
    model=PLANNER_MODEL,
    max_tokens=PLANNER_MAX_TOKENS,
    tools=[plan_tool],
    tool_choice={"type": "tool", "name": "record_plan"},  # FORCE this tool
    messages=[{"role": "user", "content": rendered_prompt}],
)
tool_use_block = next(b for b in response.content if b.type == "tool_use")
plan = TypeAdapter(list[ToolCall]).validate_python(tool_use_block.input["plan"])
```

**What this buys us:**

- **Syntactic validity guaranteed** — no more missing-brace or unterminated-string errors
- **Schema matching enforced** — required fields are present, types match, enums are respected
- **No retry loop needed for format errors** — they can't happen

**What it doesn't solve:**

- **Semantic errors** — e.g. planner names a tool `"search_players"` that doesn't exist. We catch this at the Pydantic layer via `name: Literal["query_player", ...]` — the `Literal` constrains the string to the 6 valid values, and Pydantic raises on anything else.
- **Empty / nonsensical outputs** — the model could technically return `{"plan": []}`. Our planner prompt explicitly forbids this, and the reflector would flag insufficient data if it happens.

**Why not Anthropic's `response_format` like OpenAI?** Anthropic doesn't have an equivalent. Tool-use *is* their structured-output mechanism — it's been the idiomatic pattern since Claude 3.

**Residual safety net.** If tool-use somehow returns something Pydantic can't validate (Anthropic bug, model edge case), each node catches `ValidationError`, logs it, sets `state["error"]`, and short-circuits to `END`. The API handler in #92 will render `state["error"]` as a 500 with a user-friendly message. No retry — tool-use doesn't fail transiently the way JSON parsing does.

### Is tool-use for structured output common? Expensive? Should enrichment use it?

**Common:** yes — it's the canonical Anthropic structured-output pattern. Instructor-anthropic, LangChain's Anthropic adapter, and most production Anthropic apps use it. OpenAI has `response_format={"type": "json_schema", ...}` as a first-class API; Anthropic's equivalent is forced tool-use.

**Expensive?** Essentially no:

- **Input side:** the tool schema counts as input tokens (~200 for `ScoutReport`). Tiny. And because the schema is byte-identical on every call, **prompt caching** stores it at 90% discount for 5min TTL — effectively free on repeat calls.
- **Output side:** often *cheaper* because the model can't emit prose preambles, markdown fences, or explanations — just the JSON payload.
- **Latency:** comparable. No extra round-trip.

Net: within ±10% of an unstructured call, often cheaper once caching kicks in. And you save the cost of retries on malformed JSON (which can double the cost of a call when they happen).

**Should enrichment use it too?** Almost certainly. Current enrichment does "respond with this JSON shape" via prompt + parse + retry. Switching to tool-use would:

- Eliminate `JSONDecodeError` retry loops
- Make the Pydantic model the schema source of truth (exported programmatically, not copy-pasted into prompts)
- Cache the schema across bulk calls — big win for the Haiku summary pipeline which makes hundreds of calls per run

Out of scope for PR #91, but worth a follow-up refactor issue.

---

## Key decisions

1. **Planner-first over native tool-use** — concurrent dispatch, bounded cost, easier to trace. Worth revisiting if most queries hit a single tool.
2. **`TypedDict` for state, Pydantic for I/O** — LangGraph reducers need TypedDict; API contracts need Pydantic validation.
3. **Tools receive NeonClient via factory closure, not state** — live connections don't merge/serialise.
4. **Reflector hard-caps before calling the LLM** — saves one Haiku call when iteration limit is already reached.
5. **`asyncio.gather(..., return_exceptions=True)`** — one slow/broken tool doesn't cancel the others.
6. **Token usage logged, not enforced** — PR #91 records it for the kill-switch in #92/#93.
7. **Squad loading is HTTP-layer only (not a tool)** — `GET /team` invokes the team-fetcher Lambda + Neon enrichment via `squad_loader.py`. Dashboard echoes the loaded `UserSquad` on every chat request; agent reads `state["user_squad"]`. Keeps cross-service Lambda invokes off the planner's discretion. (PR #119)

---

## Answered during planning

- **`search_similar_players`** — reads the target's stored vector from Neon (cheaper, faster than re-embedding; re-embedding is a future optimisation for "hypothetical profile" queries).
- **Planner fallback on invalid JSON** — resolved by tool-use. Server-side schema enforcement eliminates JSON syntax failures. Residual semantic failures (invalid Pydantic validation) short-circuit to `state["error"]`.
