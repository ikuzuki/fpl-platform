terraform {
  required_version = ">= 1.3.0"

  backend "s3" {
    bucket         = "fpl-dev-tf-state"
    key            = "dev/terraform.tfstate"
    region         = "eu-west-2"
    dynamodb_table = "fpl-dev-tf-lock-table"
    encrypt        = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "eu-west-2"

  default_tags {
    tags = {
      Repository  = "fpl-platform"
      Environment = var.environment
      ManagedBy   = "terraform"
      Project     = "fpl-platform"
    }
  }
}

# Modules will be added here as services are built.
# Example:
# module "data_lake" {
#   source      = "../../modules/s3-data-lake"
#   environment = var.environment
# }
