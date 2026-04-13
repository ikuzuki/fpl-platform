# -----------------------------------------------------------------------------
# Scout Agent — HTTP entry point and runtime resources.
#
# - DynamoDB table tracks monthly token usage for budget kill-switch
# - IAM policy grants the shared Lambda role access to the table
# - API Gateway v2 fronts the agent Lambda with CORS + throttling
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

module "api_gateway" {
  source = "../../modules/api-gateway"

  name                 = "fpl-agent-${var.environment}"
  environment          = var.environment
  lambda_function_name = module.lambda_agent.function_name
  lambda_invoke_arn    = module.lambda_agent.invoke_arn

  # Production traffic is same-origin (dashboard and agent both served from
  # the CloudFront domain), so CORS only matters for local Vite dev.
  # Intentionally scoped to localhost to avoid a circular dependency on
  # module.web_hosting.cloudfront_domain.
  cors_allow_origins = ["http://localhost:5173"]
}
