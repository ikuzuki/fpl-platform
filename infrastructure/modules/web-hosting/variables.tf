variable "environment" {
  description = "Deployment environment (dev/prod)"
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be dev or prod."
  }
}

variable "data_lake_bucket_name" {
  description = "Name of the S3 data lake bucket (fpl-data-lake-{env}). CloudFront will be granted read access to the public/ prefix."
  type        = string
}

variable "data_lake_bucket_arn" {
  description = "ARN of the S3 data lake bucket. Used to scope the CloudFront OAC bucket policy."
  type        = string
}

variable "price_class" {
  description = "CloudFront price class. PriceClass_100 covers US/Europe (cheapest). PriceClass_All adds Asia/Pacific."
  type        = string
  default     = "PriceClass_100"

  validation {
    condition     = contains(["PriceClass_100", "PriceClass_200", "PriceClass_All"], var.price_class)
    error_message = "price_class must be PriceClass_100, PriceClass_200, or PriceClass_All."
  }
}

variable "enable_agent_api" {
  description = "Whether to wire the /api/agent/* CloudFront behaviour to the agent endpoint. Must be a statically-known bool (not derived from a computed attribute) so count/for_each can be evaluated at plan time."
  type        = bool
  default     = false
}

variable "agent_api_domain" {
  description = "Bare host (no scheme) of the agent endpoint, e.g. the Lambda Function URL host 'abc123.lambda-url.eu-west-2.on.aws'. Only read when enable_agent_api is true. May be a computed attribute — Terraform defers resolution to apply-time."
  type        = string
  default     = ""
}
