---
paths:
  - "services/etl/dbt/**"
---

# dbt Rules
- Models follow staging → intermediate → marts pattern
- Staging models: 1:1 with source, light transformation only
- Intermediate models: joins and business logic
- Marts models: final tables consumed by dashboards/services
- All models must have at least one test (unique, not_null on keys)
- Use macros for repeated logic (per_90, rolling_average)
