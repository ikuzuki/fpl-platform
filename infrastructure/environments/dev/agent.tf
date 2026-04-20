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
# TEMPORARILY reverted (again) from AWS_IAM + CloudFront-OAC to
# `AuthType = NONE` + `principal = "*"`. PR #132 fixed the root cause of
# the dashboard 403s (missing `lambda:InvokeFunction` grant required by
# AWS's October-2025 Function URL change) and re-enabled the AWS_IAM +
# OAC hardening, BUT CloudFront→Function URL was still rejected with 403
# even after the permission fix. Metrics show `Url4xxCount = UrlRequestCount`
# — every CloudFront-signed origin request is being rejected. With the
# permission gap now closed, the remaining OAC issue is genuinely separate
# (suspect interaction between OAC SigV4 signing and RESPONSE_STREAM, or
# the resource-policy `cloudfront.amazonaws.com` + SourceArn condition
# not matching OAC-signed requests).
#
# Short-term: `AuthType = NONE` + `principal = "*"` — direct curl to the
# Function URL works, CloudFront forwards unsigned requests and the URL
# accepts them. Re-hardening to AWS_IAM is parked as a follow-up once the
# OAC/resource-policy matching question has a real answer.
resource "aws_lambda_function_url" "agent" {
  function_name      = module.lambda_agent.function_name
  authorization_type = "NONE"
  invoke_mode        = "RESPONSE_STREAM"

  # CORS is handled at the FastAPI application layer so the dashboard and
  # localhost Vite dev can both hit the endpoint. Function URL CORS config
  # is left empty to avoid a duplicate layer that would need to stay in
  # sync with the application config.
}

# Function URL gates invocation by TWO independent checks AND'd together:
# the URL's `authorization_type` (SigV4 check) and the function's resource
# policy (allowed principals). `AuthType = NONE` skips the SigV4 step but
# does NOT grant invoke permission.
#
# As of AWS's October 2025 change, the resource policy must grant BOTH
# `lambda:InvokeFunctionUrl` AND `lambda:InvokeFunction` — in separate
# statements, independently checked. Missing either one returns
# `403 AccessDeniedException` "even when the function URL uses the NONE
# auth type" (Lambda docs). Verified in-incident: adding only the first
# statement produced the 403 loop the dashboard spent hours stuck on.
# See https://docs.aws.amazon.com/lambda/latest/dg/urls-auth.html
resource "aws_lambda_permission" "agent_function_url_public" {
  statement_id           = "FunctionURLAllowPublicAccess"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = module.lambda_agent.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "agent_function_url_public_invoke" {
  statement_id  = "FunctionURLInvokeFunctionPublic"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda_agent.function_name
  principal     = "*"
}
