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
  timeout = 60
  # 3008 MB gets the agent close to 2 vCPU (Lambda scales CPU linearly with
  # memory, full 2 vCPU at ~3584 MB). At 1024 MB (~0.57 vCPU) cold-start was
  # ~27s dominated by Python imports (LangGraph + pgvector + asyncpg +
  # langfuse + anthropic + FastAPI); Lambda's 10s init cap tripped, the
  # container was force-restarted, and LWA's /health probe only went green
  # ~28s in — outside CloudFront's 30s origin-response window, so browser
  # requests saw 502s intermittently. The Lambda's steady-state memory
  # usage stays well under 300 MB; this knob is bought purely for the CPU.
  memory_size = 3008
  # Hardware-level backpressure for the public agent endpoint. Replaces API
  # Gateway's 10rps/20-burst throttling after ADR-0010 removed API Gateway
  # from the agent stack. See docs/architecture/security-architecture.md.
  reserved_concurrent_executions = 10
  # Secrets are fetched at cold-start by path (``/fpl-platform/{env}/<name>``)
  # via ``fpl_lib.secrets.resolve_secret_to_env`` — the ``lambda_role`` policy
  # already scopes ``GetSecretValue`` to that prefix, so the only per-Lambda
  # wiring needed is ``ENV``. Adding a new secret is a pure Terraform +
  # resolver-call change; no new env var here.
  environment_variables = {
    ENV                        = var.environment
    AGENT_USAGE_TABLE          = aws_dynamodb_table.agent_usage.name
    SQUAD_CACHE_TABLE          = aws_dynamodb_table.squad_cache.name
    TEAM_FETCHER_FUNCTION_NAME = module.lambda_team_fetcher.function_name

    # Langfuse tracing is on with the SDK pinned to tight timeouts so a slow
    # or unreachable Langfuse endpoint adds at most ~5s to the response path
    # (vs. the 60s default that blew up /team in #133). Matches the pattern
    # Langfuse maintainers recommend for low-traffic Lambda deployments —
    # ADOT Lambda Extension is the production answer at higher RPS and stays
    # deferred pending observed trace-drop rate (see ADR-0005 revision).
    LANGFUSE_TRACING_ENABLED = "true"
    # OTLP exporter: give up on any single HTTP upload to cloud.langfuse.com
    # after 3s (default 10s). Below the 5s BSP cap so one retry can still fit.
    OTEL_EXPORTER_OTLP_TIMEOUT = "3000"
    # BatchSpanProcessor: hard ceiling on the entire flush including retries.
    # Lambda freezes the process the instant the handler returns, so any
    # flush() call on the response thread blocks up to this value.
    OTEL_BSP_EXPORT_TIMEOUT = "5000"
    # Emit each span immediately — we'd rather pay 1 flush per span at low
    # traffic than batch spans that could be stranded in the queue when the
    # container freezes. At 1-2 rpm the upload cost is negligible.
    LANGFUSE_FLUSH_AT       = "1"
    LANGFUSE_FLUSH_INTERVAL = "1000"

    # Shared-secret gate: CloudFront injects this header on every origin
    # request (terraform-managed, stored in Secrets Manager). The FastAPI
    # middleware rejects requests that don't carry it, making the Function
    # URL effectively unreachable except via CloudFront. Replaces the
    # AWS_IAM + OAC approach rejected in the ADR-0010 revision — OAC requires
    # the browser to compute x-amz-content-sha256 for POST bodies, which it
    # doesn't do. See docs/architecture/security-architecture.md.
    CLOUDFRONT_SECRET_HEADER_NAME = "X-CloudFront-Secret"
  }
}
