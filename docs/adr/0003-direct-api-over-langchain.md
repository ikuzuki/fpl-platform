# ADR-0003: Direct Anthropic API over LangChain

## Status
Accepted

## Date
2026-04-04

## Context
The enrichment pipeline makes structured LLM calls (player summaries, injury signals, sentiment, fixture outlook). Each call sends a batch of items and expects a JSON array back. We needed to decide whether to use a framework or call the API directly.

## Options Considered

### 1. Direct `anthropic` Python SDK (chosen)
Call `client.messages.create()` directly. Build our own batching (`FPLEnricher` ABC), validation (Pydantic), and retry logic.

### 2. LangChain (rejected)
Use LangChain's chains, output parsers, and retry decorators. Provides `ChatAnthropic`, `PydanticOutputParser`, and `RunnableWithRetry` out of the box.

**Rejected because:**
- Our enrichment calls are simple: system prompt + user message → JSON array. LangChain's chain abstraction adds indirection without simplifying this pattern.
- LangChain wraps prompts with its own formatting — we need exact control over prompt content for versioning (see ADR-0005) and cost tracking
- LangChain pulls ~20 transitive dependencies, increasing Lambda container size and cold start time
- Debugging LangChain's chain-of-responsibility stack is harder than debugging a direct API call
- Token counting is straightforward from `response.usage` — LangChain's callback system is heavier machinery for the same result

### 3. LiteLLM (rejected)
Lightweight proxy that normalises different LLM provider APIs behind one interface.

**Rejected because:** We only use Anthropic. Multi-provider abstraction adds a layer with no current benefit. LiteLLM also proxies requests, adding latency and a failure mode to every LLM call. If we added a second provider (e.g. OpenAI for embeddings or cheaper classification), LiteLLM would be worth revisiting — but at that point we'd evaluate whether a thin adapter in `fpl_lib` is simpler than pulling in a proxy dependency.

## Decision
Use the `anthropic` Python SDK directly for all enrichment pipeline LLM calls.

## Consequences
**Easier:**
- Full control over prompt formatting, batching, and retry logic
- Simpler dependency tree — `anthropic` is one package
- Token counting and cost tracking are straightforward from `response.usage`
- Easier to debug — no hidden prompt wrapping or chain-of-responsibility indirection
- Smaller Lambda container images (fewer deps = faster cold starts)

**Harder:**
- We built our own batching (`FPLEnricher` base class) and retry logic (~100 lines of code)
- If we add new LLM providers, we'd need to write our own abstraction
- No built-in chain composition (not needed for batch enrichment)

## Related
- The LangGraph agent (`services/agent/`) uses LangGraph for agentic orchestration — a different pattern where the framework earns its place. LangGraph provides state machines, tool calling, and human-in-the-loop, which would be significant to rebuild from scratch. The distinction: batch enrichment is a simple request-response pattern; agentic recommendations need stateful multi-step reasoning.
