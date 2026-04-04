variable "name" {
  description = "Name of the Step Functions state machine"
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

variable "definition" {
  description = "ASL definition of the state machine (JSON string)"
  type        = string
}

variable "lambda_arns" {
  description = "List of Lambda ARNs the state machine can invoke"
  type        = list(string)
  default     = []
}
