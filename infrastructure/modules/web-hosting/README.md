# web-hosting

Hosts the FPL Pulse React dashboard on S3 + CloudFront.

## Architecture

```
Browser
  └── CloudFront (d1abc.cloudfront.net)
        ├── /api/v1/*  → S3 data lake (fpl-data-lake-{env}/public/)
        └── /*         → S3 app bucket (fpl-dashboard-{env}/)
```

Two origins, one distribution:

- **App bucket** (`fpl-dashboard-{env}`) — holds the Vite build output (`dist/`). All objects private; CloudFront reads via OAC.
- **Data lake** (`fpl-data-lake-{env}`) — the existing data lake bucket. CloudFront is granted read access to the `public/` prefix only (raw/, clean/, enriched/ are unreachable). The origin path `/public` means CloudFront maps `/api/v1/player_dashboard.json` → `s3://.../public/api/v1/player_dashboard.json`.

React Router SPA routing is handled by returning `index.html` on 403/404 with HTTP 200.

## Deploying the dashboard

```bash
# 1. Build
cd web/dashboard && npm run build

# 2. Upload to S3
aws s3 sync dist/ s3://$(terraform -chdir=infrastructure/environments/dev output -raw app_bucket_name) --delete

# 3. Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id $(terraform -chdir=infrastructure/environments/dev output -raw cloudfront_distribution_id) \
  --paths "/*"
```

## Inputs

| Name | Description | Type | Default |
|------|-------------|------|---------|
| `environment` | Deployment environment (dev/prod) | `string` | — |
| `data_lake_bucket_name` | Name of the existing data lake S3 bucket | `string` | — |
| `data_lake_bucket_arn` | ARN of the existing data lake S3 bucket | `string` | — |
| `price_class` | CloudFront price class | `string` | `PriceClass_100` |

## Outputs

| Name | Description |
|------|-------------|
| `cloudfront_domain` | Dashboard URL (e.g. `d1abc.cloudfront.net`) |
| `cloudfront_distribution_id` | Distribution ID for cache invalidation |
| `app_bucket_name` | S3 bucket name to upload the build to |
| `app_bucket_arn` | ARN of the app S3 bucket |
