# -----------------------------------------------------------------------------
# Prod environment — Terraform stub. NOT APPLIED.
#
# This directory declares the prod root but is not currently provisioned on any
# AWS account. It exists to demonstrate that every module under
# ../../modules/ is environment-parameterised via `var.environment`, so the
# lift to a real prod deployment is a provisioning task, not a refactor.
#
# To go live:
#   1. Create the state bucket + lock table referenced in the backend block
#      below (`fpl-prod-tf-state`, `fpl-prod-tf-lock-table`).
#   2. Copy the service-level .tf files from ../dev/ (agent.tf, ecr.tf, iam.tf,
#      lambda.tf, pipeline.tf, secrets.tf, web.tf, notifications.tf,
#      outputs.tf) into this directory. Every module call in those files
#      already takes `environment = var.environment`, so the set of modules
#      does not need to change — only the backend + tfvars + a terraform init
#      against a prod-scoped AWS profile.
#   3. Copy terraform.tfvars.example to terraform.tfvars and fill in values.
#   4. `terraform init && terraform plan`.
#
# See README.md for context.
# -----------------------------------------------------------------------------
terraform {
  backend "s3" {
    bucket         = "fpl-prod-tf-state"
    key            = "prod/terraform.tfstate"
    region         = "eu-west-2"
    dynamodb_table = "fpl-prod-tf-lock-table"
    encrypt        = true
  }
}

provider "aws" {
  region = "eu-west-2"

  default_tags {
    tags = local.common_tags
  }
}

# -----------------------------------------------------------------------------
# S3 Data Lake — foundational storage. Mirrors dev/main.tf; the module accepts
# `environment = "prod"` and produces prod-scoped bucket names + lifecycle
# rules without code change.
# -----------------------------------------------------------------------------
module "data_lake" {
  source      = "../../modules/s3-data-lake"
  environment = var.environment
}

module "cost_reports" {
  source                     = "../../modules/s3-data-lake"
  name                       = "cost-reports"
  environment                = var.environment
  enable_data_lake_lifecycle = false
}
