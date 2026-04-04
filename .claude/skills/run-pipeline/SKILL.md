---
name: run-pipeline
description: Run the FPL data pipeline locally for a specific gameweek
disable-model-invocation: true
---

Run the FPL pipeline for gameweek $ARGUMENTS:

1. Check AWS profile is set to fpl-dev
2. Run collector: `python -m fpl_data.handlers.fpl_api_collector --season 2025-26 --gameweek $ARGUMENTS`
3. Run validator: `python -m fpl_data.handlers.data_validator --season 2025-26 --gameweek $ARGUMENTS`
4. Run transformer: `python -m fpl_etl.scripts.transform --season 2025-26 --gameweek $ARGUMENTS`
5. Run enrichment: `python -m fpl_enrich.handlers.enricher --season 2025-26 --gameweek $ARGUMENTS`
6. Report: show record counts at each layer and any DLQ entries
