# ADR-0005: Prompt Versioning and LLM Observability

## Status
Accepted

## Date
2026-04-04

## Context
The enrichment pipeline makes ~150 LLM API calls per gameweek across four enrichers. Prompt changes can silently alter output quality, break downstream validation, or shift cost profiles. We needed both a versioning strategy for prompts and an observability layer to track cost, latency, and output quality — without these, degraded outputs or cost spikes would go unnoticed until they hit the dashboard or the AWS bill.

## Options Considered

### Prompt versioning

**1. Inline prompts in Python code (rejected)**
Embed prompt strings directly in enricher classes.

Rejected because: Prompt changes become code changes requiring full CI/test cycles. Makes it hard to compare versions side by side. Mixes concerns — the enricher logic shouldn't change when you're only tweaking wording.

**2. Database-stored prompts (rejected)**
Store prompts in DynamoDB or S3 with version metadata, loaded at runtime.

Rejected because: Adds infrastructure dependency for something that changes infrequently. Version history lives in a database rather than git, losing diff/blame capabilities.

**3. Git-tracked directory-based versioning (chosen)**
Plain text files in `prompts/v{N}/` directories, loaded by `load_prompt(enricher_name, version)`.

### Observability

**1. Custom logging to CloudWatch (rejected)**
Log token counts, latency, and cost to CloudWatch Metrics.

Rejected because: CloudWatch is good for infrastructure metrics but poor for LLM-specific workflows. No built-in support for prompt versioning, trace trees, or output quality scoring.

**2. LangSmith (rejected)**
LangChain's native observability platform.

Rejected because: Tightly coupled to LangChain — we don't use LangChain (see ADR-0003). Its SDK and documentation assume LangChain patterns.

**3. Helicone (rejected)**
Proxy-based LLM observability — sits between app and LLM API.

Rejected because: Proxy architecture adds latency to every LLM call and introduces a single point of failure.

**4. Langfuse (chosen)**
Open-source LLM observability with a Python decorator-based SDK. Supports traces, spans, scoring, prompt management, and cost tracking.

## Decision

### Prompt versioning
Store prompt templates as plain text files in versioned directories:

```
services/enrich/src/fpl_enrich/prompts/
  v1/
    player_summary.txt
    injury_signal.txt
    sentiment.txt
    fixture_outlook.txt
  v2/
    ...
```

**Rules:**
- Never edit a published version directory — create `v{N+1}` instead
- The `prompt_version` parameter is passed through the Lambda event, defaulting to `"v1"`
- Prompts are plain text with `{batch_size}` and `{batch_items}` placeholders — no Jinja or complex templating
- Each prompt specifies its expected JSON output schema inline

**Deployment:** The `prompt_version` default is in the Lambda handler. To roll out a new version, either update the Step Functions state machine input or the handler default. Prompts are additive — v1 still works after v2 is deployed, so a forgotten parameter update is safe (just stale).

### LLM observability with Langfuse
Integration via the `@observe` decorator on enricher methods and Lambda handlers. Session IDs and trace-level metadata are set via `propagate_attributes` in each Lambda entry point, which propagates to all child spans created within that context.

**Session and metadata setup** (Lambda handler level):
```python
from langfuse import observe, propagate_attributes

def lambda_handler(event, context):
    _init_langfuse()
    season = event.get("season", "unknown")
    gameweek = event.get("gameweek", 0)
    with propagate_attributes(
        session_id=f"{season}-gw{gameweek}",
        metadata={"enricher": "player_summary", "prompt_version": event.get("prompt_version", "v1")},
    ):
        return RunHandler(main_func=main, ...).lambda_executor(lambda_event=event)
```

**Batch-level metadata and scoring** (base enricher):
```python
from langfuse import Langfuse, observe

@observe(name="enricher_batch_call")
async def _call_llm(self, batch: list[dict]) -> list[dict]:
    langfuse = Langfuse()
    langfuse.update_current_span(
        metadata={
            "enricher": self.__class__.__name__,
            "prompt_version": self.prompt_version,
            "model": self.MODEL,
            "batch_size": len(batch),
        },
    )
    # ... LLM call and parsing ...
    langfuse.score_current_span(
        name="output_count_valid",
        value=1.0 if len(parsed) == len(batch) else 0.0,
        comment=f"expected={len(batch)}, got={len(parsed)}",
    )
```

**Trace-level quality scoring** (after all batches complete):
```python
Langfuse().score_current_trace(
    name="validation_pass_rate",
    value=round(self.valid_count / total, 4),
    comment=f"{self.__class__.__name__}: {self.valid_count}/{total} passed",
)
```

Keys stored in Secrets Manager (`/fpl-platform/dev/langfuse-public-key`, `/fpl-platform/dev/langfuse-secret-key`).

> **Note:** This project uses Langfuse SDK v4, which replaced the v2/v3 `langfuse_context` / `langfuse.decorators` API with `Langfuse()` instance methods and the `propagate_attributes` context manager. If upgrading Langfuse, check the migration guide.

**What we trace:**
- **Per batch call:** enricher name, batch size, prompt version, model, input/output token counts, latency (all via observation metadata)
- **Per gameweek run:** session ID (`{season}-gw{gameweek}`) groups all traces for one pipeline run; enricher name and prompt version propagated to all child spans
- **Quality scores:**
  - `output_count_valid` (per batch, numeric 0.0–1.0): did the LLM return the expected number of items?
  - `validation_pass_rate` (per enricher trace, numeric 0.0–1.0): what fraction of LLM outputs passed Pydantic model validation?

### How these work together
Prompt version metadata flows into every Langfuse trace, enabling A/B comparison between prompt versions with concrete metrics (cost, latency, output quality scores). When we deploy v2, the Langfuse dashboard shows side-by-side performance against v1 without any custom analytics work. Cost attribution per enricher type is immediate — we can see that fixture outlook is ~94% of spend (see ADR-0004) and whether a prompt change shifts that.

## Consequences
**Easier:**
- A/B testing: run v1 and v2 side by side by passing different `prompt_version` values
- Rollback: revert to previous version by changing one parameter, no code deploy needed
- `@observe` decorator is minimally invasive — one line per method
- Cost attribution per enricher and prompt version is automatic
- Session-based grouping (`season-gw{N}`) makes investigating a specific gameweek's run straightforward

**Harder:**
- No compile-time validation that prompt placeholders match code expectations
- Prompt and code must stay in sync — a new output field requires both a prompt change and a validator update
- Adds `langfuse` as a dependency (OpenTelemetry, protobuf transitive deps)
- Two secrets to manage in Secrets Manager
- If Langfuse's cloud service is down, tracing silently fails (by design — doesn't block the pipeline)
- Langfuse SDK has breaking API changes between major versions (v2→v3→v4); code examples in this ADR target v4 (`propagate_attributes`, `Langfuse()` instance methods)
