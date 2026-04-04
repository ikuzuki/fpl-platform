# ADR-0002: Terraform over CDK

## Status
Accepted

## Context
We need Infrastructure as Code (IaC) for managing AWS resources. The two main options are:
- **Terraform (HCL)** — cloud-agnostic, declarative, large community
- **AWS CDK (Python)** — AWS-specific, imperative, uses familiar Python

## Decision
Use Terraform with HCL for all infrastructure management.

## Consequences
**Easier:**
- More portable — not locked to AWS (though we only use AWS today)
- Larger community and more learning resources
- Stronger hiring signal — Terraform is the most widely used IaC tool
- HCL is widely known and readable by non-Python developers
- terraform-docs auto-generates module documentation

**Harder:**
- CDK would have given us type safety and the ability to write infrastructure in Python
- CDK's constructs can abstract more boilerplate than raw Terraform modules
- Two languages in the project (HCL + Python) instead of one (Python for everything)
