# Runbook

Operational procedures for the FPL platform.

## Running the Pipeline Manually

```bash
export AWS_PROFILE=fpl-dev
python -m fpl_data.handlers.fpl_api_collector --season 2025-26 --gameweek 15
```

## Terraform Operations

```bash
cd infrastructure/environments/dev
terraform init
terraform plan
terraform apply
```

## Common Issues

*To be populated as issues are encountered.*
