output "function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.this.function_name
}

output "function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.this.arn
}

output "invoke_arn" {
  description = "Invoke ARN of the Lambda function"
  value       = aws_lambda_function.this.invoke_arn
}

output "role_arn" {
  description = "ARN of the Lambda execution role"
  value       = var.execution_role_arn != null ? var.execution_role_arn : aws_iam_role.lambda[0].arn
}

output "role_name" {
  description = "Name of the Lambda execution role (null when using external role)"
  value       = var.execution_role_arn != null ? null : aws_iam_role.lambda[0].name
}
