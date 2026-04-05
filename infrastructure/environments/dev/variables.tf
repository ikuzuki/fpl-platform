variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be dev or prod."
  }
}

variable "notification_email" {
  description = "Email address for pipeline alert notifications"
  type        = string
}

variable "current_season" {
  description = "Current FPL season for the weekly pipeline trigger (e.g. 2025-26)"
  type        = string
  default     = "2025-26"
}

variable "current_gameweek" {
  description = "Current gameweek number for the weekly pipeline trigger (update via tfvars each week)"
  type        = number
  default     = 1
}
