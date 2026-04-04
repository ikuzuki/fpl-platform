---
name: new-service
description: Scaffold a new service in the monorepo following the standard pattern
disable-model-invocation: true
---

Create a new service called $ARGUMENTS:

1. Create directory structure:
   - services/$ARGUMENTS/src/fpl_$ARGUMENTS/__init__.py
   - services/$ARGUMENTS/src/fpl_$ARGUMENTS/handlers/
   - services/$ARGUMENTS/tests/conftest.py
   - services/$ARGUMENTS/Dockerfile
   - services/$ARGUMENTS/pyproject.toml

2. Copy pyproject.toml template from an existing service, update name and dependencies
3. Create Dockerfile following the multi-stage pattern from services/data/Dockerfile
4. Add the service to the CI workflow path filters in .github/workflows/ci.yml
5. Add to the ruff isort known-first-party list in root pyproject.toml
6. Create initial test file with a passing placeholder test
7. Run `make lint` and `make test-service SERVICE=$ARGUMENTS` to verify
