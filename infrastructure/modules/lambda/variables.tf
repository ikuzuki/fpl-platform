variable "name" {
  description = "Name of the Lambda function"
  type        = string
}

variable "project" {
  description = "Project name for resource naming"
  type        = string
  default     = "fpl"
}

variable "environment" {
  description = "Deployment environment (dev/prod)"
  type        = string
}

variable "image_uri" {
  description = "ECR image URI for the Lambda function"
  type        = string
}

variable "timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 300
}

variable "memory_size" {
  description = "Lambda memory size in MB"
  type        = number
  default     = 512
}

variable "execution_role_arn" {
  description = "Optional external IAM role ARN. When provided, the module skips creating its own role."
  type        = string
  default     = null
}

variable "environment_variables" {
  description = "Environment variables for the Lambda function"
  type        = map(string)
  default     = {}
}

variable "command" {
  description = "Handler entry point for container image Lambdas (e.g. 'fpl_data.handlers.fpl_api_handler.lambda_handler'). Leave null to use the container image's own CMD (required when the image runs a long-lived server like uvicorn via Lambda Web Adapter)."
  type        = list(string)
  default     = null
}

variable "reserved_concurrent_executions" {
  description = "Caps parallel invocations. -1 uses the account-level unreserved pool (default). Used as hardware-level backpressure on public endpoints — see docs/architecture/security-architecture.md."
  type        = number
  default     = -1
}
