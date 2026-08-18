"""Contract tests: verify the pipeline state machine can read the input it is sent.

A `"foo.$": "$.bar"` Parameters path for a key that is absent from the execution
input raises `States.Runtime`, which no Retry or Catch can intercept — the
execution just dies. Terraform validates the state machine's syntax but never
checks it against the EventBridge payload that actually invokes it, so these
tests pair the two definitions that have to agree.
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFINITION = REPO_ROOT / "infrastructure/step_function_definitions/fpl-collection-pipeline.json.tpl"
PIPELINE_TF = REPO_ROOT / "infrastructure/environments/dev/pipeline.tf"

# The scheduled (auto-resolve) path ends here: PrepareResolvedInput re-seeds the
# top-level state from the resolver's output, so states after it read a different
# input shape. CollectParallel is the backfill entry point, reached only when a
# human passes gameweek > 0 along with their own season, so it is out of scope
# for what the EventBridge rule has to supply.
RESOLVED_BOUNDARY = "PrepareResolvedInput"
BACKFILL_ENTRY = "CollectParallel"


def _load_definition() -> dict[str, Any]:
    """Parse the ASL template, stubbing out Terraform's `${...}` interpolations."""
    raw = re.sub(
        r"\$\{[a-z_]+\}", "arn:aws:lambda:eu-west-2:0:function:stub", DEFINITION.read_text()
    )
    return json.loads(raw)


def _scheduled_input_keys() -> set[str]:
    """Top-level keys in the EventBridge rule's `input = jsonencode({...})` block."""
    block = re.search(r"input\s*=\s*jsonencode\(\{(.*?)\}\)", PIPELINE_TF.read_text(), re.DOTALL)
    assert block, "could not find the EventBridge target input block in pipeline.tf"
    return set(re.findall(r"^\s*(\w+)\s*=", block.group(1), re.MULTILINE))


def _paths_read(node: Any) -> set[str]:
    """Collect every JSONPath a state reads: Parameters `.$` values and Choice Variables.

    Deliberately ignores ResultPath, which writes rather than reads.
    """
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if (
                isinstance(value, str)
                and value.startswith("$.")
                and (key.endswith(".$") or key == "Variable")
            ):
                found.add(value)
            else:
                found |= _paths_read(value)
    elif isinstance(node, list):
        for item in node:
            found |= _paths_read(item)
    return found


def _paths_written(node: Any) -> set[str]:
    """Collect the top-level keys a state adds to the execution state via ResultPath."""
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "ResultPath" and isinstance(value, str) and value.startswith("$."):
                found.add(value.split(".")[1])
            else:
                found |= _paths_written(value)
    elif isinstance(node, list):
        for item in node:
            found |= _paths_written(item)
    return found


def _transitions(state: dict[str, Any]) -> set[str]:
    """Successor states on the happy path — Catch targets are error handling, not flow."""
    nexts = {state[key] for key in ("Next", "Default") if key in state}
    nexts |= {choice["Next"] for choice in state.get("Choices", []) if "Next" in choice}
    return nexts


def _walk(states: dict[str, Any], start: str, stop_at: set[str]) -> set[str]:
    """Breadth-first over successor states from `start`, not entering `stop_at`."""
    seen: set[str] = set()
    frontier = [start]
    while frontier:
        name = frontier.pop()
        if name in seen or name in stop_at or name not in states:
            continue
        seen.add(name)
        frontier.extend(_transitions(states[name]))
    return seen


def _top_level(paths: set[str]) -> set[str]:
    return {path.split(".")[1] for path in paths}


@pytest.mark.unit
class TestScheduledInputContract:
    """Every path the scheduled path reads must be satisfiable by the EventBridge input."""

    def test_pre_resolution_states_only_read_keys_the_schedule_sends(self) -> None:
        definition = _load_definition()
        states = definition["States"]
        reachable = _walk(
            states, definition["StartAt"], stop_at={RESOLVED_BOUNDARY, BACKFILL_ENTRY}
        )

        available = _scheduled_input_keys()
        for name in reachable:
            available |= _paths_written(states[name])

        required = _top_level({path for name in reachable for path in _paths_read(states[name])})

        assert required <= available, (
            f"States {sorted(reachable)} read top-level keys {sorted(required - available)} "
            f"that the EventBridge rule in pipeline.tf does not send. A missing Parameters "
            f"path is an uncatchable States.Runtime failure, not a retryable error."
        )

    def test_schedule_does_not_pin_a_season(self) -> None:
        """season is derived from the current date; pinning it survives a rollover silently."""
        assert "season" not in _scheduled_input_keys()

    def test_post_resolution_states_only_read_keys_prepare_reseeds(self) -> None:
        definition = _load_definition()
        states = definition["States"]
        reachable = _walk(states, BACKFILL_ENTRY, stop_at=set())

        seeded = states[RESOLVED_BOUNDARY]["Parameters"]
        available = {key.removesuffix(".$") for key in seeded}
        for name in reachable:
            available |= _paths_written(states[name])

        required = _top_level({path for name in reachable for path in _paths_read(states[name])})

        assert required <= available, (
            f"States after {RESOLVED_BOUNDARY} read top-level keys "
            f"{sorted(required - available)} that {RESOLVED_BOUNDARY} does not seed."
        )
