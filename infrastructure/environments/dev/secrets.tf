# -----------------------------------------------------------------------------
# Secrets Manager
#
# Secret shells only — values are populated manually via the AWS Console.
# After a fresh `terraform apply`, set each secret's value in the Console
# before running the pipeline (Lambdas read these at runtime via the SDK).
# -----------------------------------------------------------------------------
resource "aws_secretsmanager_secret" "anthropic_api_key" {
  name        = "/fpl-platform/${var.environment}/anthropic-api-key"
  description = "Anthropic API key for LLM enrichment"
}

resource "aws_secretsmanager_secret" "langfuse_public_key" {
  name        = "/fpl-platform/${var.environment}/langfuse-public-key"
  description = "Langfuse public key for observability"
}

resource "aws_secretsmanager_secret" "langfuse_secret_key" {
  name        = "/fpl-platform/${var.environment}/langfuse-secret-key"
  description = "Langfuse secret key for observability"
}

resource "aws_secretsmanager_secret" "neon_database_url" {
  name        = "/fpl-platform/${var.environment}/neon-database-url"
  description = "Neon Postgres connection string for the Scout Agent (pgvector backend)"
}
