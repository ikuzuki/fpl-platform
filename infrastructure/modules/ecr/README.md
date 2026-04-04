# ECR Module

Creates an ECR repository with configurable tag mutability, scan on push, and a lifecycle policy to retain the last 10 images.

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
| image_tag_mutability | Tag mutability (MUTABLE for dev, IMMUTABLE for prod) | string | "MUTABLE" |

## Outputs

| Name | Description |
|------|-------------|
| repository_url | ECR repository URL |
| repository_arn | ECR repository ARN |
| repository_name | ECR repository name |
