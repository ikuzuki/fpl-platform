# -----------------------------------------------------------------------------
# CloudFront → Agent shared-secret header
#
# Replaces OAC for the /api/agent/* path — OAC doesn't work for our browser
# POST clients (requires x-amz-content-sha256 which browsers don't send). The
# value is generated once by Terraform, stored in SSM Parameter Store for
# audit / rotation, injected into the CloudFront origin header below, and
# read back into the Lambda env at cold-start via resolve_secret_to_env.
# Rotation:
#   terraform taint random_password.cloudfront_agent_secret && terraform apply
# CloudFront propagation is ~5 min; during that window some in-flight requests
# may 401 until the Lambda cold-starts and picks up the new value. Acceptable
# at dev scale — documented in docs/architecture/security-architecture.md.
# -----------------------------------------------------------------------------
resource "random_password" "cloudfront_agent_secret" {
  length  = 48
  special = false
}

resource "aws_ssm_parameter" "cloudfront_agent_secret" {
  name        = "/fpl-platform/${var.environment}/cloudfront-agent-secret"
  description = "Shared secret CloudFront injects into /api/agent/* origin requests. The agent Lambda validates incoming requests carry this header."
  type        = "SecureString"
  value       = random_password.cloudfront_agent_secret.result
}

# -----------------------------------------------------------------------------
# Web Hosting — S3 + CloudFront for the React dashboard
# -----------------------------------------------------------------------------
module "web_hosting" {
  source = "../../modules/web-hosting"

  environment           = var.environment
  data_lake_bucket_name = module.data_lake.bucket_name
  data_lake_bucket_arn  = module.data_lake.bucket_arn
  # enable_agent_api is a statically-known bool so CloudFront's count/for_each
  # on the agent behaviour can be resolved at plan time. agent_api_domain is
  # a computed attribute (the Function URL is unknown until apply) — that's
  # fine once the module no longer gates its resources on the string itself.
  enable_agent_api                 = true
  agent_api_domain                 = trimsuffix(replace(aws_lambda_function_url.agent.function_url, "https://", ""), "/")
  agent_shared_secret_header_value = random_password.cloudfront_agent_secret.result
}

# -----------------------------------------------------------------------------
# CloudFront Cache Invalidation — EventBridge reacts to pipeline success
# -----------------------------------------------------------------------------
data "archive_file" "invalidate_cache" {
  type        = "zip"
  source_file = "../../lambdas/invalidate_cache/handler.py"
  output_path = "../../lambdas/invalidate_cache/handler.zip"
}

resource "aws_lambda_function" "invalidate_cache" {
  function_name    = "fpl-${var.environment}-invalidate-cache"
  role             = aws_iam_role.invalidate_cache.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.11"
  timeout          = 30
  memory_size      = 128
  filename         = data.archive_file.invalidate_cache.output_path
  source_code_hash = data.archive_file.invalidate_cache.output_base64sha256

  environment {
    variables = {
      CLOUDFRONT_DISTRIBUTION_ID = module.web_hosting.cloudfront_distribution_id
    }
  }
}

resource "aws_cloudwatch_log_group" "invalidate_cache" {
  name              = "/aws/lambda/fpl-${var.environment}-invalidate-cache"
  retention_in_days = 30
}

resource "aws_iam_role" "invalidate_cache" {
  name = "fpl-${var.environment}-invalidate-cache-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "invalidate_cache_basic" {
  role       = aws_iam_role.invalidate_cache.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "invalidate_cache_cloudfront" {
  name = "fpl-${var.environment}-invalidate-cache-cloudfront"
  role = aws_iam_role.invalidate_cache.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["cloudfront:CreateInvalidation"]
        Resource = "arn:aws:cloudfront::*:distribution/${module.web_hosting.cloudfront_distribution_id}"
      }
    ]
  })
}

# EventBridge rule: fires when the collection pipeline execution succeeds
resource "aws_cloudwatch_event_rule" "pipeline_succeeded" {
  name        = "fpl-pipeline-succeeded-${var.environment}"
  description = "Fires when the FPL collection pipeline completes successfully"

  event_pattern = jsonencode({
    source      = ["aws.states"]
    detail-type = ["Step Functions Execution Status Change"]
    detail = {
      status          = ["SUCCEEDED"]
      stateMachineArn = [module.pipeline.state_machine_arn]
    }
  })
}

resource "aws_cloudwatch_event_target" "invalidate_cache" {
  rule = aws_cloudwatch_event_rule.pipeline_succeeded.name
  arn  = aws_lambda_function.invalidate_cache.arn
}

resource "aws_lambda_permission" "eventbridge_invalidate_cache" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.invalidate_cache.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.pipeline_succeeded.arn
}
