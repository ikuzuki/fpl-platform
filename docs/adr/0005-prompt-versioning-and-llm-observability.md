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

**Implementation references:**
- **Session and metadata setup** — each Lambda handler wraps execution in `propagate_attributes` with a `{season}-gw{gameweek}` session ID. See `services/enrich/src/fpl_enrich/handlers/single_enricher.py`.
- **Batch-level metadata and scoring** — the `@observe(name="enricher_batch_call")` decorator on `_call_llm` records enricher name, prompt version, model, and batch size per span, then scores output count validity. See `services/enrich/src/fpl_enrich/enrichers/base.py`.
- **Trace-level quality scoring** — after all batches complete, the base enricher scores the trace with `validation_pass_rate`. Same file as above.

Keys stored in SSM Parameter Store as SecureString parameters (`/fpl-platform/dev/langfuse-public-key`, `/fpl-platform/dev/langfuse-secret-key`). See ADR-0011 for the choice of Parameter Store over Secrets Manager.

> **Note:** This project uses Langfuse SDK v4 (`propagate_attributes`, `Langfuse()` instance methods). See the code references above for current usage patterns.

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
- Two parameters to manage in SSM Parameter Store
- If Langfuse's cloud service is down, tracing silently fails (by design — doesn't block the pipeline)
- Langfuse SDK has breaking API changes between major versions (v2→v3→v4); code examples in this ADR target v4 (`propagate_attributes`, `Langfuse()` instance methods)

## Revision — 2026-04-20: Langfuse SDK v4 on Lambda tuning

Langfuse SDK v4 is an OpenTelemetry rewrite. On Lambda, uploads to `cloud.langfuse.com` can stack to a 60s hang on the response thread. There are **two separate blocking surfaces** and both matter:

1. **The OTLP HTTP exporter's retry loop.** `OTLPSpanExporter.export()` retries up to 6 times with exponential backoff (1s → 2s → 4s → 8s → 16s → 32s ≈ 63s total) on connect errors. Bounded only by the exporter's own `timeout` argument — OTel's standard `OTEL_BSP_EXPORT_TIMEOUT` is wired but [ignored by design](https://github.com/open-telemetry/opentelemetry-python) (the HTTP exporter has the explicit comment `# Not used. No way currently to pass timeout to export.`). Langfuse 4.x passes its own `LANGFUSE_TIMEOUT` env var (seconds, default 5) straight into the exporter constructor; that's the only knob that caps the retry deadline.
2. **`resource_manager.flush()`'s queue joins.** `Langfuse().flush()` calls `self.tracer_provider.force_flush()` (OTel default 30 s, and the passed `export_timeout_millis` is silently ignored), then `_score_ingestion_queue.join()` and `_media_upload_queue.join()` **with no timeout at all**. If we emit any scores (we do — `_emit_quality_scores` in `api.py`) and the Langfuse endpoint is slow, the handler thread blocks forever on `.join()`.

### What we tried first and why it failed

The first correction set `OTEL_EXPORTER_OTLP_TIMEOUT=3000` and `OTEL_BSP_EXPORT_TIMEOUT=5000` — both ignored by Langfuse's own processor, so `/team` hung 60s after redeploy. We also set `LANGFUSE_FLUSH_AT=1` thinking it would reduce queue depth; it actually *made things worse* because `BatchSpanProcessor.on_end()` triggers synchronous export on the handler thread whenever `queue_size >= max_export_batch_size`. With `max=1`, every span paid the full retry loop inline.

### What actually works (chosen)

- **`LANGFUSE_TIMEOUT=2`** — seconds, caps the OTLP exporter's retry loop (per-POST socket timeout AND overall deadline). A dead endpoint now costs ~2s, not 60s.
- **`LANGFUSE_FLUSH_INTERVAL=1`** — short background flush interval so the batch processor drains on its own thread between requests. Small tail of events may be stranded when the Lambda freezes mid-batch; acceptable at our scale.
- **Do NOT set `LANGFUSE_FLUSH_AT=1`** (see failure mode above — leave the SDK default of 15).
- **Remove all explicit `langfuse_flush()` calls from request handlers.** The `_score_ingestion_queue.join()` path in `resource_manager.flush()` is unbounded and the background processor covers the common case anyway.
- **Keep `LANGFUSE_TRACING_ENABLED` as the kill-switch** — a single `aws lambda update-function-configuration` flip disables tracing in seconds.

### Source citations

- `langfuse/_client/client.py:269` — `timeout = timeout or int(os.environ.get(LANGFUSE_TIMEOUT, 5))`
- `langfuse/_client/span_processor.py:108-112` — `OTLPSpanExporter(timeout=timeout)`
- `langfuse/_client/resource_manager.py:430` — `flush()` call chain; `_score_ingestion_queue.join()` without timeout
- `opentelemetry/exporter/otlp/proto/http/trace_exporter/__init__.py:174-224` — retry loop with `_MAX_RETRYS = 6`, deadline = `time() + self._timeout`

### ADOT stays deferred

[AWS Distro for OpenTelemetry](https://aws-otel.github.io/) as a Lambda Extension runs a local OTEL collector as an external extension process — the app exports to `localhost:4318` and the extension flushes during the post-invocation lifecycle (before freeze), so user latency is untouched. It's the production answer at higher RPS and sidesteps every SDK-level blocking surface above. Deferred for us because (a) the SDK-level fix above is what Langfuse maintainers recommend for low-traffic Lambda, (b) ADOT on container-image Lambdas (Layers don't work) requires Dockerfile plumbing, and (c) once `LANGFUSE_TIMEOUT=2` is in place, worst case is a ~2s tax which is invisible at 1–2 rpm. Revisit if the Langfuse UI shows visible trace drop or if cold-start latency becomes user-facing.

Langfuse PR [#1618](https://github.com/langfuse/langfuse-python/pull/1618) (v4.1+) adds a `span_exporter=` kwarg to `Langfuse()` letting apps inject a custom fire-and-forget or ADOT-routing exporter — cleaner escape hatch than overriding env vars. Worth revisiting after Langfuse 4.1 ships.
