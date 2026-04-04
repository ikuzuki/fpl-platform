resource "aws_sfn_state_machine" "this" {
  name     = "${var.project}-${var.environment}-${var.name}"
  role_arn = aws_iam_role.step_function.arn

  definition = var.definition

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.step_function.arn}:*"
    include_execution_data = true
    level                  = "ERROR"
  }
}

resource "aws_cloudwatch_log_group" "step_function" {
  name              = "/aws/states/${var.project}-${var.environment}-${var.name}"
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role" "step_function" {
  name = "${var.project}-${var.environment}-${var.name}-sfn-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "step_function_lambda" {
  name = "${var.project}-${var.environment}-${var.name}-lambda-invoke"
  role = aws_iam_role.step_function.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = var.lambda_arns
      }
    ]
  })
}

resource "aws_iam_role_policy" "step_function_logs" {
  name = "${var.project}-${var.environment}-${var.name}-logs"
  role = aws_iam_role.step_function.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups",
        ]
        Resource = "*"
      }
    ]
  })
}
