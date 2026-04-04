# S3 Data Lake Module

Creates an S3 bucket for the FPL data lake with versioning, encryption, public access blocking, and lifecycle rules.

## Data Lake Layers

- `raw/` — Raw API responses (JSON)
- `clean/` — Validated and cleaned data (Parquet)
- `enriched/` — LLM-enriched data (Parquet)
- `curated/` — Final analytics-ready data (Parquet)
- `dlq/` — Dead letter queue for failed records

## Usage

```hcl
module "data_lake" {
  source      = "../../modules/s3-data-lake"
  environment = "dev"
}
```

## Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| project | Project name | string | "fpl" |
| environment | Deployment environment | string | - |

## Outputs

| Name | Description |
|------|-------------|
| bucket_name | S3 bucket name |
| bucket_arn | S3 bucket ARN |
