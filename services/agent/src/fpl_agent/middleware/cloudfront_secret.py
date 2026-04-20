"""Shared-secret header middleware — restrict the Function URL to CloudFront.

The agent's Lambda Function URL is ``AuthType = NONE`` + ``Principal = "*"``
because Lambda OAC doesn't work for our POST /chat path (OAC requires the
client to compute ``x-amz-content-sha256`` on POST bodies, which browsers do
not do — see ADR-0010 revision). Instead of OAC we rely on CloudFront to
inject a high-entropy header on every origin request; this middleware rejects
any request that doesn't carry it.

Threat model: the Function URL's domain is discoverable (it appears in
CloudFront's origin config and AWS billing records), so without this gate
an attacker could hit the Lambda directly and bypass CloudFront — evicting
WAF rules, rate limits, and observability in the process. The shared secret
makes the Function URL effectively unreachable except via our distribution.

Secret handling:
* The value is generated once by Terraform (``random_password``), stored in
  Secrets Manager, injected into the CloudFront origin header config, and
  read back into the Lambda env at cold-start.
* Exempts ``/health`` so Lambda Web Adapter's readiness probe (which runs
  inside the container before traffic ever arrives) can't deadlock against
  a missing secret.
* Constant-time comparison (``hmac.compare_digest``) so response time is
  invariant to how much of the secret an attacker got right.
"""

from __future__ import annotations

import hmac
import logging
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Paths that bypass the gate. ``/health`` is required for LWA's in-container
# readiness probe — it runs before external traffic, so CloudFront's header
# is not yet in scope. Keep this list deliberately tiny.
_EXEMPT_PATHS: frozenset[str] = frozenset({"/health"})


class CloudFrontSecretMiddleware(BaseHTTPMiddleware):
    """Reject requests that don't carry the CloudFront-injected secret header.

    The middleware is a no-op when ``secret_value`` is empty — local dev /
    unit tests don't need the header. Deployments always wire it via
    Terraform, so the production path always enforces.
    """

    def __init__(
        self,
        app: Callable[..., Awaitable[Response]],
        *,
        header_name: str,
        secret_value: str,
    ) -> None:
        super().__init__(app)
        self._header_name = header_name
        self._secret_value = secret_value

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not self._secret_value:
            return await call_next(request)
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        supplied = request.headers.get(self._header_name, "")
        if not supplied or not hmac.compare_digest(supplied, self._secret_value):
            # Deliberately vague body — don't leak which part failed (missing
            # vs wrong value vs wrong header name). 401 rather than 403: the
            # request is structurally fine, it just isn't authenticated as
            # originating from CloudFront.
            logger.warning(
                "rejected request without %s header: path=%s", self._header_name, request.url.path
            )
            return JSONResponse({"detail": "unauthorized"}, status_code=401)

        return await call_next(request)
