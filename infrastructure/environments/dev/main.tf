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
