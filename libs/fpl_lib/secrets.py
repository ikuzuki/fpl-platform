"""Shared SSM Parameter Store → environment variable resolver.

Every Lambda built on this platform needs the same cold-start ritual: read
a few values from SSM Parameter Store, stash them in ``os.environ`` so
that downstream SDKs (Anthropic, asyncpg, Langfuse, …) can pick them up
via their native env-var conventions. Keeping the fetch here — one
helper, one SSM client, one convention — means:

* A new parameter gets added in one place (Terraform) and is accessible
  by name (``"anthropic-api-key"``) rather than by a per-Lambda
  ``*_PARAMETER_ARN`` env var.
* The IAM policy on ``lambda_role`` already scopes ``GetParameter`` to
  ``arn:...:parameter/fpl-platform/{env}/*``; callers that respect the
  path convention inherit access with no additional wiring.
* Failure modes are consistent: the helper raises, the caller decides
  whether the missing parameter is fatal (Anthropic at graph start) or
  tolerable (Neon for the health-only boot path).

We use SSM Parameter Store (SecureString) over Secrets Manager because
the platform doesn't use rotation, cross-account replication, or
resource policies — and Parameter Store is free at our parameter count
where Secrets Manager charges $0.40/parameter/month flat. See ADR-0011
for the trade-off.

No module-level boto3 client — building the client inside the function
keeps tests simple (they patch ``fpl_lib.secrets.boto3.client``) and
avoids paying for a session on Lambdas that never call this.
"""

from __future__ import annotations

import logging
import os

import boto3

logger = logging.getLogger(__name__)

DEFAULT_SECRET_PREFIX = "/fpl-platform"
DEFAULT_REGION = "eu-west-2"


def resolve_secret_to_env(
    environment: str,
    name: str,
    target_var: str,
    *,
    region: str = DEFAULT_REGION,
    secret_prefix: str = DEFAULT_SECRET_PREFIX,
) -> None:
    """Fetch ``{secret_prefix}/{environment}/{name}`` and export as ``target_var``.

    Idempotent: if ``target_var`` is already populated (local dev, tests,
    or a previous call in the same process) the function returns without
    contacting AWS. This keeps local development cheap — set the plain env
    var in ``.env.local`` and the resolver stays out of the way.

    Raises on any SSM failure; callers that treat the parameter as
    optional (Langfuse tracing, Neon on a health-only boot) should wrap
    this in try/except. Callers that treat it as required (the Anthropic
    API key) should let the exception propagate — a missing key must kill
    cold-start loudly rather than silently returning 500s from the graph.

    Args:
        environment: ``"dev"`` / ``"prod"``; the path segment between prefix
            and parameter name.
        name: The parameter's leaf name under that environment, e.g.
            ``"anthropic-api-key"``.
        target_var: The plain env var the value should land in, e.g.
            ``"ANTHROPIC_API_KEY"``.
        region: AWS region of the SSM parameter.
        secret_prefix: Path prefix under which all platform parameters live.
    """
    if os.environ.get(target_var):
        return
    client = boto3.client("ssm", region_name=region)
    parameter_name = f"{secret_prefix}/{environment}/{name}"
    response = client.get_parameter(Name=parameter_name, WithDecryption=True)
    os.environ[target_var] = response["Parameter"]["Value"]
