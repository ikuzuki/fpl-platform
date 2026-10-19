"""p50 / p95 of the ``/chat`` latency metrics over a recent window.

Two sources, same three metrics (``time_to_first_event_ms``,
``time_to_first_report_token_ms``, ``total_ms``):

* ``cloudwatch`` (default) — the ``chat_latency`` JSON log line the agent
  Lambda writes on every streamed request. Works while Langfuse tracing is
  off on the deployed Lambda.
* ``langfuse`` — the same values recorded as scores on each request trace.
  Only populated where tracing is on (local runs, or the Lambda once it is
  re-enabled).

Usage:
    python services/agent/scripts/latency_report.py --hours 24
    python services/agent/scripts/latency_report.py --source langfuse --hours 2
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import boto3
import httpx

from fpl_lib.observability import init_langfuse

METRICS = ("time_to_first_event_ms", "time_to_first_report_token_ms", "total_ms")
_LOG_MARKER = "chat_latency "


def parse_log_message(message: str) -> dict[str, int | None] | None:
    """Extract the metrics from one ``chat_latency`` log line, or ``None`` if it isn't one."""
    _, marker, payload = message.partition(_LOG_MARKER)
    if not marker:
        return None
    record = json.loads(payload)
    return {m: record.get(m) for m in METRICS}


def percentiles(values: Sequence[float]) -> tuple[float, float] | None:
    """Return (p50, p95), or ``None`` with fewer than two values."""
    if len(values) < 2:
        return None
    cuts = statistics.quantiles(values, n=100, method="inclusive")
    return cuts[49], cuts[94]


def from_cloudwatch(env: str, since: datetime) -> dict[str, list[float]]:
    logs = boto3.client("logs")
    paginator = logs.get_paginator("filter_log_events")
    values: dict[str, list[float]] = {m: [] for m in METRICS}
    for page in paginator.paginate(
        logGroupName=f"/aws/lambda/fpl-{env}-agent",
        filterPattern='"chat_latency"',
        startTime=int(since.timestamp() * 1000),
    ):
        for event in page["events"]:
            record = parse_log_message(event["message"])
            for metric, value in (record or {}).items():
                if value is not None:
                    values[metric].append(float(value))
    return values


def from_langfuse(env: str, since: datetime) -> dict[str, list[float]]:
    init_langfuse(environment=env)
    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
    auth = (os.environ["LANGFUSE_PUBLIC_KEY"], os.environ["LANGFUSE_SECRET_KEY"])
    values: dict[str, list[float]] = {}
    for metric in METRICS:
        values[metric] = []
        page = 1
        while True:
            body = httpx.get(
                f"{host}/api/public/v2/scores",
                params={
                    "name": metric,
                    "fromTimestamp": since.isoformat(),
                    "limit": 100,
                    "page": page,
                },
                auth=auth,
                timeout=30,
            ).json()
            values[metric].extend(float(s["value"]) for s in body["data"])
            if page >= body["meta"]["totalPages"]:
                break
            page += 1
    return values


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", choices=("cloudwatch", "langfuse"), default="cloudwatch")
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--env", default="dev")
    args = parser.parse_args(argv)

    since = datetime.now(UTC) - timedelta(hours=args.hours)
    fetch = from_cloudwatch if args.source == "cloudwatch" else from_langfuse
    values = fetch(args.env, since)

    print(f"{args.source}, last {args.hours:g}h")
    for metric in METRICS:
        result = percentiles(values[metric])
        n = len(values[metric])
        if result is None:
            print(f"  {metric:32} n={n:<4} (need at least 2 values)")
        else:
            print(f"  {metric:32} n={n:<4} p50={result[0]:>7.0f}  p95={result[1]:>7.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
