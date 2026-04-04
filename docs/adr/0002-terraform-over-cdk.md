# ADR-0002: Terraform over CDK

## Status
Accepted

## Date
2026-04-04

## Context
We need Infrastructure as Code for managing AWS resources (S3 buckets, Lambda functions, ECR repos, Step Functions, IAM roles). The project is AWS-only and the author has professional Terraform experience from Intech.

## Options Considered

### 1. Terraform with HCL (chosen)
Declarative, cloud-agnostic, large community. Module-based composition (`modules/lambda`, `modules/s3-data-lake`, etc.).

### 2. AWS CDK with Python (rejected)
AWS-specific, imperative, uses the same language as the services. Offers higher-level constructs that abstract boilerplate.

**Rejected because:**
- The author has professional Terraform experience (Intech's entire infrastructure is Terraform) — CDK would mean learning a new tool for no portfolio benefit
- Terraform is the most widely used IaC tool; stronger hiring signal for infrastructure-aware roles
- HCL is readable by non-Python developers — the project targets a general technical audience
- CDK's higher-level constructs can obscure what's actually being created, making it harder for reviewers to verify IAM policies and resource configs

### 3. AWS SAM / CloudFormation (rejected)
**Rejected because:** Verbose YAML/JSON, no module system, poor reusability. SAM is Lambda-focused and doesn't cover the full resource set (Step Functions, ECR lifecycle policies, budget alerts).

## Decision
Use Terraform with HCL for all infrastructure management. Modules in `infrastructure/modules/`, environments in `infrastructure/environments/{env}/`.

## Consequences
**Easier:**
- Portable — not locked to AWS (though we only use AWS today)
- `terraform plan` gives exact diff before apply — critical for a project with budget alerts at $5/month
- Module composition is straightforward and well-documented
- `terraform-docs` auto-generates module READMEs
- State backend (S3 + DynamoDB) is already bootstrapped and proven at Intech

**Harder:**
- Two languages in the project (HCL + Python) instead of one
- CDK's L2/L3 constructs would reduce boilerplate for common patterns (e.g., Lambda + API Gateway)
- No type safety in HCL — variable mismatches are caught at plan time, not compile time
