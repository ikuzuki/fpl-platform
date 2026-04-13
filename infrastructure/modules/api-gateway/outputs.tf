output "api_endpoint" {
  description = "Fully-qualified API endpoint (e.g. https://abc123.execute-api.eu-west-2.amazonaws.com). Use directly for testing before CloudFront is wired up."
  value       = aws_apigatewayv2_api.this.api_endpoint
}

output "api_domain" {
  description = "Bare host of the API endpoint (scheme stripped). Used as the domain_name on a CloudFront custom origin."
  value       = replace(aws_apigatewayv2_api.this.api_endpoint, "https://", "")
}

output "api_id" {
  description = "ID of the HTTP API."
  value       = aws_apigatewayv2_api.this.id
}

output "api_execution_arn" {
  description = "Execution ARN of the HTTP API. Used for scoping Lambda invoke permissions."
  value       = aws_apigatewayv2_api.this.execution_arn
}
