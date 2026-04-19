output "dashboard_url" {
  description = "CloudFront URL for the FPL Pulse dashboard"
  value       = "https://${module.web_hosting.cloudfront_domain}"
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID — used by CI to invalidate the cache after a new build is deployed"
  value       = module.web_hosting.cloudfront_distribution_id
}

output "app_bucket_name" {
  description = "S3 bucket to upload the Vite build output (dist/) to"
  value       = module.web_hosting.app_bucket_name
}

output "agent_api_endpoint" {
  description = "Direct Lambda Function URL for the Scout Agent. Use this for testing before CloudFront propagates. Production traffic goes via /api/agent/* on the dashboard URL."
  value       = aws_lambda_function_url.agent.function_url
}
