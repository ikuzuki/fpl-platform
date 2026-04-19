# Prod environment — Terraform stub

**Status: declared, not applied.**

This directory contains the Terraform root for the prod environment. It is not
currently provisioned on any AWS account — the FPL platform runs dev-only on a
personal account, and standing up a second account is a provisioning task, not
a signal of missing engineering work.

## What's here

- [`main.tf`](main.tf) — backend config (prod state bucket + lock table) and
  the foundational module calls: [`data_lake`](../../modules/s3-data-lake/)
  and `cost_reports`.
- [`variables.tf`](variables.tf), [`versions.tf`](versions.tf),
  [`tags.tf`](tags.tf) — identical to [`../dev/`](../dev/) except
  `variable "environment"` defaults to `"prod"`.
- [`terraform.tfvars.example`](terraform.tfvars.example) — the values a real
  deployment would fill in. Kept as `.example` so a stray `terraform apply`
  errors out rather than running with placeholder input.

## What's **not** here

The service-level `.tf` files that dev has —
[`agent.tf`](../dev/agent.tf), [`ecr.tf`](../dev/ecr.tf),
[`iam.tf`](../dev/iam.tf), [`lambda.tf`](../dev/lambda.tf),
[`pipeline.tf`](../dev/pipeline.tf), [`secrets.tf`](../dev/secrets.tf),
[`web.tf`](../dev/web.tf), [`notifications.tf`](../dev/notifications.tf),
[`outputs.tf`](../dev/outputs.tf) — are not duplicated here. Every module call
inside those files already takes `environment = var.environment`, so they are
copy-ready: the set of modules does not change between dev and prod, only the
state backend and the tfvars.

Duplicating them here unapplied would create a drift-prone second copy that a
future dev-only change silently falsifies. Leaving them in dev and
copying-on-lift keeps a single source of truth until prod is actually funded.

## Lifting to a real prod deployment

1. Create the state bucket + lock table referenced in
   [`main.tf`](main.tf) (`fpl-prod-tf-state`, `fpl-prod-tf-lock-table`).
2. Copy the service-level `.tf` files from [`../dev/`](../dev/) into this
   directory.
3. Copy [`terraform.tfvars.example`](terraform.tfvars.example) to
   `terraform.tfvars` and fill in real values. (This repo commits tfvars —
   see [`../dev/terraform.tfvars`](../dev/terraform.tfvars) — so review the
   values before committing; secrets don't belong in tfvars regardless.)
4. Configure an AWS profile scoped to the prod account.
5. `terraform init && terraform plan` — review the diff against a fresh prod
   account. Apply when satisfied.

## Why this matters

The modules under [`../../modules/`](../../modules/) are environment-parameterised
(every one takes `var.environment` and namespaces its AWS resources on it).
This directory is the proof that dev and prod are a provisioning difference,
not a code-structure one. If tomorrow a prod account appeared, the path to a
green `terraform plan` is mechanical — no module refactor, no environment-hoisting
exercise, no "we'd have to split this first" blocker.
