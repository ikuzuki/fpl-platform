# Lambda Role Module

Shared IAM execution role for all pipeline Lambda functions. Grants access to S3 data lake buckets, Secrets Manager, CloudWatch Logs, and optionally SNS.

## Usage

```hcl
module "lambda_role" {
  source = "../../modules/lambda-role"

  environment         = var.environment
  s3_bucket_arns      = [module.data_lake.bucket_arn, module.cost_reports.bucket_arn]
  secrets_path_prefix = "/fpl-platform/${var.environment}"
  sns_topic_arns      = [aws_sns_topic.pipeline_alerts.arn]
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| project | Project name for resource naming | string | "fpl" | no |
| environment | Deployment environment (dev/prod) | string | — | yes |
| s3_bucket_arns | S3 bucket ARNs the role can access | list(string) | — | yes |
| secrets_path_prefix | Secrets Manager path prefix | string | — | yes |
| sns_topic_arns | SNS topic ARNs the role can publish to | list(string) | [] | no |

## Outputs

| Name | Description |
|------|-------------|
| role_arn | ARN of the Lambda execution role |
| role_name | Name of the Lambda execution role |
| role_id | ID of the Lambda execution role |
