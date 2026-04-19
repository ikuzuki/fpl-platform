# Runbook

Operational procedures for the FPL platform.

## Running the Pipeline Manually

```bash
export AWS_PROFILE=fpl-dev
python -m fpl_data.handlers.fpl_api_collector --season 2025-26 --gameweek 15
```

## Terraform Operations

```bash
cd infrastructure/environments/dev
terraform init
terraform plan
terraform apply
```

## Agent Observability (Langfuse)

Every scout-agent request becomes one root trace in Langfuse, grouped by the
`X-Session-Id` header (defaults to `"anon"` when absent). Each trace contains
one generation span per LLM node (`node.planner`, `node.reflector`,
`node.recommender`) and one tool span per invocation (`tool.query_player`, …).

### Where to look
- **Traces**: filter by `tags = agent` and `environment = dev|prod`.
- **Session view**: search `session_id` to see every chat turn from one
  browser session in order.
- **Cost/latency per node**: generation spans carry `model` and
  `usage_details={input, output}` so Langfuse computes cost against its
  published rate table. Use the Generations view, not Spans.

### Quality scores (attached to every trace)
- `output_valid` — 1.0 when the recommender produced a `ScoutReport` and no
  `state["error"]` was set. Drop ≠ 1.0 means the agent failed to answer.
- `iterations_used` — raw count (1–3). Rising average suggests the planner
  is mis-picking tools on first try.
- `tool_success_rate` — fraction of plan items that returned data vs an
  `{"error": ...}` dict. Low values usually mean a Neon schema drift.

### Is tracing actually working?
The Lambda logs `"Langfuse init failed, tracing disabled: …"` at cold-start
if Secrets Manager couldn't be reached — the service still serves traffic,
just without spans. Fix by confirming the two secrets are populated:

```bash
aws secretsmanager get-secret-value --secret-id /fpl-platform/dev/langfuse-public-key
aws secretsmanager get-secret-value --secret-id /fpl-platform/dev/langfuse-secret-key
```

If both have `SecretString` values and traces still don't appear, check the
Lambda execution role has `secretsmanager:GetSecretValue` on
`/fpl-platform/*` (covered by the shared `lambda-role` module).

## Loading a User's FPL Squad

`GET /team?team_id={id}&gameweek={n}` on the agent service returns the
enriched `UserSquad` shape — picks joined against Neon for `web_name`,
`team_name`, `price`. Money fields are in pounds millions (£3.2m), not
the FPL API's tenths-of-millions wire format.

```bash
# Smoke test against dev (replace with the live CloudFront domain)
curl -s "https://{cloudfront-domain}/api/agent/team?team_id=5767400&gameweek=33" | jq .
```

Status code map:
- **200** — enriched squad
- **404** — `team_id` doesn't exist on FPL (or has no picks for that GW)
- **502** — upstream failure: team-fetcher Lambda erroring, FPL rate-limiting, or Neon down
- **503** — `TEAM_FETCHER_FUNCTION_NAME` env var missing (Lambda not wired in)

If a chat request includes the squad in the request body, the agent
seeds it onto `state["user_squad"]` so both the planner and recommender
prompts see it as context. Squad loading is HTTP-layer only — the agent
graph has no tool that fetches a squad. Langfuse traces for those
requests carry `team_id` + `gameweek` metadata so you can filter by
manager.

### When `/team` returns 502 in production

1. Check the team-fetcher Lambda directly:
   ```bash
   aws --profile fpl-prod lambda invoke --function-name fpl-prod-team-fetcher \
     --payload '{"team_id":5767400,"gameweek":33}' /tmp/out.json && cat /tmp/out.json
   ```
2. If that fails with `FPLAccessError`, FPL is rate-limiting via Cloudflare
   — the Lambda already retries 403s once after 2s. Wait, then retry.
3. If it fails with a Neon error, check Neon status and the
   `NEON_DATABASE_URL` secret hasn't rotated.

## Common Issues

*To be populated as issues are encountered.*
