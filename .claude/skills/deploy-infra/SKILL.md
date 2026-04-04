---
name: deploy-infra
description: Plan and apply Terraform changes for the FPL platform
disable-model-invocation: true
---

Deploy infrastructure changes for $ARGUMENTS (defaults to dev):

1. Format: `terraform fmt -recursive infrastructure/`
2. Validate: `cd infrastructure/environments/${ARGUMENTS:-dev} && terraform validate`
3. Plan: `terraform plan -out=tfplan`
4. Show the plan summary and ask for confirmation before applying
5. Apply: `terraform apply tfplan`
6. Verify by checking key outputs
