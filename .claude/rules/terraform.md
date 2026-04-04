---
paths:
  - "infrastructure/**/*.tf"
  - "infrastructure/**/*.tfvars"
---

# Terraform Rules
- All modules must have: main.tf, variables.tf, outputs.tf, README.md
- Use terraform-docs to auto-generate module docs
- Variable descriptions are mandatory
- Use validation blocks on variables where possible
- Always use the common_tags local from tags.tf
- State backend config lives in environments/{env}/
- Module sources reference infrastructure/modules/{name}
