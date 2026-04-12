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

resource "aws_sns_topic_policy" "pipeline_alerts" {
  arn = aws_sns_topic.pipeline_alerts.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowEventBridgePublish"
        Effect    = "Allow"
        Principal = { Service = "events.amazonaws.com" }
        Action    = "sns:Publish"
        Resource  = aws_sns_topic.pipeline_alerts.arn
      }
    ]
  })
}

# EventBridge rule: notify on pipeline success or failure
resource "aws_cloudwatch_event_rule" "pipeline_notify" {
  name        = "fpl-pipeline-notify-${var.environment}"
  description = "Fires when the FPL pipeline succeeds, fails, times out, or is aborted"

  event_pattern = jsonencode({
    source      = ["aws.states"]
    detail-type = ["Step Functions Execution Status Change"]
    detail = {
      status          = ["SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"]
      stateMachineArn = [module.pipeline.state_machine_arn]
    }
  })
}

resource "aws_cloudwatch_event_target" "pipeline_notify_sns" {
  rule      = aws_cloudwatch_event_rule.pipeline_notify.name
  target_id = "pipeline-sns-notify"
  arn       = aws_sns_topic.pipeline_alerts.arn

  input_transformer {
    input_paths = {
      status = "$.detail.status"
      name   = "$.detail.name"
      time   = "$.time"
      arn    = "$.detail.executionArn"
    }
    input_template = "\"FPL Pipeline — <status>\\n\\nExecution: <name>\\nTime: <time>\\nARN: <arn>\\n\\nCheck the Step Functions console for full execution details.\""
  }
}
