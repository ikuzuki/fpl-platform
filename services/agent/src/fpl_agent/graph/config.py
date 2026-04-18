"""Model choices and limits for the scout report agent graph.

Values here are referenced from :mod:`fpl_agent.graph.nodes`. Centralising
them makes ADR-0009's tiered-model decision (Haiku for planning/reflection,
Sonnet for synthesis) visible in one place and keeps per-node LLM configs
out of the node bodies.
"""

from __future__ import annotations

# Tiered model selection per ADR-0009. Haiku is ~3× cheaper and fast enough
# for the structured planning/reflection decisions; Sonnet is reserved for
# the one call that has to reason over multiple data sources.
PLANNER_MODEL = "claude-haiku-4-5"
REFLECTOR_MODEL = "claude-haiku-4-5"
RECOMMENDER_MODEL = "claude-sonnet-4-6"

# Hard cap on reflector → planner loops. With 3 iterations we make at most
# 3 × (planner + reflector) + 1 recommender = 7 LLM calls per request, which
# keeps per-query cost in the $0.03–0.08 range the ADR targets.
MAX_ITERATIONS = 3

# Per-tool timeout. Lambda's 60s ceiling minus ~15s of LLM latency leaves
# ~45s for up to 3 iterations of tool calls; 10s per tool is generous for
# a Neon query and safe for a boto3 Lambda invoke.
TOOL_TIMEOUT_SECONDS = 10

# Max tokens per LLM call. Set high enough that structured outputs don't
# truncate; each call normally uses far fewer.
PLANNER_MAX_TOKENS = 1024
REFLECTOR_MAX_TOKENS = 512
RECOMMENDER_MAX_TOKENS = 4096
