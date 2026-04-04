# Lambda Module

Creates an AWS Lambda function with container image support, execution role, and CloudWatch log group.

## Usage

```hcl
module "collector" {
  source      = "../../modules/lambda"
  name        = "fpl-api-collector"
  environment = "dev"
  image_uri   = "123456789.dkr.ecr.eu-west-2.amazonaws.com/fpl-data:latest"
}
```

## Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| name | Name of the Lambda function | string | - |
| environment | Deployment environment | string | - |
| image_uri | ECR image URI | string | - |
| timeout | Timeout in seconds | number | 300 |
| memory_size | Memory in MB | number | 512 |
| execution_role_arn | Optional external IAM role ARN (skips internal role creation) | string | null |

## Outputs

| Name | Description |
|------|-------------|
| function_name | Lambda function name |
| function_arn | Lambda function ARN |
| invoke_arn | Lambda invoke ARN |
| role_arn | Execution role ARN (external or internal) |
| role_name | Execution role name (null when using external role) |
