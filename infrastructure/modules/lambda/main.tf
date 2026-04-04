resource "aws_lambda_function" "this" {
  function_name = "${var.project}-${var.environment}-${var.name}"
  package_type  = "Image"
  image_uri     = var.image_uri
  role          = var.execution_role_arn != null ? var.execution_role_arn : aws_iam_role.lambda[0].arn
  timeout       = var.timeout
  memory_size   = var.memory_size

  environment {
    variables = var.environment_variables
  }
}

# Internal IAM role — only created when no external role is provided
resource "aws_iam_role" "lambda" {
  count = var.execution_role_arn == null ? 1 : 0
  name  = "${var.project}-${var.environment}-${var.name}-role"

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

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  count      = var.execution_role_arn == null ? 1 : 0
  role       = aws_iam_role.lambda[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${aws_lambda_function.this.function_name}"
  retention_in_days = 30
}
