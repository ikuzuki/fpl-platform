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
