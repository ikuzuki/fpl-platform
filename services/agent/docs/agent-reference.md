# Agent Quick Reference

Scan-first companion to [`langgraph-walkthrough.md`](langgraph-walkthrough.md) (the learning doc) and [`../../../docs/architecture/agent-architecture.md`](../../../docs/architecture/agent-architecture.md) (the system overview).

---

## Flow at a glance

```
request
   │
   ▼
┌──────────┐   ┌───────────────┐   ┌──────────┐            ┌─────────────┐
│ planner  │──▶│ tool_executor │──▶│reflector │──sufficient│ recommender │──▶ response
│  Haiku   │   │   (no LLM)    │   │  Haiku   │───────────▶│   Sonnet    │
└──────────┘   └───────────────┘   └────┬─────┘            └─────────────┘
      ▲                                 │
      └─────────── needs more ──────────┘
             (max 3 iterations)
```

1. **Planner** decides *which tools* to call this iteration (structured output: `list[ToolCall]`).
2. **Tool executor** runs them concurrently, captures results (and errors) into `gathered_data`.
3. **Reflector** decides *is this enough data to answer?* Hard cap at 3 iterations.
4. **Recommender** reads everything gathered, produces a structured `ScoutReport`.

Three LLM calls minimum (planner + reflector + recommender), max nine (3× planner + 3× reflector + 1× recommender), typical five (2 iterations).

---

## What each file does

### Code

| File | Purpose | Key exports |
|------|---------|-------------|
| [`src/fpl_agent/models/state.py`](../src/fpl_agent/models/state.py) | State shape + reducers | `AgentState`, `ToolCall`, `merge_dicts`, `initial_state` |
| [`src/fpl_agent/models/responses.py`](../src/fpl_agent/models/responses.py) | Pydantic schemas for LLM outputs & API envelope | `ScoutReport`, `PlayerAnalysis`, `ComparisonResult`, `ReflectionResult`, `AgentResponse` |
| [`src/fpl_agent/tools/player_tools.py`](../src/fpl_agent/tools/player_tools.py) | The 6 async tools + factory + error type | `make_tools(neon)`, `ToolError`, `ToolFn` |
| [`src/fpl_agent/graph/config.py`](../src/fpl_agent/graph/config.py) | Model IDs, iteration cap, timeouts | `PLANNER_MODEL`, `RECOMMENDER_MODEL`, `MAX_ITERATIONS`, `TOOL_TIMEOUT_SECONDS` |
| [`src/fpl_agent/graph/nodes.py`](../src/fpl_agent/graph/nodes.py) | The 4 node functions + conditional edge router | `planner_node`, `tool_executor_node`, `reflector_node`, `recommender_node`, `route_after_reflector` |
| [`src/fpl_agent/graph/builder.py`](../src/fpl_agent/graph/builder.py) | Wires nodes into a `StateGraph` and compiles it | `build_agent_graph(client, tools)` |
| [`src/fpl_agent/handlers/api_handler.py`](../src/fpl_agent/handlers/api_handler.py) | Lambda entry point (currently stub — real wiring in PR #92) | `lambda_handler` |

### Prompts

| File | Used by | Substitutions |
|------|---------|---------------|
| [`src/fpl_agent/graph/prompts/v1/planner.md`](../src/fpl_agent/graph/prompts/v1/planner.md) | planner_node | `{question}`, `{gathered_data_json}` |
| [`src/fpl_agent/graph/prompts/v1/reflector.md`](../src/fpl_agent/graph/prompts/v1/reflector.md) | reflector_node | `{question}`, `{gathered_data_json}`, `{iteration_count}`, `{max_iterations}` |
| [`src/fpl_agent/graph/prompts/v1/recommender.md`](../src/fpl_agent/graph/prompts/v1/recommender.md) | recommender_node | `{question}`, `{user_squad_json}`, `{gathered_data_json}` |

Bump to `v2/` when changing a prompt meaningfully — keep `v1/` for trace comparison.

### Tests

| File | What it covers |
|------|----------------|
| [`tests/test_tools.py`](../tests/test_tools.py) | Each of the 6 tools + `make_tools` factory (12 tests) |
| [`tests/test_graph_nodes.py`](../tests/test_graph_nodes.py) | Each node in isolation + `route_after_reflector` (17 tests) |
| [`tests/test_graph_builder.py`](../tests/test_graph_builder.py) | Graph compiles, end-to-end invoke, loop exercises (4 tests) |

---

## Terminology

### LangGraph

| Term | Definition |
|------|------------|
| **StateGraph** | The graph builder. Add nodes, add edges, `.compile()`. Analogy: AWS Step Functions ASL in Python. |
| **State** | A `TypedDict` passed to every node. Nodes return partial dicts; LangGraph merges them into the running state. |
| **Node** | A function `(state) -> dict`. Ours are all `async def`. |
| **Edge** | Static transition: after node A, run node B. `graph.add_edge("a", "b")`. |
| **Conditional edge** | A routing function `(state) -> str` whose return value is looked up in a mapping to pick the next node. Our only one is `route_after_reflector`. |
| **START / END** | Sentinel nodes marking graph entry/exit. `graph.add_edge(START, "planner")` says "begin here." |
| **Reducer** | A function `(old_value, new_value) -> combined_value` that decides how a node's partial update merges into state. Declared via `Annotated[Type, reducer_fn]` in the state TypedDict. Ours: default overwrite, `operator.add` for lists, `merge_dicts` for dicts. |
| **`.ainvoke(state)`** | Run the graph once, return the final state. |
| **`.astream(state)`** | Yield intermediate states as they're produced — used for SSE streaming in PR #92. |
| **CompiledStateGraph** | The return type of `.compile()`. What you call `.ainvoke()` on. |

### Anthropic / tool-use

| Term | Definition |
|------|------------|
| **Tool-use** | Anthropic's mechanism for structured output. We define a *fake* tool whose `input_schema` is a Pydantic-derived JSON Schema, force the model to "call" it via `tool_choice`, and read the tool arguments back as a dict. Server-side decoder constrains token sampling to valid JSON matching the schema — malformed JSON is physically impossible. |
| **`tool_choice`** | Argument to `messages.create` that forces the model to call a specific tool. `{"type": "tool", "name": "record_plan"}` makes the model emit a `record_plan` call instead of prose. |
| **`input_schema`** | JSON Schema describing the tool's arguments. We derive ours from Pydantic models (`ScoutReport.model_json_schema()`, `TypeAdapter(list[ToolCall]).json_schema()`). |
| **`content` blocks** | Anthropic responses are a list of content blocks — some text, some `tool_use`. Even when `tool_choice` forces one tool, you still scan the list. That's what `_extract_tool_input` does. |
| **Prompt caching** | Anthropic server-side cache for byte-identical prefixes (the tool schema, the system prompt). 90% discount for 5min TTL. Effectively free once warm. |

### Agent-specific

| Term | Definition |
|------|------------|
| **`AgentState`** | The TypedDict flowing through the graph. Fields: `question`, `user_squad`, `plan`, `gathered_data`, `tool_calls_made`, `iteration_count`, `should_continue`, `final_response`, `error`. |
| **`ToolCall`** | Pydantic model: `name: Literal[<6 tool names>]`, `args: dict`. The planner produces a `list[ToolCall]`; the executor dispatches them. |
| **Tool registry** | The dict `{"query_player": <callable>, ...}` returned by `make_tools(neon)`. The executor indexes into it by `ToolCall.name`. |
| **Factory closure** | Pattern used for tools — `make_tools(neon)` returns 6 async functions, each with the `NeonClient` captured via closure. Lets tools access the DB without having the DB in state or as a global. |
| **Partial injection** | Pattern used for nodes — `functools.partial(planner_node, client=client)` pre-binds the Anthropic client, letting LangGraph see a one-arg `(state) -> dict` callable. |
| **Hard-cap short-circuit** | The reflector skips the LLM call when `iteration_count + 1 >= MAX_ITERATIONS` — the answer is forced regardless, so calling Haiku would be wasted. |
| **`state["error"]` drain** | Any node that hits an unrecoverable failure sets `state["error"]`. `route_after_reflector` checks it and routes to `done`. Every failure path converges on the same exit. |
| **`@observe(name=...)`** | Langfuse decorator. Creates a trace span for each call. No-op until Langfuse is initialised (PR #93) — decorators are already in place so #93 is a pure infra change. |
| **`ToolError`** | Exception raised by a tool when it fails in a known way ("no player found"). Executor catches and records in `gathered_data` so siblings continue. |

### Cost controls

| Term | Definition |
|------|------------|
| **`MAX_ITERATIONS = 3`** | Hard cap on the reflector loop. Bounds worst-case LLM calls at 9 per request. |
| **`TOOL_TIMEOUT_SECONDS = 10`** | Per-tool timeout. Slow Neon query or Lambda invoke can't consume more than 10s. |
| **API Gateway throttling** | 10 RPS, 20 burst. Configured in Terraform. First line of defence. |
| **DynamoDB kill-switch** | `fpl-agent-usage-dev` table, monthly `$5` cap. Enforced at request entry in PR #92/#93. |

---

## The five conventions that repeat everywhere

1. **State-only data flow.** Nothing moves between nodes except through `state`. Dependencies come in via `functools.partial` at graph build time.
2. **Tool-use for structured output.** Every LLM call uses `tools=[...] + tool_choice={...}` with a Pydantic-derived `input_schema`. No prompt ever carries the schema.
3. **Pydantic = source of truth.** Change a field on `ScoutReport`, and both the LLM's output constraints and the validation downstream update automatically.
4. **Errors drain to `state["error"]`.** Every failure mode converges there. The graph always completes; there are no Python exceptions escaping through LangGraph.
5. **`@observe()` everywhere that costs money.** Every LLM-calling node and every tool is decorated. Langfuse init in #93 lights all of them up.
