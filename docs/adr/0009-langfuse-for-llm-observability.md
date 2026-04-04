# ADR-0009: Langfuse for LLM Observability

## Status
Accepted

## Date
2026-04-04

## Context
The enrichment pipeline makes ~1,200 LLM API calls per gameweek across four enrichers. We need observability to track cost, latency, output quality, and prompt version performance. Without it, degraded output quality or cost spikes would go unnoticed until they hit the dashboard or the AWS bill.

## Options Considered

### 1. Custom logging to CloudWatch (rejected)
Log token counts, latency, and cost to CloudWatch Metrics. Build dashboards in CloudWatch.

**Rejected because:** CloudWatch is good for infrastructure metrics but poor for LLM-specific workflows. No built-in support for prompt versioning, trace trees, or output quality scoring. Building a custom LLM dashboard in CloudWatch would duplicate what observability tools provide out of the box.

### 2. LangSmith (rejected)
LangChain's native observability platform. Tight integration with LangChain, traces, datasets, evaluation.

**Rejected because:** Tightly coupled to LangChain — we don't use LangChain (see ADR-0003). While LangSmith can work without LangChain, its SDK and documentation assume LangChain patterns. Also, LangSmith's pricing is opaque for self-hosted/free tier usage.

### 3. Helicone (rejected)
Proxy-based LLM observability — sits between your app and the LLM API, captures all traffic.

**Rejected because:** Proxy architecture adds latency to every LLM call and introduces a single point of failure. Our batch pipeline can tolerate some observability delay — we don't need real-time interception.

### 4. Langfuse (chosen)
Open-source LLM observability with a Python decorator-based SDK. Supports traces, spans, scoring, prompt management, and cost tracking.

## Decision
Use Langfuse for all LLM observability. Integration via the `@observe` decorator on enricher methods and the Lambda handler.

```python
@observe(name="enricher_batch_call")
def _call_llm(self, batch: list[dict]) -> list[dict]:
    langfuse_context.update_current_observation(
        metadata={"enricher": self.__class__.__name__, "prompt_version": self.prompt_version}
    )
    # ... LLM call ...
    langfuse_context.score_current_observation(
        name="output_count_valid",
        value=1.0 if len(results) == len(batch) else 0.0,
    )
```

Keys stored in Secrets Manager (`/fpl-platform/dev/langfuse-public-key`, `/fpl-platform/dev/langfuse-secret-key`).

## What we trace
- **Per batch call:** enricher name, batch size, prompt version, input/output token counts, latency, model
- **Per gameweek run:** session ID (`{season}-gw{gameweek}`), total calls, total cost, success/failure counts
- **Quality scores:** output count validation (did the LLM return the right number of items?)

## Consequences
**Easier:**
- `@observe` decorator is minimally invasive — one line per method, no restructuring needed
- Prompt version metadata enables A/B comparison between v1 and v2 prompts in the Langfuse dashboard
- Cost attribution per enricher type — instantly see that fixture outlook is 92% of spend (see ADR-0004)
- Open-source with generous free tier — no vendor lock-in, can self-host if needed
- Session-based grouping (`season-gw{N}`) makes it easy to investigate a specific gameweek's run

**Harder:**
- Adds `langfuse` as a dependency with its own transitive deps (OpenTelemetry, protobuf, etc.)
- Two more secrets to manage in Secrets Manager
- If Langfuse's cloud service is down, tracing silently fails (by design — doesn't block the pipeline), but you lose observability for that run
- Decorator-based approach means tracing is tied to the code structure — moving logic between methods requires moving decorators
