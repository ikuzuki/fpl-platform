# ECR Module

Creates an ECR repository with immutable tags, scan on push, and a lifecycle policy to retain the last 10 images.

## Usage

```hcl
module "data_repo" {
  source      = "../../modules/ecr"
  name        = "data-collector"
  environment = "dev"
}
```

## Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| name | Repository name | string | - |
| environment | Deployment environment | string | - |

## Outputs

| Name | Description |
|------|-------------|
| repository_url | ECR repository URL |
| repository_arn | ECR repository ARN |
| repository_name | ECR repository name |
