terraform {
  backend "s3" {
    bucket         = "fpl-dev-tf-state"
    key            = "dev/terraform.tfstate"
    region         = "eu-west-2"
    dynamodb_table = "fpl-dev-tf-lock-table"
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
# Remote state — bootstrap stack (OIDC provider, CICD role, budget alerts)
#
# Prerequisite: migrate bootstrap local state to S3:
#   cd infrastructure/bootstrap
#   terraform init -migrate-state \
#     -backend-config="bucket=fpl-dev-tf-state" \
#     -backend-config="key=bootstrap/terraform.tfstate" \
#     -backend-config="region=eu-west-2" \
#     -backend-config="dynamodb_table=fpl-dev-tf-lock-table" \
#     -backend-config="encrypt=true"
# -----------------------------------------------------------------------------
data "terraform_remote_state" "bootstrap" {
  backend = "s3"

  config = {
    bucket = "fpl-dev-tf-state"
    key    = "bootstrap/terraform.tfstate"
    region = "eu-west-2"
  }
}

# -----------------------------------------------------------------------------
# S3 Data Lake
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
