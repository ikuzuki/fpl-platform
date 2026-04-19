# -----------------------------------------------------------------------------
# Scout Agent — HTTP entry point and runtime resources.
#
# - DynamoDB table tracks monthly token usage for budget kill-switch
# - IAM policy grants the shared Lambda role access to the table
# - Lambda Function URL (RESPONSE_STREAM) is the HTTP surface; CloudFront fronts
#   it. See ADR-0010 for the transport decision.
# -----------------------------------------------------------------------------

# Monthly usage tracking — one row per calendar month (e.g. "2026-04").
# Columns set at runtime: input_tokens, output_tokens, total_cost_usd,
# budget_limit_usd, exceeded_at. The agent lazy-creates the current month's
# row on first invocation via PutItem with attribute_not_exists(month).
resource "aws_dynamodb_table" "agent_usage" {
  name         = "fpl-agent-usage-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "month"

  attribute {
    name = "month"
    type = "S"
  }
}

resource "aws_iam_role_policy" "lambda_agent_dynamo" {
  name = "fpl-${var.environment}-agent-dynamo"
  role = module.lambda_role.role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:PutItem",
        ]
        Resource = aws_dynamodb_table.agent_usage.arn
      }
    ]
  })
}

# The agent's GET /team endpoint invokes the team-fetcher Lambda synchronously
# (see services/agent/src/fpl_agent/squad_loader.py). The agent graph itself
# never invokes Lambdas — squad loading is strictly an HTTP-layer concern.
# Scoped to the one function rather than `*` so a future second invokeable
# Lambda has to be granted explicitly.
resource "aws_iam_role_policy" "lambda_agent_invoke_team_fetcher" {
  name = "fpl-${var.environment}-agent-invoke-team-fetcher"
  role = module.lambda_role.role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = module.lambda_team_fetcher.function_arn
      }
    ]
  })
}

# Lambda Function URL with response streaming. `AuthType = NONE` because
# CloudFront is the only fronting origin in production — never called directly.
# A future hardening step is moving to AWS_IAM with CloudFront OAC signing
# requests (flagged in docs/architecture/security-architecture.md).
resource "aws_lambda_function_url" "agent" {
  function_name      = module.lambda_agent.function_name
  authorization_type = "NONE"
  invoke_mode        = "RESPONSE_STREAM"

  # CORS is handled at the FastAPI application layer so the dashboard and
  # localhost Vite dev can both hit the endpoint. Function URL CORS config
  # is left empty to avoid a duplicate layer that would need to stay in
  # sync with the application config.
}

# Resource-based policy paired with the URL above. Function URLs have two
# independent access gates AND'd together: the URL's `authorization_type`
# (SigV4 check) and the function's resource policy (allowed principals).
# `authorization_type = "NONE"` only skips the SigV4 step — it does NOT
# grant invoke permission. Without this `aws_lambda_permission` every
# request hits the URL and returns 403 because the resource policy is
# empty. AWS keeps the gates decoupled so opening a function to the
# public internet stays an explicit, auditable action.
#
# CloudFront masks the 403 with the SPA error-page fallback (403 →
# /index.html with HTTP 200), so the symptom presents as the dashboard
# receiving HTML instead of JSON and throwing SyntaxError on
# response.json(). Hence the explicit public grant here.
resource "aws_lambda_permission" "agent_function_url_public" {
  statement_id           = "FunctionURLAllowPublicAccess"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = module.lambda_agent.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}
