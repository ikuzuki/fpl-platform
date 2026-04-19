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

# Lambda Function URL with response streaming. `AuthType = AWS_IAM` means
# the URL rejects any request that isn't SigV4-signed. CloudFront signs every
# origin request via the Lambda OAC in the web-hosting module, so CloudFront
# is the only caller that can reach this Lambda — hitting the Function URL
# directly (e.g. `curl https://<host>.lambda-url.eu-west-2.on.aws/`) returns
# 403 "signature missing". See #123 and docs/architecture/security-architecture.md.
resource "aws_lambda_function_url" "agent" {
  function_name      = module.lambda_agent.function_name
  authorization_type = "AWS_IAM"
  invoke_mode        = "RESPONSE_STREAM"

  # CORS is handled at the FastAPI application layer so the dashboard and
  # localhost Vite dev can both hit the endpoint. Function URL CORS config
  # is left empty to avoid a duplicate layer that would need to stay in
  # sync with the application config.
}

# Resource-based policy paired with the URL above. Function URLs have two
# independent access gates AND'd together: the URL's `authorization_type`
# (SigV4 check) and the function's resource policy (allowed principals).
# Both gates must pass.
#
# This policy grants `lambda:InvokeFunctionUrl` to the CloudFront service
# principal, scoped by `aws:SourceArn` to our one distribution. Combined with
# `authorization_type = "AWS_IAM"` and the Lambda OAC on the CloudFront
# origin, the only SigV4-signed caller the URL will accept is this
# distribution. The Function URL is therefore not publicly reachable:
#   - direct curl → 403 (no SigV4 signature)
#   - curl signed by another account/role → 403 (principal mismatch)
#   - CloudFront origin request → 200 (OAC signs with the right principal)
resource "aws_lambda_permission" "agent_function_url_cloudfront" {
  statement_id           = "AllowCloudFrontInvokeFunctionUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = module.lambda_agent.function_name
  principal              = "cloudfront.amazonaws.com"
  source_arn             = module.web_hosting.cloudfront_distribution_arn
  function_url_auth_type = "AWS_IAM"
}
