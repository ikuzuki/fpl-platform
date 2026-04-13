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

  # --- Agent API origin (conditional — only when agent_api_domain is set) ---
  # API Gateway is a standard HTTPS endpoint, so we use custom_origin_config
  # (OAC is S3-only). Host header is stripped via AllViewerExceptHostHeader
  # policy on the cache behaviour below.
  dynamic "origin" {
    for_each = var.agent_api_domain != "" ? [1] : []
    content {
      origin_id   = "agent_api"
      domain_name = var.agent_api_domain

      custom_origin_config {
        http_port              = 80
        https_port             = 443
        origin_protocol_policy = "https-only"
        origin_ssl_protocols   = ["TLSv1.2"]
      }
    }
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

  # --- /api/agent/* → agent API Gateway (no caching; SSE streams must pass through) ---
  dynamic "ordered_cache_behavior" {
    for_each = var.agent_api_domain != "" ? [1] : []
    content {
      path_pattern           = "/api/agent/*"
      target_origin_id       = "agent_api"
      viewer_protocol_policy = "redirect-to-https"
      allowed_methods        = ["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"]
      cached_methods         = ["GET", "HEAD"]
      compress               = true

      # AWS managed: CachingDisabled — streaming LLM responses must not be cached
      cache_policy_id = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
      # AWS managed: AllViewerExceptHostHeader — forwards everything (auth, body, query)
      # but strips Host so API Gateway accepts the request.
      origin_request_policy_id = "b689b0a8-53d0-40ab-baf2-68738e2966ac"

      # Strip the /api/agent prefix before forwarding to API Gateway.
      # CloudFront's path_pattern selects which origin to use but doesn't
      # rewrite the URL — so without this function, API Gateway would
      # receive GET /api/agent/health instead of GET /health and 404.
      function_association {
        event_type   = "viewer-request"
        function_arn = aws_cloudfront_function.strip_agent_prefix[0].arn
      }
    }
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
# CloudFront Function — strip /api/agent prefix before forwarding to API Gateway
#
# CloudFront's ordered_cache_behavior.path_pattern selects the origin but does
# not modify the URL. API Gateway's routes are /health and /chat (no prefix),
# so the prefix has to be stripped on the way out.
#
# Runs at viewer-request (every request), ~1ms latency, free up to 10M/month.
# -----------------------------------------------------------------------------
resource "aws_cloudfront_function" "strip_agent_prefix" {
  count = var.agent_api_domain != "" ? 1 : 0

  name    = "fpl-${var.environment}-strip-agent-prefix"
  runtime = "cloudfront-js-2.0"
  publish = true
  comment = "Strips /api/agent from the request URI before forwarding to API Gateway"

  code = <<-EOT
    function handler(event) {
      var request = event.request;
      request.uri = request.uri.replace(/^\/api\/agent/, '');
      if (request.uri === '') {
        request.uri = '/';
      }
      return request;
    }
  EOT
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
