output "state_bucket_name" {
  description = "Name of the Terraform state S3 bucket"
  value       = aws_s3_bucket.tf_state.id
}

output "lock_table_name" {
  description = "Name of the DynamoDB lock table"
  value       = aws_dynamodb_table.tf_lock.name
}

output "oidc_provider_arn" {
  description = "ARN of the GitHub OIDC identity provider"
  value       = aws_iam_openid_connect_provider.github.arn
}

output "cicd_role_arn" {
  description = "ARN of the CI/CD IAM role"
  value       = aws_iam_role.cicd.arn
}
