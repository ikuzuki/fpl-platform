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

variable "agent_api_domain" {
  description = "Bare host (no scheme) of the agent API Gateway endpoint, e.g. 'abc123.execute-api.eu-west-2.amazonaws.com'. Empty string disables the /api/agent/* behaviour — useful when the agent stack isn't deployed yet."
  type        = string
  default     = ""
}
