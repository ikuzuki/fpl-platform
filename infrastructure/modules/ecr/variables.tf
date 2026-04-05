variable "name" {
  description = "Name of the ECR repository"
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

variable "max_image_count" {
  description = "Maximum number of images to retain in the repository"
  type        = number
  default     = 3

  validation {
    condition     = var.max_image_count >= 1
    error_message = "Must keep at least 1 image."
  }
}

variable "image_tag_mutability" {
  description = "Tag mutability setting (MUTABLE allows :latest overwrite, IMMUTABLE for prod)"
  type        = string
  default     = "MUTABLE"

  validation {
    condition     = contains(["MUTABLE", "IMMUTABLE"], var.image_tag_mutability)
    error_message = "Must be MUTABLE or IMMUTABLE."
  }
}
