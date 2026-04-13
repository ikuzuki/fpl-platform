variable "name" {
  description = "Name of the HTTP API (also used as the prefix for the CloudWatch access log group). Typically matches the Lambda function name, e.g. 'fpl-agent-dev'."
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev/prod)."
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be dev or prod."
  }
}

variable "lambda_function_name" {
  description = "Name of the Lambda function to integrate with. Used for the lambda:InvokeFunction permission."
  type        = string
}

variable "lambda_invoke_arn" {
  description = "Invoke ARN of the Lambda function (aws_lambda_function.x.invoke_arn)."
  type        = string
}

variable "cors_allow_origins" {
  description = "List of origins allowed to call the API. Use bare https URLs, e.g. ['https://d1abc.cloudfront.net', 'http://localhost:5173']."
  type        = list(string)
}

variable "throttle_rate_limit" {
  description = "Steady-state throttle rate (requests per second) applied across all routes on the default stage."
  type        = number
  default     = 10

  validation {
    condition     = var.throttle_rate_limit > 0
    error_message = "throttle_rate_limit must be greater than 0."
  }
}

variable "throttle_burst_limit" {
  description = "Burst throttle limit (concurrent requests) applied across all routes on the default stage."
  type        = number
  default     = 20

  validation {
    condition     = var.throttle_burst_limit > 0
    error_message = "throttle_burst_limit must be greater than 0."
  }
}
