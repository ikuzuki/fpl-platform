output "cloudfront_domain" {
  description = "CloudFront distribution domain name (e.g. d1abc2def3.cloudfront.net). Use this as the dashboard URL."
  value       = aws_cloudfront_distribution.dashboard.domain_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID. Used by CI to run cache invalidations after deploying a new build."
  value       = aws_cloudfront_distribution.dashboard.id
}

output "app_bucket_name" {
  description = "Name of the S3 bucket that holds the React app build output. Upload dist/ here after each build."
  value       = aws_s3_bucket.app.id
}

output "app_bucket_arn" {
  description = "ARN of the S3 app bucket."
  value       = aws_s3_bucket.app.arn
}
