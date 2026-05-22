"""Run eval cases against a compiled agent graph and grade the output.

:class:`AgentEvaluator` is the orchestrator. It takes a compiled graph (real
or fixture-backed — doesn't care which), runs each :class:`EvalCase`
through it, and produces an :class:`EvalResult` per case combining the
deterministic hard checks with an optional judge verdict.

Hard checks run synchronously against the agent's :class:`ScoutReport`:

* ``expected_tools`` — every required tool name appears in the state's
  ``tool_calls_made`` list (subset check).
* ``forbidden_tools`` — none of the forbidden tool names appear.
* ``must_mention_players`` — each name shows up in either the analysis
  text or a ``PlayerAnalysis.player_name`` field. Matched with word
  boundaries unless ``match_word_boundary=False`` (set for partial-name
  cases like "Trent" → "Alexander-Arnold").
* ``must_set_comparison`` — ``ScoutReport.comparison`` populated or not,
  per the case's declaration. Strict equality, not a one-way check.
* ``must_have_empty_players_list`` — ``ScoutReport.players`` is empty.
  Only enforced when the case sets it True (unknown-player cases).
* ``min_caveats`` — ``len(ScoutReport.caveats) >= case.min_caveats``.

Judge integration ships in task #3 — :class:`AgentEvaluator` accepts a
``judge`` callable conforming to :data:`JudgeFn`, calls it if provided,
and falls back to ``judge=None`` on the resulting :class:`EvalResult`.

The agent itself is never reconstructed by the evaluator — callers build
the graph (with whichever tool registry they want) and pass it in. Keeps
the two concerns orthogonal.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable, Sequence

from langgraph.graph.state import CompiledStateGraph

from fpl_agent.evaluation.eval_cases import EVAL_CASES, EVAL_CASES_VERSION, EvalCase
from fpl_agent.evaluation.fixture_data import PlayerFixture, canned_user_squad
from fpl_agent.evaluation.models import (
    CategoryStats,
    EvalResult,
    EvalSummary,
    HardCheckResult,
    JudgeVerdict,
)
from fpl_agent.models.responses import ScoutReport, UserSquad
from fpl_agent.models.state import initial_state

logger = logging.getLogger(__name__)


# A judge callable: takes the case, the agent's report, and the user squad
# (or None), returns a verdict. Async because the implementation hits Haiku.
# Defined as a type alias rather than a Protocol because the judge is purely
# functional — no shared state across calls.
JudgeFn = Callable[[EvalCase, ScoutReport, UserSquad | None], Awaitable[JudgeVerdict]]


# ---------------------------------------------------------------------------
# Hard-check helpers
# ---------------------------------------------------------------------------


def _player_mentioned(report: ScoutReport, name: str, *, word_boundary: bool) -> bool:
    """Search for ``name`` in the analysis text and every PlayerAnalysis.player_name.

    Word-boundary matching uses ``\\b`` so "Saka" won't match "Sakai". For
    hyphenated names like "Alexander-Arnold", the hyphen counts as a word
    boundary so the pattern matches the full token.
    """
    haystacks: list[str] = [report.analysis]
    haystacks.extend(p.player_name for p in report.players)

    if word_boundary:
        pattern = re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)
        return any(pattern.search(h) for h in haystacks)
    needle = name.lower()
    return any(needle in h.lower() for h in haystacks)


def _check_expected_tools(case: EvalCase, tool_calls_made: list[str]) -> HardCheckResult:
    called = set(tool_calls_made)
    expected = set(case.expected_tools)
    missing = expected - called
    if missing:
        return HardCheckResult(
            check_name="expected_tools",
            passed=False,
            reason=f"Required tools not called: {sorted(missing)}",
            details={"expected": sorted(expected), "called": sorted(called), "missing": sorted(missing)},
        )
    return HardCheckResult(
        check_name="expected_tools",
        passed=True,
        reason=f"All {len(expected)} required tool(s) called.",
        details={"expected": sorted(expected), "called": sorted(called)},
    )


def _check_forbidden_tools(case: EvalCase, tool_calls_made: list[str]) -> HardCheckResult:
    called = set(tool_calls_made)
    forbidden = set(case.forbidden_tools)
    violations = called & forbidden
    if violations:
        return HardCheckResult(
            check_name="forbidden_tools",
            passed=False,
            reason=f"Forbidden tools were called: {sorted(violations)}",
            details={"forbidden": sorted(forbidden), "violations": sorted(violations)},
        )
    return HardCheckResult(
        check_name="forbidden_tools",
        passed=True,
        reason=(
            f"No forbidden tools called ({len(forbidden)} on watchlist)."
            if forbidden
            else "No forbidden tools declared — vacuous pass."
        ),
        details={"forbidden": sorted(forbidden)},
    )


def _check_must_mention(case: EvalCase, report: ScoutReport) -> HardCheckResult:
    if not case.must_mention_players:
        return HardCheckResult(
            check_name="must_mention_players",
            passed=True,
            reason="No players required to be mentioned — vacuous pass.",
        )
    missing = [
        name
        for name in case.must_mention_players
        if not _player_mentioned(report, name, word_boundary=case.match_word_boundary)
    ]
    if missing:
        return HardCheckResult(
            check_name="must_mention_players",
            passed=False,
            reason=f"Required players not mentioned: {missing}",
            details={
                "required": list(case.must_mention_players),
                "missing": missing,
                "match_word_boundary": case.match_word_boundary,
            },
        )
    return HardCheckResult(
        check_name="must_mention_players",
        passed=True,
        reason=f"All {len(case.must_mention_players)} required player(s) mentioned.",
        details={"required": list(case.must_mention_players)},
    )


def _check_comparison(case: EvalCase, report: ScoutReport) -> HardCheckResult:
    has_comparison = report.comparison is not None
    if has_comparison == case.must_set_comparison:
        return HardCheckResult(
            check_name="must_set_comparison",
            passed=True,
            reason=(
                "Comparison populated as required."
                if case.must_set_comparison
                else "Comparison correctly left null."
            ),
        )
    if case.must_set_comparison:
        return HardCheckResult(
            check_name="must_set_comparison",
            passed=False,
            reason="Comparison field was expected but ScoutReport.comparison is null.",
        )
    return HardCheckResult(
        check_name="must_set_comparison",
        passed=False,
        reason="Comparison field populated but the case expected it to be null.",
    )


def _check_empty_players_list(case: EvalCase, report: ScoutReport) -> HardCheckResult:
    if not case.must_have_empty_players_list:
        return HardCheckResult(
            check_name="must_have_empty_players_list",
            passed=True,
            reason="Check not enforced for this case — vacuous pass.",
        )
    if report.players:
        return HardCheckResult(
            check_name="must_have_empty_players_list",
            passed=False,
            reason=(
                f"Expected empty players[] (unknown-player case) but got "
                f"{len(report.players)} fabricated PlayerAnalysis entries: "
                f"{[p.player_name for p in report.players]}"
            ),
            details={"fabricated_count": len(report.players)},
        )
    return HardCheckResult(
        check_name="must_have_empty_players_list",
        passed=True,
        reason="players[] empty as required for unknown-player case.",
    )


def _check_min_caveats(case: EvalCase, report: ScoutReport) -> HardCheckResult:
    n = len(report.caveats)
    if n >= case.min_caveats:
        return HardCheckResult(
            check_name="min_caveats",
            passed=True,
            reason=(
                f"{n} caveat(s) present; required >= {case.min_caveats}."
                if case.min_caveats > 0
                else "No minimum caveats required — vacuous pass."
            ),
            details={"actual": n, "minimum": case.min_caveats},
        )
    return HardCheckResult(
        check_name="min_caveats",
        passed=False,
        reason=f"Only {n} caveat(s) found; required >= {case.min_caveats}.",
        details={"actual": n, "minimum": case.min_caveats},
    )


# ---------------------------------------------------------------------------
# AgentEvaluator
# ---------------------------------------------------------------------------


class AgentEvaluator:
    """Run eval cases against a compiled graph and produce graded results."""

    def __init__(
        self,
        *,
        graph: CompiledStateGraph,
        fixture: PlayerFixture,
        judge: JudgeFn | None = None,
        snapshot_version: str = "player_db_v1",
    ) -> None:
        """Initialise the evaluator.

        Args:
            graph: A compiled agent graph — typically built with fixture tools
                via :func:`fpl_agent.evaluation.fixture_tools.make_fixture_tools`.
                The evaluator never constructs a graph; callers wire whichever
                tool registry they want.
            fixture: The :class:`PlayerFixture` the graph's tools read from.
                Used by the evaluator to build the canned UserSquad for
                ``has_user_squad=True`` cases.
            judge: Optional async callable returning a :class:`JudgeVerdict`.
                When None, results carry ``judge=None`` and aggregates skip the
                judge-score mean. Wired in by task #3.
            snapshot_version: Identifier embedded in the resulting EvalSummary
                so a saved run names the fixture it was graded against.
        """
        self._graph = graph
        self._fixture = fixture
        self._judge = judge
        self._snapshot_version = snapshot_version

    # -- Hard checks ---------------------------------------------------------

    def check_hard(
        self,
        case: EvalCase,
        report: ScoutReport,
        tool_calls_made: list[str],
    ) -> list[HardCheckResult]:
        """Run every hard check on a single agent response.

        Returns a list of :class:`HardCheckResult` in deterministic order so
        downstream summary rendering is stable.
        """
        return [
            _check_expected_tools(case, tool_calls_made),
            _check_forbidden_tools(case, tool_calls_made),
            _check_must_mention(case, report),
            _check_comparison(case, report),
            _check_empty_players_list(case, report),
            _check_min_caveats(case, report),
        ]

    # -- Single case ---------------------------------------------------------

    async def run_case(self, case: EvalCase) -> EvalResult:
        """Invoke the agent on one case and grade the response.

        The agent's own error paths (``state['error']`` set, recommender
        short-circuit) still produce a :class:`ScoutReport` — the error
        report has an empty ``players`` list and a caveat naming the failure.
        Hard checks run against that report just like any other; cases will
        typically fail several of them, surfacing the error as a graded
        outcome rather than an exception.
        """
        squad: UserSquad | None = (
            canned_user_squad(self._fixture) if case.has_user_squad else None
        )
        start = time.perf_counter()
        try:
            state = await self._graph.ainvoke(initial_state(case.question, squad))
        except Exception as exc:  # noqa: BLE001 — capture and continue
            elapsed = time.perf_counter() - start
            logger.exception("Case %s raised during graph invocation", case.id)
            return EvalResult(
                case_id=case.id,
                passed=False,
                hard_checks=[
                    HardCheckResult(
                        check_name="graph_invocation",
                        passed=False,
                        reason=f"Graph raised: {exc}",
                    )
                ],
                judge=None,
                agent_report=None,
                tool_calls_made=[],
                iterations_used=0,
                error=str(exc),
                duration_seconds=elapsed,
            )

        report: ScoutReport | None = state.get("final_response")
        tool_calls_made: list[str] = state.get("tool_calls_made") or []
        iterations_used: int = int(state.get("iteration_count") or 0)
        state_error: str | None = state.get("error")

        if report is None:
            # The graph completed without raising but produced no ScoutReport —
            # shouldn't happen given the recommender's error short-circuit, but
            # the contract allows for it. Mark the case failed without crashing.
            elapsed = time.perf_counter() - start
            return EvalResult(
                case_id=case.id,
                passed=False,
                hard_checks=[
                    HardCheckResult(
                        check_name="graph_invocation",
                        passed=False,
                        reason="Graph completed without producing a ScoutReport.",
                    )
                ],
                judge=None,
                agent_report=None,
                tool_calls_made=tool_calls_made,
                iterations_used=iterations_used,
                error=state_error,
                duration_seconds=elapsed,
            )

        hard_checks = self.check_hard(case, report, tool_calls_made)
        passed = all(hc.passed for hc in hard_checks)

        verdict: JudgeVerdict | None = None
        if self._judge is not None:
            try:
                verdict = await self._judge(case, report, squad)
            except Exception as exc:  # noqa: BLE001 — judge failure shouldn't kill the run
                logger.exception("Judge raised on case %s", case.id)
                verdict = None
                # Surface this as a synthetic HardCheckResult so the failure
                # is visible in the summary, but don't flip `passed`.
                hard_checks.append(
                    HardCheckResult(
                        check_name="judge_invocation",
                        passed=True,  # advisory only — don't poison the hard pass-rate
                        reason=f"Judge errored: {exc}. Verdict omitted.",
                    )
                )

        elapsed = time.perf_counter() - start
        return EvalResult(
            case_id=case.id,
            passed=passed,
            hard_checks=hard_checks,
            judge=verdict,
            agent_report=report,
            tool_calls_made=tool_calls_made,
            iterations_used=iterations_used,
            error=state_error,
            duration_seconds=elapsed,
        )

    # -- All cases -----------------------------------------------------------

    async def run_all(
        self,
        cases: Sequence[EvalCase] = EVAL_CASES,
        *,
        concurrency: int = 1,
    ) -> EvalSummary:
        """Run every case and aggregate.

        Args:
            cases: Cases to run. Defaults to the full :data:`EVAL_CASES` set.
            concurrency: Max in-flight cases. Default 1 (serial) so traces
                stay readable and Anthropic rate limits aren't tripped.
                Bump to ~3–5 if you trust the rate budget.
        """
        if concurrency < 1:
            raise ValueError(f"concurrency must be >= 1, got {concurrency}")

        if concurrency == 1:
            results: list[EvalResult] = []
            for case in cases:
                results.append(await self.run_case(case))
        else:
            semaphore = asyncio.Semaphore(concurrency)

            async def _bounded(case: EvalCase) -> EvalResult:
                async with semaphore:
                    return await self.run_case(case)

            results = list(await asyncio.gather(*(_bounded(c) for c in cases)))

        return self._build_summary(cases, results)

    # -- Summary aggregation -------------------------------------------------

    def _build_summary(
        self,
        cases: Sequence[EvalCase],
        results: list[EvalResult],
    ) -> EvalSummary:
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        pass_rate = (passed / total) if total else 0.0

        judge_scores = [r.judge.overall for r in results if r.judge is not None]
        mean_judge = (sum(judge_scores) / len(judge_scores)) if judge_scores else None

        by_id = {c.id: c for c in cases}
        by_category = _aggregate(results, key=lambda r: by_id[r.case_id].category)
        by_difficulty = _aggregate(results, key=lambda r: by_id[r.case_id].difficulty)

        return EvalSummary(
            results=results,
            total=total,
            hard_check_passed=passed,
            hard_check_pass_rate=pass_rate,
            mean_judge_score=mean_judge,
            by_category=by_category,
            by_difficulty=by_difficulty,
            snapshot_version=self._snapshot_version,
            eval_cases_version=EVAL_CASES_VERSION,
        )


def _aggregate(
    results: list[EvalResult],
    *,
    key: Callable[[EvalResult], str],
) -> dict[str, CategoryStats]:
    """Bucket results by a string key and compute per-bucket pass rate + judge mean."""
    buckets: dict[str, list[EvalResult]] = {}
    for r in results:
        buckets.setdefault(key(r), []).append(r)

    stats: dict[str, CategoryStats] = {}
    for bucket_key, items in buckets.items():
        count = len(items)
        passed = sum(1 for r in items if r.passed)
        verdicts = [r.judge.overall for r in items if r.judge is not None]
        stats[bucket_key] = CategoryStats(
            count=count,
            passed=passed,
            pass_rate=(passed / count) if count else 0.0,
            mean_judge_score=(sum(verdicts) / len(verdicts)) if verdicts else None,
        )
    return stats


# Public re-exports — useful for tests and the CLI.
__all__ = [
    "AgentEvaluator",
    "JudgeFn",
]
