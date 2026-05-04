# -----------------------------------------------------------------------------
# SSM Parameter Store
#
# SecureString parameter shells only — values are populated manually via the
# AWS Console after a fresh `terraform apply`. Lambdas read these at cold-start
# via `fpl_lib.secrets.resolve_secret_to_env`.
#
# `lifecycle.ignore_changes = [value]` means Terraform creates the parameter
# with the placeholder, then leaves the value alone on subsequent applies once
# you've populated the real value through the Console. Default key alias
# `alias/aws/ssm` handles encryption — free, no per-key KMS cost.
#
# See ADR-0011 for why we use Parameter Store over Secrets Manager.
# -----------------------------------------------------------------------------
resource "aws_ssm_parameter" "anthropic_api_key" {
  name        = "/fpl-platform/${var.environment}/anthropic-api-key"
  description = "Anthropic API key for LLM enrichment"
  type        = "SecureString"
  value       = "REPLACE_ME"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "langfuse_public_key" {
  name        = "/fpl-platform/${var.environment}/langfuse-public-key"
  description = "Langfuse public key for observability"
  type        = "SecureString"
  value       = "REPLACE_ME"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "langfuse_secret_key" {
  name        = "/fpl-platform/${var.environment}/langfuse-secret-key"
  description = "Langfuse secret key for observability"
  type        = "SecureString"
  value       = "REPLACE_ME"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "neon_database_url" {
  name        = "/fpl-platform/${var.environment}/neon-database-url"
  description = "Neon Postgres connection string for the Scout Agent (pgvector backend)"
  type        = "SecureString"
  value       = "REPLACE_ME"

  lifecycle {
    ignore_changes = [value]
  }
}
