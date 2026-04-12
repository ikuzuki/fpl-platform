# -----------------------------------------------------------------------------
# ECR Repositories (one per service — matches deploy.yml naming: fpl-{name}-dev)
# -----------------------------------------------------------------------------
module "ecr_data" {
  source      = "../../modules/ecr"
  name        = "data"
  environment = var.environment
}

module "ecr_enrich" {
  source      = "../../modules/ecr"
  name        = "enrich"
  environment = var.environment
}

module "ecr_curate" {
  source      = "../../modules/ecr"
  name        = "curate"
  environment = var.environment
}

module "ecr_agent" {
  source      = "../../modules/ecr"
  name        = "agent"
  environment = var.environment
}
