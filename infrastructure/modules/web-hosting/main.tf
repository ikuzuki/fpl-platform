# -----------------------------------------------------------------------------
# S3 bucket — React app static assets (Vite build output)
# -----------------------------------------------------------------------------
resource "aws_s3_bucket" "app" {
  bucket = "fpl-dashboard-${var.environment}"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "app" {
  bucket = aws_s3_bucket.app.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "app" {
  bucket = aws_s3_bucket.app.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# -----------------------------------------------------------------------------
# CloudFront Origin Access Controls
# OAC replaces OAI — allows CloudFront to sign requests to private S3 buckets.
# -----------------------------------------------------------------------------
resource "aws_cloudfront_origin_access_control" "app" {
  name                              = "fpl-dashboard-app-${var.environment}"
  description                       = "OAC for React app bucket (fpl-dashboard-${var.environment})"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_origin_access_control" "data" {
  name                              = "fpl-dashboard-data-${var.environment}"
  description                       = "OAC for data lake public/ prefix (${var.data_lake_bucket_name})"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# -----------------------------------------------------------------------------
# CloudFront distribution
#
# Two origins:
#   app  — S3 app bucket (React SPA)
#   data — S3 data lake bucket, origin path /public
#          so /api/v1/player_dashboard.json → s3://fpl-data-lake-{env}/public/api/v1/player_dashboard.json
#
# Behaviours:
#   /api/v1/*  → data origin  (no caching — weekly data, but cache_policy_id keeps it simple)
#   /*         → app origin   (long cache; invalidated on deploy)
# -----------------------------------------------------------------------------
resource "aws_cloudfront_distribution" "dashboard" {
  enabled             = true
  default_root_object = "index.html"
  price_class         = var.price_class
  comment             = "FPL Pulse dashboard — ${var.environment}"

  # --- App bucket origin ---
  origin {
    origin_id                = "app"
    domain_name              = aws_s3_bucket.app.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.app.id
  }

  # --- Data lake origin (public/ prefix maps to /api/v1 path) ---
  origin {
    origin_id                = "data"
    domain_name              = "${var.data_lake_bucket_name}.s3.eu-west-2.amazonaws.com"
    origin_path              = "/public"
    origin_access_control_id = aws_cloudfront_origin_access_control.data.id
  }

  # --- /api/v1/* → data lake (short cache — data updates weekly) ---
  ordered_cache_behavior {
    path_pattern           = "/api/v1/*"
    target_origin_id       = "data"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    # AWS managed cache policy: CachingOptimized (86400s default TTL)
    # Data updates weekly so a 24h cache is acceptable; pipeline invalidates on deploy
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"
  }

  # --- /* → app bucket (long cache; deploy triggers invalidation) ---
  default_cache_behavior {
    target_origin_id       = "app"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    # AWS managed cache policy: CachingOptimized
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"
  }

  # React Router: return index.html for any 403/404 so client-side routing works
  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

# -----------------------------------------------------------------------------
# S3 bucket policy — app bucket
# Grants CloudFront OAC permission to read all objects.
# -----------------------------------------------------------------------------
resource "aws_s3_bucket_policy" "app" {
  bucket = aws_s3_bucket.app.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontOAC"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.app.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.dashboard.arn
          }
        }
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# S3 bucket policy — data lake bucket (public/ prefix only)
# Adds to the existing data lake bucket — the data lake module has no policy.
# Scoped to public/* so CloudFront cannot reach raw/, clean/, enriched/, etc.
# -----------------------------------------------------------------------------
resource "aws_s3_bucket_policy" "data_lake_public" {
  bucket = var.data_lake_bucket_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontOACPublicPrefix"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${var.data_lake_bucket_arn}/public/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.dashboard.arn
          }
        }
      }
    ]
  })
}
