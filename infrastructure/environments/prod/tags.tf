locals {
  common_tags = {
    Repository  = "fpl-platform"
    Environment = var.environment
    ManagedBy   = "terraform"
    Project     = "fpl-platform"
  }
}
