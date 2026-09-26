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
    lambda_arn_sync_embeddings        = module.lambda_sync_embeddings.function_arn
    sns_topic_arn_pipeline_alerts     = aws_sns_topic.pipeline_alerts.arn
  })

  sns_topic_arns = [aws_sns_topic.pipeline_alerts.arn]

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
    module.lambda_sync_embeddings.function_arn,
  ]
}

# -----------------------------------------------------------------------------
# EventBridge Schedule — daily 8am UTC
#
# The FPL calendar is not weekly: midweek rounds finish and are superseded
# within a single week, so a weekly trigger silently never processes them.
# Daily runs pick every round up within 24h, and ResolveGameweek derives what
# has already been processed from S3, so a day with nothing new costs one
# sub-second Lambda invocation.
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_event_rule" "weekly_pipeline" {
  name                = "fpl-weekly-pipeline-${var.environment}"
  description         = "Trigger FPL pipeline daily at 8am UTC; ResolveGameweek no-ops until a new gameweek finishes"
  schedule_expression = "cron(0 8 * * ? *)"
}

resource "aws_cloudwatch_event_target" "pipeline_target" {
  rule     = aws_cloudwatch_event_rule.weekly_pipeline.name
  arn      = module.pipeline.state_machine_arn
  role_arn = aws_iam_role.eventbridge_sfn.arn

  # gameweek=0 triggers auto-resolution via the FPL API (ResolveGameweek).
  # gameweek>0 skips resolution and runs that specific gameweek (backfill mode).
  # season and last_processed_gw are both omitted so ResolveGameweek derives them
  # — season from the current date, last_processed_gw from the completed runs in
  # S3. Pass either explicitly only when invoking the state machine by hand.
  input = jsonencode({
    gameweek = 0
    force    = false
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
