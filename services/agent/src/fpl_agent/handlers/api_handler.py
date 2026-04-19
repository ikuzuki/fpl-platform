"""Lambda entry point — adapts the FastAPI app to API Gateway via Mangum.

Mangum translates API Gateway v2 (HTTP API) events into ASGI requests the
FastAPI app already understands, and translates responses back. The
``lifespan='on'`` setting ensures our ``@asynccontextmanager`` lifespan
runs on the first invocation so the Neon pool, Anthropic client, compiled
graph, and budget/rate-limit singletons are set up before any request is
served. Subsequent warm invocations reuse the same event loop / app state.
"""

from __future__ import annotations

import logging

from mangum import Mangum

from fpl_agent.api import app

logger = logging.getLogger()
logger.setLevel(logging.INFO)

lambda_handler = Mangum(app, lifespan="on")
