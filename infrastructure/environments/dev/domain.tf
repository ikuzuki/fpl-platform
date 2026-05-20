# -----------------------------------------------------------------------------
# Custom domain — fpl.isseikuzuki.co.uk on the dashboard CloudFront distribution
#
# The apex isseikuzuki.co.uk + www points at the personal website (separate
# CloudFront distribution, separate Terraform state in the `website` repo). The
# Route 53 hosted zone for isseikuzuki.co.uk lives in the same AWS account, so
# this stack looks it up via data source and writes the fpl. subdomain records
# into it.
#
# ACM is region-bound: CloudFront only reads certs from us-east-1, so the cert
# resource uses an aliased provider while the rest of the stack stays in
# eu-west-2 (London).
# -----------------------------------------------------------------------------

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = local.common_tags
  }
}

# Hosted zone created by Route 53 Domains when isseikuzuki.co.uk was registered
# in the website repo's setup. Looked up by name so this stack does not depend
# on the website repo's Terraform state.
data "aws_route53_zone" "primary" {
  name = "isseikuzuki.co.uk"
}

resource "aws_acm_certificate" "dashboard" {
  provider = aws.us_east_1

  domain_name       = "fpl.isseikuzuki.co.uk"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

# DNS validation: ACM publishes a CNAME challenge, Terraform writes it into the
# hosted zone, ACM checks it, cert flips to ISSUED. Single-domain cert so
# there is one validation record (no for_each needed, but kept for symmetry
# with the website repo's pattern and easy extension to additional SANs later).
resource "aws_route53_record" "dashboard_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.dashboard.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = data.aws_route53_zone.primary.zone_id
}

# Blocks downstream until ACM has validated the cert. The CloudFront viewer_certificate
# block depends on this resource's certificate_arn output, so the distribution
# update only attempts the new cert after it is ISSUED.
resource "aws_acm_certificate_validation" "dashboard" {
  provider = aws.us_east_1

  certificate_arn         = aws_acm_certificate.dashboard.arn
  validation_record_fqdns = [for record in aws_route53_record.dashboard_cert_validation : record.fqdn]
}

# A and AAAA alias records — apex pattern would need IPv4+IPv6, fpl. subdomain
# uses the same convention for parity with the website repo. Both target the
# dashboard's CloudFront distribution (one distribution serves both the React
# SPA via the `app` origin and the agent API via `/api/agent/*`).
resource "aws_route53_record" "fpl_a" {
  zone_id = data.aws_route53_zone.primary.zone_id
  name    = "fpl.isseikuzuki.co.uk"
  type    = "A"

  alias {
    name                   = module.web_hosting.cloudfront_domain
    zone_id                = module.web_hosting.cloudfront_distribution_hosted_zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "fpl_aaaa" {
  zone_id = data.aws_route53_zone.primary.zone_id
  name    = "fpl.isseikuzuki.co.uk"
  type    = "AAAA"

  alias {
    name                   = module.web_hosting.cloudfront_domain
    zone_id                = module.web_hosting.cloudfront_distribution_hosted_zone_id
    evaluate_target_health = false
  }
}
