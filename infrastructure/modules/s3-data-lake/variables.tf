variable "project" {
  description = "Project name for resource naming"
  type        = string
  default     = "fpl"
}

variable "environment" {
  description = "Deployment environment (dev/prod)"
  type        = string
}

variable "name" {
  description = "Bucket purpose name (e.g. 'data-lake', 'cost-reports'). Bucket will be named {project}-{name}-{environment}."
  type        = string
  default     = "data-lake"
}

variable "enable_data_lake_lifecycle" {
  description = "Enable raw/ transition/expiration and dlq/ expiration lifecycle rules. Set to false for non-data-lake buckets."
  type        = bool
  default     = true
}
