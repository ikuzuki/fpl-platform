resource "aws_sfn_state_machine" "this" {
  name     = "${var.project}-${var.environment}-${var.name}"
  role_arn = aws_iam_role.step_function.arn

  definition = var.definition
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
