terraform {
  required_version = ">= 1.3.0"

  backend "s3" {
    bucket         = "fpl-dev-tf-state"
    key            = "dev/terraform.tfstate"
    region         = "eu-west-2"
    dynamodb_table = "fpl-dev-tf-lock-table"
    encrypt        = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "eu-west-2"

  default_tags {
    tags = {
      Repository  = "fpl-platform"
      Environment = var.environment
      ManagedBy   = "terraform"
      Project     = "fpl-platform"
    }
  }
}

# -----------------------------------------------------------------------------
# ECR Repositories (one per service — matches deploy.yml naming: fpl-{name}-dev)
# -----------------------------------------------------------------------------
module "ecr_data" {
  source      = "../../modules/ecr"
  name        = "data"
  environment = var.environment
}

module "ecr_enrich" {
  source      = "../../modules/ecr"
  name        = "enrich"
  environment = var.environment
}

module "ecr_curate" {
  source      = "../../modules/ecr"
  name        = "curate"
  environment = var.environment
}

module "ecr_agent" {
  source      = "../../modules/ecr"
  name        = "agent"
  environment = var.environment
}

# -----------------------------------------------------------------------------
# S3 Data Lake
# -----------------------------------------------------------------------------
module "data_lake" {
  source      = "../../modules/s3-data-lake"
  environment = var.environment
}

module "cost_reports" {
  source                     = "../../modules/s3-data-lake"
  name                       = "cost-reports"
  environment                = var.environment
  enable_data_lake_lifecycle = false
}

# -----------------------------------------------------------------------------
# SNS Alerts
# -----------------------------------------------------------------------------
resource "aws_sns_topic" "pipeline_alerts" {
  name = "fpl-pipeline-alerts-${var.environment}"
}

resource "aws_sns_topic_subscription" "email_alert" {
  topic_arn = aws_sns_topic.pipeline_alerts.arn
  protocol  = "email"
  endpoint  = var.notification_email
}

# -----------------------------------------------------------------------------
# Secrets Manager
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

# -----------------------------------------------------------------------------
# Lambda Execution Role (shared across all Lambdas)
# -----------------------------------------------------------------------------
resource "aws_iam_role" "lambda_standard" {
  name = "fpl-lambda-standard-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_standard.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_s3" {
  name = "fpl-lambda-s3-${var.environment}"
  role = aws_iam_role.lambda_standard.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "s3:DeleteObject",
        ]
        Resource = [
          module.data_lake.bucket_arn,
          "${module.data_lake.bucket_arn}/*",
          module.cost_reports.bucket_arn,
          "${module.cost_reports.bucket_arn}/*",
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_secrets" {
  name = "fpl-lambda-secrets-${var.environment}"
  role = aws_iam_role.lambda_standard.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = "arn:aws:secretsmanager:eu-west-2:*:secret:/fpl-platform/${var.environment}/*"
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_logs" {
  name = "fpl-lambda-logs-${var.environment}"
  role = aws_iam_role.lambda_standard.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:eu-west-2:*:log-group:/aws/lambda/fpl-*"
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# Lambda Functions
# -----------------------------------------------------------------------------
module "lambda_fpl_collector" {
  source             = "../../modules/lambda"
  name               = "fpl-api-collector"
  environment        = var.environment
  image_uri          = "${module.ecr_data.repository_url}:latest"
  execution_role_arn = aws_iam_role.lambda_standard.arn
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
  execution_role_arn = aws_iam_role.lambda_standard.arn
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
  execution_role_arn = aws_iam_role.lambda_standard.arn
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
  execution_role_arn = aws_iam_role.lambda_standard.arn
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
  execution_role_arn = aws_iam_role.lambda_standard.arn
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
  execution_role_arn = aws_iam_role.lambda_standard.arn
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
  execution_role_arn = aws_iam_role.lambda_standard.arn
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
  execution_role_arn = aws_iam_role.lambda_standard.arn
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
  execution_role_arn = aws_iam_role.lambda_standard.arn
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
  execution_role_arn = aws_iam_role.lambda_standard.arn
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
  execution_role_arn = aws_iam_role.lambda_standard.arn
  command            = ["fpl_enrich.handlers.merge_enrichments.lambda_handler"]
  timeout            = 120
  memory_size        = 512
  environment_variables = {
    ENV              = var.environment
    DATA_LAKE_BUCKET = module.data_lake.bucket_name
  }
}

module "lambda_curate_data" {
  source             = "../../modules/lambda"
  name               = "curate-data"
  environment        = var.environment
  image_uri          = "${module.ecr_curate.repository_url}:latest"
  execution_role_arn = aws_iam_role.lambda_standard.arn
  command            = ["fpl_curate.handlers.curate_all.lambda_handler"]
  timeout            = 120
  memory_size        = 512
  environment_variables = {
    ENV              = var.environment
    DATA_LAKE_BUCKET = module.data_lake.bucket_name
  }
}

# -----------------------------------------------------------------------------
# Step Functions Pipeline
# -----------------------------------------------------------------------------
module "pipeline" {
  source      = "../../modules/step-function"
  name        = "collection-pipeline"
  environment = var.environment

  definition = templatefile("../../step_function_definitions/fpl-collection-pipeline.json.tpl", {
    lambda_arn_resolve_gameweek       = module.lambda_resolve_gameweek.function_arn
    lambda_arn_fpl_collector          = module.lambda_fpl_collector.function_arn
    lambda_arn_understat_collector    = module.lambda_understat_collector.function_arn
    lambda_arn_news_collector         = module.lambda_news_collector.function_arn
    lambda_arn_validator              = module.lambda_validator.function_arn
    lambda_arn_transform              = module.lambda_transform.function_arn
    lambda_arn_enrich_player_summary  = module.lambda_enrich_player_summary.function_arn
    lambda_arn_enrich_injury_signal   = module.lambda_enrich_injury_signal.function_arn
    lambda_arn_enrich_sentiment       = module.lambda_enrich_sentiment.function_arn
    lambda_arn_enrich_fixture_outlook = module.lambda_enrich_fixture_outlook.function_arn
    lambda_arn_merge_enrichments      = module.lambda_merge_enrichments.function_arn
    lambda_arn_curate_data            = module.lambda_curate_data.function_arn
  })

  lambda_arns = [
    module.lambda_resolve_gameweek.function_arn,
    module.lambda_fpl_collector.function_arn,
    module.lambda_understat_collector.function_arn,
    module.lambda_news_collector.function_arn,
    module.lambda_validator.function_arn,
    module.lambda_transform.function_arn,
    module.lambda_enrich_player_summary.function_arn,
    module.lambda_enrich_injury_signal.function_arn,
    module.lambda_enrich_sentiment.function_arn,
    module.lambda_enrich_fixture_outlook.function_arn,
    module.lambda_merge_enrichments.function_arn,
    module.lambda_curate_data.function_arn,
  ]
}

# -----------------------------------------------------------------------------
# EventBridge Schedule — Tuesday 8am UTC (after Monday GW deadline)
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# Web Hosting — S3 + CloudFront for the React dashboard
# -----------------------------------------------------------------------------
module "web_hosting" {
  source = "../../modules/web-hosting"

  environment           = var.environment
  data_lake_bucket_name = module.data_lake.bucket_name
  data_lake_bucket_arn  = module.data_lake.bucket_arn
}

# -----------------------------------------------------------------------------
# EventBridge Schedule — Tuesday 8am UTC (after Monday GW deadline)
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_event_rule" "weekly_pipeline" {
  name                = "fpl-weekly-pipeline-${var.environment}"
  description         = "Trigger FPL pipeline every Tuesday at 8am UTC"
  schedule_expression = "cron(0 8 ? * TUE *)"
}

resource "aws_cloudwatch_event_target" "pipeline_target" {
  rule     = aws_cloudwatch_event_rule.weekly_pipeline.name
  arn      = module.pipeline.state_machine_arn
  role_arn = aws_iam_role.eventbridge_sfn.arn

  # gameweek=0 triggers auto-resolution via the FPL API (ResolveGameweek).
  # gameweek>0 skips resolution and runs that specific gameweek (backfill mode).
  input = jsonencode({
    season            = "2025-26"
    gameweek          = 0
    last_processed_gw = 0
    force             = false
  })
}

resource "aws_iam_role" "eventbridge_sfn" {
  name = "fpl-eventbridge-sfn-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "eventbridge_sfn_start" {
  name = "fpl-eventbridge-start-sfn-${var.environment}"
  role = aws_iam_role.eventbridge_sfn.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["states:StartExecution"]
        Resource = module.pipeline.state_machine_arn
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_sns" {
  name = "fpl-lambda-sns-${var.environment}"
  role = aws_iam_role.lambda_standard.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = aws_sns_topic.pipeline_alerts.arn
      }
    ]
  })
}
