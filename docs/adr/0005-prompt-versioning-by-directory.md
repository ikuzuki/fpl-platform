# ADR-0005: Prompt Versioning by Directory

## Status
Accepted

## Context
LLM prompts are a critical part of the enrichment pipeline. Prompt changes can silently alter output quality, break downstream validation, or shift cost profiles. We needed a strategy for versioning prompts that supports iteration without risking production stability.

## Decision
Store prompt templates as plain text files in versioned directories: `services/enrich/src/fpl_enrich/prompts/v{N}/`. Each enricher loads its prompt at runtime via `load_prompt(enricher_name, version)`.

```
prompts/
  v1/
    player_summary.txt
    injury_signal.txt
    sentiment.txt
    fixture_outlook.txt
  v2/
    ...
```

## Rules
- Never edit a published version directory — create a new `v{N+1}` instead
- The `prompt_version` parameter is passed through the Lambda event, defaulting to `"v1"`
- Prompts are plain text with `{batch_size}` and `{batch_items}` placeholders — no Jinja or complex templating
- Each prompt specifies its expected JSON output schema inline

## Consequences
**Easier:**
- A/B testing: run v1 and v2 side by side by passing different `prompt_version` values
- Rollback: revert to previous version without code changes
- Auditability: git history shows exactly what changed between versions
- Langfuse traces include `prompt_version` metadata for quality comparison
- No code changes needed to iterate on prompts — just add a new directory

**Harder:**
- No compile-time validation that prompt placeholders match code expectations
- Directory proliferation over time (mitigated: old versions can be archived)
- Prompt and code must stay in sync — a new output field requires both a prompt change and a validator update
