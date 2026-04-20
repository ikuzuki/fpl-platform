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

# Lambda Function URL with response streaming.
#
# TEMPORARILY REVERTED from the AWS_IAM + CloudFront-OAC hardening in #125
# because every CloudFront→Function URL origin request was being rejected
# with 403 (`Url4xxCount = UrlRequestCount` on the Lambda metrics, Lambda
# never invoked), and CloudFront's custom_error_response masked the 403
# with the SPA /index.html fallback, so the dashboard saw cached HTML
# instead of JSON/SSE. Investigation showed OAC, resource-policy SourceArn,
# and `lambda:FunctionUrlAuthType` condition all matching the live state,
# yet OAC signing was still being rejected — suspected stuck OAC or an
# interaction between RESPONSE_STREAM and OAC that we haven't nailed down.
#
# Back to `AuthType = NONE` + `principal = "*"` (the state between #123
# and #125) to unblock the product while the OAC issue is investigated
# separately. The eventual re-hardening is tracked in
# docs/architecture/security-architecture.md.
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
# `authorization_type = "NONE"` skips the SigV4 check but does NOT grant
# invoke permission — without this permission every request hits the URL
# and returns 403 because the resource policy would be empty. See #123.
resource "aws_lambda_permission" "agent_function_url_public" {
  statement_id           = "FunctionURLAllowPublicAccess"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = module.lambda_agent.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

# Second statement required by AWS's October 2025 change: Function URLs now
# require `lambda:InvokeFunction` IN ADDITION to `lambda:InvokeFunctionUrl`.
# Without this, every request returns `403 Forbidden` with
# `AccessDeniedException` even when the URL is `AuthType = NONE` and
# the first statement allows `Principal = "*"`. The two permissions were
# previously implicit-granted by a single `lambda:InvokeFunctionUrl`;
# AWS now checks them independently.
# See https://docs.aws.amazon.com/lambda/latest/dg/urls-auth.html
# (the "Starting in October 2025" note).
resource "aws_lambda_permission" "agent_function_url_public_invoke" {
  statement_id  = "FunctionURLInvokeFunctionPublic"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda_agent.function_name
  principal     = "*"
}
