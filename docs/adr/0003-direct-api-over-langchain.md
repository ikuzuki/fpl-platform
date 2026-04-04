# ADR-0003: Direct Anthropic API over LangChain

## Status
Accepted

## Context
The enrichment pipeline makes structured LLM calls (player summaries, injury signals, sentiment, fixture outlook). LangChain is the most popular Python framework for LLM orchestration and offers chains, output parsers, and retry logic out of the box. We needed to decide whether to use it or call the Anthropic API directly.

## Decision
Use the `anthropic` Python SDK directly for all LLM calls. No LangChain anywhere in the pipeline.

## Consequences
**Easier:**
- Full control over prompt formatting, batching, and retry logic — no fighting framework abstractions
- Simpler dependency tree — `anthropic` is one package vs LangChain's 20+ transitive dependencies
- Token counting and cost tracking are straightforward from `response.usage`
- Easier to debug — no hidden prompt wrapping or chain-of-responsibility indirection
- Structured JSON output validated with Pydantic directly, not LangChain's output parsers
- Smaller Lambda container images (fewer deps = faster cold starts)

**Harder:**
- We built our own batching (`FPLEnricher` base class) and retry logic instead of using LangChain's built-in
- If we add new LLM providers, we'd need to write our own abstraction (LangChain provides this)
- No built-in support for chains or multi-step reasoning (not needed for our enrichment use case)

## Notes
The LangGraph agent (`services/agent/`) is a separate concern — it uses LangGraph for the agentic recommendation graph, which is a different pattern from the batch enrichment pipeline.
