# Step Function Module

Creates an AWS Step Functions state machine with an execution role that can invoke Lambda functions.

## Usage

```hcl
module "pipeline" {
  source      = "../../modules/step-function"
  name        = "data-pipeline"
  environment = "dev"
  definition  = file("pipeline-definition.asl.json")
  lambda_arns = [module.collector.function_arn, module.enricher.function_arn]
}
```

## Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| name | State machine name | string | - |
| environment | Deployment environment | string | - |
| definition | ASL definition (JSON) | string | - |
| lambda_arns | Lambda ARNs to invoke | list(string) | [] |
| log_retention_days | CloudWatch log retention in days | number | 30 |

## Outputs

| Name | Description |
|------|-------------|
| state_machine_arn | State machine ARN |
| state_machine_name | State machine name |
| role_arn | Execution role ARN |
| log_group_arn | CloudWatch log group ARN |
