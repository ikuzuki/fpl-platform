# ADR-0010: Agent HTTP Transport — Lambda Function URL with Response Streaming

## Status
Accepted

## Date
2026-04-19

## Context
ADR-0009 spec'd API Gateway v2 HTTP API as the agent's HTTP surface. Implementation (PR #117) hit two blockers that make this transport unsuitable for the agent's `/chat` SSE endpoint:

- **29-second integration timeout**, non-negotiable on HTTP APIs. Agent worst-case runtime is 3 iterations × (planner + up to 5 parallel tools + reflector) + recommender ≈ 45 seconds.
- **Response buffering**. API Gateway v2 buffers the entire response before sending, which silently defeats SSE — the browser sees one delayed payload instead of incremental `step` events.

Moving to a transport that supports true streaming and a longer runtime is a prerequisite for the PR #94 frontend chat page — without it, the streaming UX is theatre.

## Options Considered

### 1. API Gateway v2 HTTP API + Mangum (status quo, rejected)
What ADR-0009 originally spec'd. Rejected on both counts above.

### 2. API Gateway WebSocket API (rejected)
Different product from HTTP API. 2h connection timeout, supports streaming natively.

Rejected because: WebSocket protocol changes the frontend from a standard SSE reader to a connection-managing client (ping/pong, reconnect, ordering). The additional backend state (connection IDs in DynamoDB, route keys, `@connections` post-back) is also material. For a unidirectional stream of server → client progress events, SSE is the simpler protocol and is natively supported by modern browser `EventSource` and React hooks.

### 3. Async job pattern — SQS + worker Lambda + polling (rejected)
Submit returns 202 immediately; worker Lambda runs the agent off a queue; client polls or subscribes for results.

Rejected because: unbounded runtime and durability across disconnects are not requirements — agent runs are bounded (≤60s) and users are actively waiting. The extra SQS queue, DynamoDB job table, and separate polling/subscription endpoint add infrastructure without buying anything for the demo scope. Reserved for future features that genuinely need fire-and-forget (e.g. "email me my season review").

### 4. ECS Fargate + ALB (rejected)
Production-grade answer for streaming AI endpoints. Long-lived container, no cold starts, no runtime cliff.

Rejected because: loses scale-to-zero (the whole platform's posture per ADR-0009's serverless-first framing), adds ~$22/month of ALB + Fargate baseline cost, and is more infrastructure than a portfolio demo justifies. The right answer if this grows into a real product.

### 5. Lambda Function URL + AWS Lambda Web Adapter (chosen)
Function URL with `invoke_mode = "RESPONSE_STREAM"` supports true streaming from Lambda. AWS Lambda Web Adapter (LWA) is a sidecar extension that runs an unmodified FastAPI app via uvicorn inside the Lambda container, translating Function URL streaming events into standard HTTP. AWS's documented pattern for serverless streaming endpoints.

## Decision
Agent HTTP surface moves from API Gateway v2 to Lambda Function URL + LWA.

- **Transport**: `aws_lambda_function_url` with `invoke_mode = "RESPONSE_STREAM"` and `authorization_type = "NONE"` (CloudFront is the front door).
- **Runtime**: Dockerfile copies the LWA extension from `public.ecr.aws/awsguru/aws-lambda-adapter:0.9.0` and runs `uvicorn fpl_agent.api:app` as the container CMD. `AWS_LWA_INVOKE_MODE=response_stream` and `AWS_LWA_READINESS_CHECK_PATH=/health` configure the adapter.
- **Edge**: CloudFront behaviour for `/api/agent/*` sets `compress = false`. Compression requires knowing the full response size and therefore buffers — fatal for SSE.
- **CORS**: moves from API Gateway config to FastAPI `CORSMiddleware`, scoped to the dashboard origin and localhost for Vite dev.

## Consequences
**Easier:**
- Real streaming in production — `step` events arrive incrementally, matching TestClient behaviour.
- Full 60s Lambda budget replaces the 29s API Gateway cliff. No in-graph wall-clock guard needed; `MAX_ITERATIONS=3` plus per-tool 10s timeouts are sufficient.
- Same FastAPI code runs locally (`uvicorn fpl_agent.api:app`) and in Lambda (LWA + uvicorn). Fewer Lambda/local divergences.
- No Mangum — one fewer translation layer.

**Harder — mitigations:**
- **Lost: API Gateway's 10rps/20-burst endpoint throttling.** Replaced by a layered defence: Lambda `reserved_concurrent_executions = 10` (caps parallel invocations at the infrastructure level), the existing per-session `RateLimiter`, the `BudgetTracker` monthly cap, and AWS Shield Standard (automatic at CloudFront). WAF with a rate-based rule is the textbook L7 replacement; deferred until production traffic justifies the ~$5/month per rule. Documented in `docs/architecture/security-architecture.md`.
- **Lost: API Gateway managed CORS.** Moved into FastAPI `CORSMiddleware`.
- **Added: AWS Lambda Web Adapter to the stack.** Small, AWS-official, actively maintained, widely used in serverless AI reference architectures — but it is one more tool a reader needs to know about. Pinned to a specific image version.
- Function URL domain is cosmetically uglier (`*.lambda-url.eu-west-2.on.aws`) than an API Gateway custom stage, but CloudFront fronts it so users never see either.

## Related
- Updates ADR-0009's "HTTP entry point" description — API Gateway reference is superseded by this ADR.
- Security implications (lost throttling, layered defence, explicit WAF-later stance) are expanded in `docs/architecture/security-architecture.md`.
- AWS: *Configuring a Lambda function to stream responses* (2023).
- AWS Lambda Web Adapter: https://github.com/awslabs/aws-lambda-web-adapter.
