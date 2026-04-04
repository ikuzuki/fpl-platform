variable "code_repo_name" {
  description = "Name of the GitHub repository"
  type        = string
  default     = "fpl-platform"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be dev or prod."
  }
}

locals {
  common_tags = {
    Repository  = var.code_repo_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Project     = "fpl-platform"
  }
}
