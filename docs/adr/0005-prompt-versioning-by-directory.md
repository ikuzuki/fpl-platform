# ADR-0005: Prompt Versioning by Directory

## Status
Accepted

## Date
2026-04-04

## Context
LLM prompts are a critical part of the enrichment pipeline. Prompt changes can silently alter output quality, break downstream validation, or shift cost profiles. We needed a strategy for versioning prompts that supports iteration without risking production stability.

## Options Considered

### 1. Inline prompts in Python code (rejected)
Embed prompt strings directly in enricher classes.

**Rejected because:** Prompt changes become code changes, requiring full CI/test cycles. Makes it hard to compare versions side by side. Mixes concerns — the enricher logic shouldn't change when you're only tweaking wording.

### 2. Database-stored prompts (rejected)
Store prompts in DynamoDB or S3 with version metadata, loaded at runtime.

**Rejected because:** Adds infrastructure dependency for something that changes infrequently. Harder to review in PRs. Version history lives in a database rather than git, losing diff/blame capabilities.

### 3. Git-tracked directory-based versioning (chosen)
Plain text files in `prompts/v{N}/` directories, loaded by `load_prompt(enricher_name, version)`.

## Decision
Store prompt templates as plain text files in versioned directories: `services/enrich/src/fpl_enrich/prompts/v{N}/`.

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

## Deployment coordination
The `prompt_version` default is hardcoded in the Lambda handler (`"v1"`). To roll out a new version:
1. Merge the new `v2/` directory
2. Update the Step Functions state machine input to pass `prompt_version: "v2"`
3. Or update the handler default — this is a code change and goes through CI

**Risk:** If someone deploys new prompt files but forgets to update the version parameter, the old version continues running. This is acceptable because:
- Prompts are additive (v1 still works after v2 is deployed)
- Langfuse traces include `prompt_version` metadata, so version drift is visible in the dashboard
- The Step Functions input is the single source of truth for "what version is running"

## Consequences
**Easier:**
- A/B testing: run v1 and v2 side by side by passing different `prompt_version` values
- Rollback: revert to previous version by changing one parameter, no code deploy needed
- Auditability: git history shows exactly what changed between versions, with PR review
- Langfuse traces include `prompt_version` metadata for quality comparison

**Harder:**
- No compile-time validation that prompt placeholders match code expectations
- Deployment coordination requires updating the version parameter (see above)
- Prompt and code must stay in sync — a new output field requires both a prompt change and a validator update in the same PR
