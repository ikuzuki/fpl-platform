resource "aws_iam_role" "this" {
  name = "${var.project}-lambda-standard-${var.environment}"

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

resource "aws_iam_role_policy_attachment" "basic_execution" {
  role       = aws_iam_role.this.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "s3" {
  name = "${var.project}-lambda-s3-${var.environment}"
  role = aws_iam_role.this.id

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
        Resource = flatten([
          for arn in var.s3_bucket_arns : [arn, "${arn}/*"]
        ])
      }
    ]
  })
}

resource "aws_iam_role_policy" "ssm_parameters" {
  name = "${var.project}-lambda-ssm-${var.environment}"
  role = aws_iam_role.this.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
        ]
        Resource = "arn:aws:ssm:eu-west-2:*:parameter${var.parameter_path_prefix}/*"
      }
    ]
  })
}

resource "aws_iam_role_policy" "logs" {
  name = "${var.project}-lambda-logs-${var.environment}"
  role = aws_iam_role.this.id

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
        Resource = "arn:aws:logs:eu-west-2:*:log-group:/aws/lambda/${var.project}-*"
      }
    ]
  })
}

resource "aws_iam_role_policy" "sns" {
  count = length(var.sns_topic_arns) > 0 ? 1 : 0
  name  = "${var.project}-lambda-sns-${var.environment}"
  role  = aws_iam_role.this.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = var.sns_topic_arns
      }
    ]
  })
}
