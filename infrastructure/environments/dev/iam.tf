# -----------------------------------------------------------------------------
# Lambda Execution Role (shared across all pipeline Lambdas)
# -----------------------------------------------------------------------------
module "lambda_role" {
  source = "../../modules/lambda-role"

  environment           = var.environment
  s3_bucket_arns        = [module.data_lake.bucket_arn, module.cost_reports.bucket_arn]
  parameter_path_prefix = "/fpl-platform/${var.environment}"
  sns_topic_arns        = [aws_sns_topic.pipeline_alerts.arn]
}
