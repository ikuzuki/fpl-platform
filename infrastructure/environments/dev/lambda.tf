# -----------------------------------------------------------------------------
# Lambda Functions
# -----------------------------------------------------------------------------
module "lambda_fpl_collector" {
  source             = "../../modules/lambda"
  name               = "fpl-api-collector"
  environment        = var.environment
  image_uri          = "${module.ecr_data.repository_url}:latest"
  execution_role_arn = module.lambda_role.role_arn
  command            = ["fpl_data.handlers.fpl_api_handler.lambda_handler"]
  timeout            = 300
  memory_size        = 512
  environment_variables = {
    ENV              = var.environment
    DATA_LAKE_BUCKET = module.data_lake.bucket_name
  }
}

module "lambda_resolve_gameweek" {
  source             = "../../modules/lambda"
  name               = "resolve-gameweek"
  environment        = var.environment
  image_uri          = "${module.ecr_data.repository_url}:latest"
  execution_role_arn = module.lambda_role.role_arn
  command            = ["fpl_data.handlers.resolve_gameweek.lambda_handler"]
  timeout            = 30
  memory_size        = 256
  environment_variables = {
    ENV = var.environment
  }
}

module "lambda_understat_collector" {
  source             = "../../modules/lambda"
  name               = "understat-collector"
  environment        = var.environment
  image_uri          = "${module.ecr_data.repository_url}:latest"
  execution_role_arn = module.lambda_role.role_arn
  command            = ["fpl_data.handlers.understat_handler.lambda_handler"]
  timeout            = 300
  memory_size        = 512
  environment_variables = {
    ENV              = var.environment
    DATA_LAKE_BUCKET = module.data_lake.bucket_name
  }
}

module "lambda_news_collector" {
  source             = "../../modules/lambda"
  name               = "news-collector"
  environment        = var.environment
  image_uri          = "${module.ecr_data.repository_url}:latest"
  execution_role_arn = module.lambda_role.role_arn
  command            = ["fpl_data.handlers.news_handler.lambda_handler"]
  timeout            = 300
  memory_size        = 512
  environment_variables = {
    ENV              = var.environment
    DATA_LAKE_BUCKET = module.data_lake.bucket_name
  }
}

module "lambda_validator" {
  source             = "../../modules/lambda"
  name               = "validator"
  environment        = var.environment
  image_uri          = "${module.ecr_data.repository_url}:latest"
  execution_role_arn = module.lambda_role.role_arn
  command            = ["fpl_data.handlers.validator.lambda_handler"]
  timeout            = 300
  memory_size        = 512
  environment_variables = {
    ENV              = var.environment
    DATA_LAKE_BUCKET = module.data_lake.bucket_name
  }
}

module "lambda_transform" {
  source             = "../../modules/lambda"
  name               = "transform"
  environment        = var.environment
  image_uri          = "${module.ecr_data.repository_url}:latest"
  execution_role_arn = module.lambda_role.role_arn
  command            = ["fpl_data.handlers.transform.lambda_handler"]
  timeout            = 300
  memory_size        = 1024
  environment_variables = {
    ENV              = var.environment
    DATA_LAKE_BUCKET = module.data_lake.bucket_name
  }
}

module "lambda_enrich_player_summary" {
  source             = "../../modules/lambda"
  name               = "enrich-player-summary"
  environment        = var.environment
  image_uri          = "${module.ecr_enrich.repository_url}:latest"
  execution_role_arn = module.lambda_role.role_arn
  command            = ["fpl_enrich.handlers.single_enricher.player_summary_handler"]
  timeout            = 900
  memory_size        = 512
  environment_variables = {
    ENV              = var.environment
    DATA_LAKE_BUCKET = module.data_lake.bucket_name
  }
}

module "lambda_enrich_injury_signal" {
  source             = "../../modules/lambda"
  name               = "enrich-injury-signal"
  environment        = var.environment
  image_uri          = "${module.ecr_enrich.repository_url}:latest"
  execution_role_arn = module.lambda_role.role_arn
  command            = ["fpl_enrich.handlers.single_enricher.injury_signal_handler"]
  timeout            = 900
  memory_size        = 512
  environment_variables = {
    ENV              = var.environment
    DATA_LAKE_BUCKET = module.data_lake.bucket_name
  }
}

module "lambda_enrich_sentiment" {
  source             = "../../modules/lambda"
  name               = "enrich-sentiment"
  environment        = var.environment
  image_uri          = "${module.ecr_enrich.repository_url}:latest"
  execution_role_arn = module.lambda_role.role_arn
  command            = ["fpl_enrich.handlers.single_enricher.sentiment_handler"]
  timeout            = 900
  memory_size        = 512
  environment_variables = {
    ENV              = var.environment
    DATA_LAKE_BUCKET = module.data_lake.bucket_name
  }
}

module "lambda_enrich_fixture_outlook" {
  source             = "../../modules/lambda"
  name               = "enrich-fixture-outlook"
  environment        = var.environment
  image_uri          = "${module.ecr_enrich.repository_url}:latest"
  execution_role_arn = module.lambda_role.role_arn
  command            = ["fpl_enrich.handlers.single_enricher.fixture_outlook_handler"]
  timeout            = 900
  memory_size        = 512
  environment_variables = {
    ENV              = var.environment
    DATA_LAKE_BUCKET = module.data_lake.bucket_name
  }
}

module "lambda_merge_enrichments" {
  source             = "../../modules/lambda"
  name               = "merge-enrichments"
  environment        = var.environment
  image_uri          = "${module.ecr_enrich.repository_url}:latest"
  execution_role_arn = module.lambda_role.role_arn
  command            = ["fpl_enrich.handlers.merge_enrichments.lambda_handler"]
  timeout            = 120
  memory_size        = 512
  environment_variables = {
    ENV              = var.environment
    DATA_LAKE_BUCKET = module.data_lake.bucket_name
  }
}

module "lambda_team_fetcher" {
  source             = "../../modules/lambda"
  name               = "team-fetcher"
  environment        = var.environment
  image_uri          = "${module.ecr_data.repository_url}:latest"
  execution_role_arn = module.lambda_role.role_arn
  command            = ["fpl_data.handlers.team_fetcher.lambda_handler"]
  timeout            = 30
  memory_size        = 256
  environment_variables = {
    ENV = var.environment
  }
}

module "lambda_curate_data" {
  source             = "../../modules/lambda"
  name               = "curate-data"
  environment        = var.environment
  image_uri          = "${module.ecr_curate.repository_url}:latest"
  execution_role_arn = module.lambda_role.role_arn
  command            = ["fpl_curate.handlers.curate_all.lambda_handler"]
  timeout            = 120
  memory_size        = 512
  environment_variables = {
    ENV              = var.environment
    DATA_LAKE_BUCKET = module.data_lake.bucket_name
  }
}

module "lambda_agent" {
  source             = "../../modules/lambda"
  name               = "agent"
  environment        = var.environment
  image_uri          = "${module.ecr_agent.repository_url}:latest"
  execution_role_arn = module.lambda_role.role_arn
  # No `command` override — the container image runs uvicorn via its own CMD,
  # with the AWS Lambda Web Adapter extension translating Function URL
  # RESPONSE_STREAM events into local HTTP. See ADR-0010.
  timeout     = 60
  memory_size = 1024
  # Hardware-level backpressure for the public agent endpoint. Replaces API
  # Gateway's 10rps/20-burst throttling after ADR-0010 removed API Gateway
  # from the agent stack. See docs/architecture/security-architecture.md.
  #
  # TEMPORARILY DISABLED — see #121.
  # The fpl-dev account ships with a 10-concurrent-execution Lambda quota
  # (new-account default; AWS standard is 1000). AWS enforces
  # UnreservedConcurrentExecutions >= 10, so reserving any concurrency on a
  # single function fails with InvalidParameterValueException. Restore the
  # line below once the Service Quotas case raises the account quota to 1000.
  # reserved_concurrent_executions = 10
  environment_variables = {
    ENV                            = var.environment
    NEON_SECRET_ARN                = aws_secretsmanager_secret.neon_database_url.arn
    ANTHROPIC_SECRET_ARN           = aws_secretsmanager_secret.anthropic_api_key.arn
    LANGFUSE_PUBLIC_KEY_SECRET_ARN = aws_secretsmanager_secret.langfuse_public_key.arn
    LANGFUSE_SECRET_KEY_SECRET_ARN = aws_secretsmanager_secret.langfuse_secret_key.arn
    USAGE_TABLE_NAME               = aws_dynamodb_table.agent_usage.name
    TEAM_FETCHER_FUNCTION_NAME     = module.lambda_team_fetcher.function_name
  }
}
