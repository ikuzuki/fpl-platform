"""CLI for running the agent eval suite.

End-to-end pipeline:

1. Load the snapshot fixture (parquet by default, ``--synthetic`` for unit-test
   smoke runs).
2. Compile the agent graph against ``make_fixture_tools`` - the graph reads
   from the in-memory snapshot, not live Neon, so scores are reproducible.
3. Build a Haiku judge (unless ``--no-judge``) and pass it into the
   :class:`AgentEvaluator`.
4. Filter cases by id / category / max-count per the CLI args, run them,
   render a Rich table, optionally write a JSON :class:`EvalSummary`.
5. Exit 0 if hard-check pass rate >= ``--threshold``; otherwise 1.

Usage:
    export ANTHROPIC_API_KEY=...
    python services/agent/scripts/run_evals.py
    python services/agent/scripts/run_evals.py --max-cases 5 --no-judge
    python services/agent/scripts/run_evals.py --categories comparison,squad-aware
    python services/agent/scripts/run_evals.py --case-ids single-saka-season-view
    python services/agent/scripts/run_evals.py --output results.json --threshold 0.8

The first real run takes a few minutes (29 cases x ~5-7 LLM calls each).
Use ``--max-cases 1`` while iterating on the framework itself.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from anthropic import AsyncAnthropic
from rich.console import Console
from rich.table import Table

from fpl_agent.evaluation.eval_cases import EVAL_CASES, EVAL_CASES_VERSION, EvalCase
from fpl_agent.evaluation.evaluator import AgentEvaluator
from fpl_agent.evaluation.fixture_data import DEFAULT_FIXTURE_PATH, PlayerFixture
from fpl_agent.evaluation.fixture_tools import make_fixture_tools
from fpl_agent.evaluation.judge import make_judge
from fpl_agent.evaluation.models import CategoryStats, EvalSummary
from fpl_agent.graph.builder import build_agent_graph

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments. Extracted so tests can pass argv directly."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.8,
        help="Minimum hard-check pass rate to exit 0 (default: 0.8).",
    )
    parser.add_argument(
        "--categories",
        type=str,
        default=None,
        help="Comma-separated category filter, e.g. 'comparison,single-player'. "
        "Default: run all categories.",
    )
    parser.add_argument(
        "--case-ids",
        type=str,
        default=None,
        help="Comma-separated case-id filter, e.g. 'single-saka-season-view'. "
        "Wins over --categories if both are set.",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="Cap total cases after filtering. Useful for iteration / quick checks.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write the EvalSummary as JSON to this path (default: stdout-only).",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Max in-flight cases (default: 1). Bump to 3-5 if rate limits allow.",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=DEFAULT_FIXTURE_PATH,
        help=f"Snapshot parquet path (default: {DEFAULT_FIXTURE_PATH}).",
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Use the in-memory synthetic fixture instead of the parquet. "
        "For framework smoke tests only - not for real baselines.",
    )
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="Skip the Haiku judge - hard checks only. Cuts cost while iterating.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable DEBUG-level logging.",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Case filtering
# ---------------------------------------------------------------------------


def filter_cases(
    cases: Sequence[EvalCase],
    *,
    case_ids: str | None = None,
    categories: str | None = None,
    max_cases: int | None = None,
) -> list[EvalCase]:
    """Apply the CLI filters in priority order: ids > categories > max-cap.

    Pure function so tests can exercise it without touching argparse.
    """
    selected: list[EvalCase] = list(cases)

    if case_ids:
        wanted_ids = {x.strip() for x in case_ids.split(",") if x.strip()}
        selected = [c for c in selected if c.id in wanted_ids]
        if not selected:
            raise ValueError(f"No cases match --case-ids={case_ids!r}")
    elif categories:
        wanted_cats = {x.strip() for x in categories.split(",") if x.strip()}
        selected = [c for c in selected if c.category in wanted_cats]
        if not selected:
            raise ValueError(f"No cases match --categories={categories!r}")

    if max_cases is not None and max_cases > 0:
        selected = selected[:max_cases]

    return selected


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_summary(summary: EvalSummary, console: Console) -> None:
    """Print a Rich-formatted view of the eval results."""
    pass_pct = summary.hard_check_pass_rate * 100
    judge_str = (
        f"{summary.mean_judge_score:.2f}/5"
        if summary.mean_judge_score is not None
        else "(no judge)"
    )

    console.rule(
        f"[bold]Eval run[/bold] · {summary.total} cases · "
        f"snapshot={summary.snapshot_version} · cases_version={summary.eval_cases_version}"
    )
    console.print(
        f"[bold]Hard-check pass rate:[/bold] {summary.hard_check_passed}/{summary.total} "
        f"({pass_pct:.1f}%) · [bold]Mean judge:[/bold] {judge_str}"
    )

    # Per-case table - only show essential columns to keep it scannable.
    case_table = Table(title="Per case", show_lines=False)
    case_table.add_column("Case id", overflow="fold")
    case_table.add_column("Category")
    case_table.add_column("Passed", justify="center")
    case_table.add_column("Judge", justify="right")
    case_table.add_column("Dur (s)", justify="right")
    case_table.add_column("Failed checks", overflow="fold")

    for r in summary.results:
        passed_marker = "[green]PASS[/green]" if r.passed else "[red]FAIL[/red]"
        judge_cell = f"{r.judge.overall:.1f}" if r.judge else "-"
        failed_names = [hc.check_name for hc in r.hard_checks if not hc.passed]
        case_table.add_row(
            r.case_id,
            _find_category(summary, r.case_id),
            passed_marker,
            judge_cell,
            f"{r.duration_seconds:.2f}",
            ", ".join(failed_names) if failed_names else "-",
        )
    console.print(case_table)

    # Aggregate breakdowns
    _render_breakdown(console, "By category", summary.by_category)
    _render_breakdown(console, "By difficulty", summary.by_difficulty)

    # Failure detail - full reason text for each failed check, grouped by case.
    failed_results = [r for r in summary.results if not r.passed]
    if failed_results:
        console.rule(f"[bold red]Failure detail ({len(failed_results)} cases)[/bold red]")
        for r in failed_results:
            console.print(f"[bold]{r.case_id}[/bold]")
            for hc in r.hard_checks:
                if not hc.passed:
                    console.print(f"  [red]✗[/red] {hc.check_name}: {hc.reason}")
            if r.error:
                console.print(f"  [red]error:[/red] {r.error}")


def _find_category(summary: EvalSummary, case_id: str) -> str:
    """Look up the case's category - handy for tables that don't carry it on EvalResult."""
    # EvalResult doesn't carry category on it directly, so reach back into EVAL_CASES.
    # We could thread it through, but the lookup is O(N) per case and cheap.
    for c in EVAL_CASES:
        if c.id == case_id:
            return c.category
    return "(unknown)"


def _render_breakdown(
    console: Console, title: str, stats: dict[str, CategoryStats]
) -> None:
    """Render a category- or difficulty-sliced summary as a Rich table."""
    if not stats:
        return
    table = Table(title=title)
    table.add_column("Bucket")
    table.add_column("Count", justify="right")
    table.add_column("Passed", justify="right")
    table.add_column("Pass rate", justify="right")
    table.add_column("Mean judge", justify="right")
    for bucket, s in sorted(stats.items()):
        mean = s.mean_judge_score
        table.add_row(
            bucket,
            str(s.count),
            str(s.passed),
            f"{s.pass_rate * 100:.1f}%",
            f"{mean:.2f}" if mean is not None else "-",
        )
    console.print(table)


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------


def write_json(summary: EvalSummary, path: Path) -> None:
    """Persist the summary as JSON for the baseline doc generator + comparison runs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(summary.model_dump_json(indent=2) + "\n", encoding="utf-8")
    logger.info("Wrote eval summary to %s", path)


# ---------------------------------------------------------------------------
# Exit code
# ---------------------------------------------------------------------------


def compute_exit_code(summary: EvalSummary, threshold: float) -> int:
    """Return the CLI exit code based on the hard-check pass rate.

    Pulled into a pure function so the threshold logic is unit-testable
    without spinning up an Anthropic client or a graph.
    """
    if summary.hard_check_pass_rate >= threshold:
        return 0
    return 1


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------


def _load_fixture(args: argparse.Namespace) -> PlayerFixture:
    if args.synthetic:
        logger.warning("Using synthetic fixture - scores are not real baseline numbers.")
        return PlayerFixture.synthetic()
    return PlayerFixture.from_parquet(args.snapshot)


def _snapshot_version_from_path(path: Path) -> str:
    """Derive a version label from the snapshot filename (e.g. 'player_db_v1.parquet' → 'player_db_v1')."""
    return path.stem if path.stem else "unknown"


async def run(args: argparse.Namespace, *, console: Console | None = None) -> int:
    """Async entry-point - orchestrates the whole pipeline."""
    if console is None:
        console = Console()

    fixture = _load_fixture(args)

    client = AsyncAnthropic()  # ANTHROPIC_API_KEY picked up from env
    tools = make_fixture_tools(fixture)
    graph = build_agent_graph(client=client, tools=tools)
    judge_fn = None if args.no_judge else make_judge(client)

    evaluator = AgentEvaluator(
        graph=graph,
        fixture=fixture,
        judge=judge_fn,
        snapshot_version=(
            "synthetic" if args.synthetic else _snapshot_version_from_path(args.snapshot)
        ),
    )

    cases = filter_cases(
        EVAL_CASES,
        case_ids=args.case_ids,
        categories=args.categories,
        max_cases=args.max_cases,
    )
    logger.info(
        "Running %d/%d eval cases (cases_version=%s, judge=%s, concurrency=%d)",
        len(cases),
        len(EVAL_CASES),
        EVAL_CASES_VERSION,
        "off" if args.no_judge else "haiku",
        args.concurrency,
    )

    summary = await evaluator.run_all(cases, concurrency=args.concurrency)
    render_summary(summary, console)

    if args.output:
        write_json(summary, args.output)

    return compute_exit_code(summary, args.threshold)


def main(argv: Sequence[str] | None = None) -> int:
    """Sync entrypoint - parses args, configures logging, runs the pipeline."""
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
