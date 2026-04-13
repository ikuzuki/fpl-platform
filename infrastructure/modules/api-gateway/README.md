# api-gateway

HTTP API (API Gateway v2) with a Lambda proxy integration, CORS, request
throttling, and CloudWatch access logs. Designed for the Scout Agent Lambda
but reusable for any single-Lambda HTTP service.

## Routes
- `POST /chat` — agent chat endpoint (streaming responses expected)
- `GET /health` — liveness probe

Both routes target the same Lambda — the handler dispatches on `event.rawPath`.

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `name` | string | — | API name (also log group prefix). Typically the Lambda function name. |
| `environment` | string | — | `dev` or `prod`. |
| `lambda_function_name` | string | — | Lambda to invoke (for the invoke permission). |
| `lambda_invoke_arn` | string | — | Lambda invoke ARN (`aws_lambda_function.x.invoke_arn`). |
| `cors_allow_origins` | list(string) | — | Allowed origins. Do not use `["*"]` on LLM-backed endpoints. |
| `throttle_rate_limit` | number | `10` | Steady-state req/s on the default stage. |
| `throttle_burst_limit` | number | `20` | Burst concurrency on the default stage. |

## Outputs

| Name | Description |
|---|---|
| `api_endpoint` | Full URL including `https://`. Test directly via `curl`. |
| `api_domain` | Bare host for use as a CloudFront origin `domain_name`. |
| `api_id` | API Gateway HTTP API ID. |
| `api_execution_arn` | Execution ARN (for Lambda invoke permission scoping). |

## Example

```hcl
module "agent_api" {
  source = "../../modules/api-gateway"

  name                 = "fpl-agent-dev"
  environment          = "dev"
  lambda_function_name = module.lambda_agent.function_name
  lambda_invoke_arn    = module.lambda_agent.invoke_arn
  cors_allow_origins   = ["https://${module.web_hosting.cloudfront_domain}", "http://localhost:5173"]
}
```

## Why HTTP API (v2) instead of REST API (v1)?

- ~70% cheaper per request
- Native JWT authorizer support (useful if/when auth is added)
- Payload format 2.0 is what FastAPI/LangGraph handlers expect
- Lower latency (no request/response transformations by default)

REST APIs remain useful for usage plans and API keys — neither needed here.
