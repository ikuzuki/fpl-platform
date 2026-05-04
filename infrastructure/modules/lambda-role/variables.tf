variable "project" {
  description = "Project name for resource naming"
  type        = string
  default     = "fpl"
}

variable "environment" {
  description = "Deployment environment (dev/prod)"
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be dev or prod."
  }
}

variable "s3_bucket_arns" {
  description = "List of S3 bucket ARNs the Lambda role can access"
  type        = list(string)
}

variable "parameter_path_prefix" {
  description = "SSM Parameter Store path prefix (e.g. /fpl-platform/dev) — scopes the Lambda role's GetParameter permission."
  type        = string
}

variable "sns_topic_arns" {
  description = "List of SNS topic ARNs the Lambda role can publish to"
  type        = list(string)
  default     = []
}
