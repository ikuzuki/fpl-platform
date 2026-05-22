"""Unit tests for the eval framework.

Coverage targets:

* Fixture tools — each returns the expected shape; ToolError on misses.
* Hard checks — pass + fail paths for every check, including word-boundary
  matching and the must_have_empty_players_list fix for the earlier no-op bug.
* Judge — verdict extraction, bullet-count contract, prompt assembly.
* Evaluator — aggregates by category, captures graph exceptions instead of
  crashing the run.
* CLI — case filtering and the threshold-driven exit code.

No real Anthropic calls. Graph + client are mocked; the synthetic fixture
gives the tools something deterministic to query against.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from fpl_agent.evaluation.eval_cases import EVAL_CASES, EVAL_CASES_VERSION, get_case_by_id
from fpl_agent.evaluation.evaluator import AgentEvaluator, _player_mentioned
from fpl_agent.evaluation.fixture_data import PlayerFixture, canned_user_squad
from fpl_agent.evaluation.fixture_tools import make_fixture_tools
from fpl_agent.evaluation.judge import (
    JudgeError,
    _format_rubric,
    _load_judge_prompt,
    _render_squad_for_judge,
    judge_case,
)
from fpl_agent.evaluation.models import (
    BulletScore,
    CategoryStats,
    EvalResult,
    EvalSummary,
    HardCheckResult,
    JudgeVerdict,
)
from fpl_agent.models.responses import (
    ComparisonResult,
    PlayerAnalysis,
    ScoutReport,
)
from fpl_agent.tools.player_tools import ToolError

# scripts/ isn't a package, so the CLI tests load it via importlib.util below.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load_run_evals_module() -> Any:
    """Import scripts/run_evals.py as a module — scripts/ isn't a package."""
    spec = importlib.util.spec_from_file_location(
        "run_evals_module", _SCRIPTS_DIR / "run_evals.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_evals_module"] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def synthetic_fixture() -> PlayerFixture:
    """Synthetic PlayerFixture shared across tests. Deterministic via seed=42."""
    return PlayerFixture.synthetic()


@pytest.fixture(scope="module")
def fixture_tools(synthetic_fixture: PlayerFixture) -> dict[str, Any]:
    """Tool registry over the synthetic fixture."""
    return make_fixture_tools(synthetic_fixture)


def _good_scout_report(case_id: str = "comparison-saka-vs-palmer") -> ScoutReport:
    """Build a ScoutReport that should pass the hard checks for the given case."""
    return ScoutReport(
        question="Saka or Palmer?",
        analysis="Saka has higher form than Palmer this run; both have green fixtures.",
        players=[
            PlayerAnalysis(
                player_name="Saka", position="MID", price=10.0, form=6.8,
                fixture_outlook="green", verdict="In form.", confidence=0.8,
            ),
            PlayerAnalysis(
                player_name="Palmer", position="MID", price=11.0, form=7.1,
                fixture_outlook="amber", verdict="High ceiling.", confidence=0.75,
            ),
        ],
        comparison=ComparisonResult(
            players=[
                PlayerAnalysis(
                    player_name="Saka", position="MID", price=10.0, form=6.8,
                    fixture_outlook="green", verdict="In form.", confidence=0.8,
                ),
                PlayerAnalysis(
                    player_name="Palmer", position="MID", price=11.0, form=7.1,
                    fixture_outlook="amber", verdict="High ceiling.", confidence=0.75,
                ),
            ],
            winner="Palmer",
            reasoning="Higher form on the same fixture difficulty.",
        ),
        recommendation="Take Palmer for the higher ceiling.",
        caveats=[],
        data_sources=["query_player", "get_fixture_outlook"],
    )


def _empty_scout_report(question: str = "") -> ScoutReport:
    """Minimal ScoutReport — used for unknown-player tests."""
    return ScoutReport(
        question=question,
        analysis="No data found.",
        players=[],
        comparison=None,
        recommendation="Cannot recommend.",
        caveats=["Player not in current snapshot."],
        data_sources=[],
    )


def _mock_anthropic_response(tool_input: dict[str, Any], tool_name: str = "record_judge_verdict") -> MagicMock:
    """Build a MagicMock that satisfies the Anthropic SDK response shape."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = tool_input
    response = MagicMock()
    response.content = [block]
    response.usage = MagicMock(input_tokens=400, output_tokens=150)
    response.stop_reason = "end_turn"
    return response


# ===========================================================================
# Section 1 — Fixture data + tools
# ===========================================================================


def test_synthetic_fixture_loads_with_expected_schema(synthetic_fixture: PlayerFixture) -> None:
    """The synthetic fixture must satisfy the schema check + provide 384-dim embeddings."""
    assert synthetic_fixture.player_count() >= 15
    assert synthetic_fixture.embeddings.shape[1] == 384
    # Required columns asserted by _assert_schema in from_parquet — exercise it here too
    PlayerFixture._assert_schema(synthetic_fixture.df)


def test_canned_user_squad_has_15_picks_with_captain(synthetic_fixture: PlayerFixture) -> None:
    """canned_user_squad builds a valid FPL squad shape."""
    squad = canned_user_squad(synthetic_fixture)
    assert len(squad.picks) == 15
    starters = [p for p in squad.picks if p.position <= 11]
    bench = [p for p in squad.picks if p.position > 11]
    assert len(starters) == 11
    assert len(bench) == 4
    captains = [p for p in squad.picks if p.is_captain]
    assert len(captains) == 1, "exactly one captain expected"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name,arg,expected_keys",
    [
        ("query_player", {"name": "Saka"}, {"web_name", "total_points", "position"}),
        ("get_fixture_outlook", {"player_name": "Salah"}, {"player", "team", "difficulty", "note"}),
        ("get_injury_signals", {"player_name": "Grealish"}, {"player", "injury_risk_score", "form_trend", "summary"}),
    ],
)
async def test_fixture_tools_return_expected_keys(
    fixture_tools: dict[str, Any],
    tool_name: str,
    arg: dict[str, Any],
    expected_keys: set[str],
) -> None:
    """Each tool's return dict must contain the keys downstream code expects."""
    result = await fixture_tools[tool_name](**arg)
    assert expected_keys.issubset(result.keys()), (
        f"{tool_name} missing keys: {expected_keys - set(result.keys())}"
    )


@pytest.mark.asyncio
async def test_query_players_by_criteria_filters_by_position_and_price(
    fixture_tools: dict[str, Any],
) -> None:
    """Criteria filter respects both axes — every returned player satisfies both."""
    result = await fixture_tools["query_players_by_criteria"](
        position="MID", max_price=8.0, limit=10
    )
    assert result["count"] > 0
    for p in result["players"]:
        assert p["position"] == "MID"
        assert p["price"] <= 8.0


@pytest.mark.asyncio
async def test_search_similar_players_excludes_self(
    fixture_tools: dict[str, Any],
) -> None:
    """The target player must not appear in its own similarity neighbours."""
    result = await fixture_tools["search_similar_players"]("Salah", k=5)
    assert result["target"] == "Salah"
    for neighbour in result["similar"]:
        assert neighbour["web_name"] != "Salah"


@pytest.mark.asyncio
async def test_fixture_tools_raise_tool_error_on_unknown_player(
    fixture_tools: dict[str, Any],
) -> None:
    """Every single-player tool raises ToolError when the player isn't in the fixture."""
    unknown = "Xherdan Shaqiri"
    for tool_name in ("query_player", "get_fixture_outlook", "get_injury_signals", "search_similar_players"):
        kwarg = "name" if tool_name == "query_player" else "player_name"
        with pytest.raises(ToolError):
            await fixture_tools[tool_name](**{kwarg: unknown})


# ===========================================================================
# Section 2 — Hard checks
# ===========================================================================


def test_hard_check_expected_tools_pass_when_subset_satisfied(
    synthetic_fixture: PlayerFixture,
) -> None:
    """A superset of expected tools still passes the subset check."""
    case = get_case_by_id("comparison-saka-vs-palmer")
    evaluator = AgentEvaluator(graph=MagicMock(), fixture=synthetic_fixture)
    extra_calls = list(case.expected_tools) + ["query_players_by_criteria"]
    results = evaluator.check_hard(case, _good_scout_report(), extra_calls)
    expected_tools_check = next(r for r in results if r.check_name == "expected_tools")
    assert expected_tools_check.passed


def test_hard_check_expected_tools_fails_with_missing_named_in_details(
    synthetic_fixture: PlayerFixture,
) -> None:
    """Failure surfaces which expected tools weren't called."""
    case = get_case_by_id("comparison-saka-vs-palmer")
    evaluator = AgentEvaluator(graph=MagicMock(), fixture=synthetic_fixture)
    results = evaluator.check_hard(case, _good_scout_report(), tool_calls_made=[])
    expected_tools_check = next(r for r in results if r.check_name == "expected_tools")
    assert not expected_tools_check.passed
    assert "missing" in expected_tools_check.details
    assert set(expected_tools_check.details["missing"]) == set(case.expected_tools)


def test_hard_check_forbidden_tools_fails_on_violation(
    synthetic_fixture: PlayerFixture,
) -> None:
    """Calling a forbidden tool fails the check, and the violation is named."""
    case = get_case_by_id("comparison-saka-vs-palmer")  # forbids search_similar_players
    evaluator = AgentEvaluator(graph=MagicMock(), fixture=synthetic_fixture)
    results = evaluator.check_hard(
        case,
        _good_scout_report(),
        tool_calls_made=list(case.expected_tools) + ["search_similar_players"],
    )
    forbidden_check = next(r for r in results if r.check_name == "forbidden_tools")
    assert not forbidden_check.passed
    assert "search_similar_players" in forbidden_check.details["violations"]


def test_player_mention_word_boundary_avoids_substring_false_positives() -> None:
    """'Saka' with word boundary must not match 'Sakai'."""
    report = ScoutReport(
        question="", analysis="Sakai impressed in midfield.",
        players=[], comparison=None, recommendation="", caveats=[], data_sources=[],
    )
    assert not _player_mentioned(report, "Saka", word_boundary=True)
    # Without word boundary, the substring fallback fires.
    assert _player_mentioned(report, "Saka", word_boundary=False)


def test_player_mention_word_boundary_matches_hyphenated_names() -> None:
    """'Alexander-Arnold' matches as a single token despite the hyphen."""
    report = ScoutReport(
        question="", analysis="Alexander-Arnold delivered three assists.",
        players=[], comparison=None, recommendation="", caveats=[], data_sources=[],
    )
    assert _player_mentioned(report, "Alexander-Arnold", word_boundary=True)


def test_hard_check_must_have_empty_players_list_catches_fabrication(
    synthetic_fixture: PlayerFixture,
) -> None:
    """The unknown-player fabrication-guard fires when the report fabricates a PlayerAnalysis."""
    case = get_case_by_id("unknown-shaqiri")
    evaluator = AgentEvaluator(graph=MagicMock(), fixture=synthetic_fixture)
    fabricated = ScoutReport(
        question="Tell me about Xherdan Shaqiri.",
        analysis="Shaqiri is a Swiss midfielder.",
        players=[
            PlayerAnalysis(
                player_name="Shaqiri", position="MID", price=6.5, form=4.0,
                fixture_outlook="amber", verdict="Made up.", confidence=0.5,
            ),
        ],
        comparison=None,
        recommendation="Avoid.",
        caveats=["Sparse data."],
        data_sources=["query_player"],
    )
    results = evaluator.check_hard(case, fabricated, ["query_player"])
    check = next(r for r in results if r.check_name == "must_have_empty_players_list")
    assert not check.passed
    assert check.details["fabricated_count"] == 1


def test_hard_check_must_have_empty_players_list_passes_on_empty_report(
    synthetic_fixture: PlayerFixture,
) -> None:
    """Graceful unknown-player handling — empty players list passes the check."""
    case = get_case_by_id("unknown-shaqiri")
    evaluator = AgentEvaluator(graph=MagicMock(), fixture=synthetic_fixture)
    results = evaluator.check_hard(
        case, _empty_scout_report("Tell me about Xherdan Shaqiri."), ["query_player"]
    )
    check = next(r for r in results if r.check_name == "must_have_empty_players_list")
    assert check.passed


def test_hard_check_min_caveats_counts_correctly(
    synthetic_fixture: PlayerFixture,
) -> None:
    """min_caveats fails when fewer caveats are present than required."""
    case = get_case_by_id("single-saka-season-view")  # min_caveats=1
    evaluator = AgentEvaluator(graph=MagicMock(), fixture=synthetic_fixture)

    report_with = _good_scout_report()
    report_with = report_with.model_copy(update={"caveats": ["one caveat"]})
    results_with = evaluator.check_hard(case, report_with, ["query_player"])
    assert next(r for r in results_with if r.check_name == "min_caveats").passed

    report_without = _good_scout_report().model_copy(update={"caveats": []})
    results_without = evaluator.check_hard(case, report_without, ["query_player"])
    assert not next(r for r in results_without if r.check_name == "min_caveats").passed


def test_hard_check_must_set_comparison_is_strict_both_ways(
    synthetic_fixture: PlayerFixture,
) -> None:
    """The check fails BOTH when comparison was required but null AND when set but not expected."""
    cmp_case = get_case_by_id("comparison-saka-vs-palmer")  # must_set_comparison=True
    single_case = get_case_by_id("single-saka-season-view")  # must_set_comparison=False
    evaluator = AgentEvaluator(graph=MagicMock(), fixture=synthetic_fixture)

    # Comparison required, but null → fail
    no_cmp = _good_scout_report().model_copy(update={"comparison": None})
    cmp_results = evaluator.check_hard(cmp_case, no_cmp, list(cmp_case.expected_tools))
    assert not next(r for r in cmp_results if r.check_name == "must_set_comparison").passed

    # Comparison set, but case didn't expect it → also fail
    with_cmp = _good_scout_report()
    single_results = evaluator.check_hard(single_case, with_cmp, ["query_player"])
    assert not next(r for r in single_results if r.check_name == "must_set_comparison").passed


# ===========================================================================
# Section 3 — Judge
# ===========================================================================


def test_judge_prompt_loads_with_all_substitution_slots() -> None:
    """All four placeholders must be present in the loaded template."""
    template = _load_judge_prompt()
    for slot in ("{question}", "{user_squad_block}", "{scout_report_json}", "{rubric_bullets}"):
        assert slot in template, f"Judge prompt missing slot: {slot}"


def test_judge_squad_render_without_squad_explains_absence() -> None:
    rendered = _render_squad_for_judge(None)
    assert "No squad loaded" in rendered


def test_judge_squad_render_with_squad_includes_captain_and_starters(
    synthetic_fixture: PlayerFixture,
) -> None:
    squad = canned_user_squad(synthetic_fixture)
    rendered = _render_squad_for_judge(squad)
    assert "Starters" in rendered
    assert "Captain" in rendered
    # The canned captain is the top-scoring MID — Salah in the synthetic.
    assert "Salah" in rendered


def test_judge_format_rubric_numbers_bullets() -> None:
    bullets = ("first bullet", "second bullet", "third bullet")
    formatted = _format_rubric(bullets)
    assert "1. first bullet" in formatted
    assert "2. second bullet" in formatted
    assert "3. third bullet" in formatted


@pytest.mark.asyncio
async def test_judge_extracts_verdict_from_tool_use_block() -> None:
    case = get_case_by_id("comparison-saka-vs-palmer")
    tool_input = {
        "bullet_scores": [
            {"bullet": b, "score": 4, "reasoning": f"OK {i + 1}."}
            for i, b in enumerate(case.judge_rubric)
        ],
        "overall": 4.0,
        "reasoning": "Solid response.",
    }
    fake_client = AsyncMock()
    fake_client.messages.create = AsyncMock(return_value=_mock_anthropic_response(tool_input))

    verdict = await judge_case(case, _good_scout_report(), fake_client, user_squad=None)
    assert verdict.overall == 4.0
    assert len(verdict.bullet_scores) == len(case.judge_rubric)
    assert verdict.bullet_scores[0].score == 4


@pytest.mark.asyncio
async def test_judge_raises_on_bullet_count_mismatch() -> None:
    """Returning the wrong number of bullet_scores must raise JudgeError loud."""
    case = get_case_by_id("comparison-saka-vs-palmer")
    tool_input = {
        "bullet_scores": [
            {"bullet": case.judge_rubric[0], "score": 4, "reasoning": "Only one."},
        ],
        "overall": 4.0,
        "reasoning": "Partial.",
    }
    fake_client = AsyncMock()
    fake_client.messages.create = AsyncMock(return_value=_mock_anthropic_response(tool_input))

    with pytest.raises(JudgeError, match="bullet scores"):
        await judge_case(case, _good_scout_report(), fake_client, user_squad=None)


@pytest.mark.asyncio
async def test_judge_raises_on_anthropic_api_failure() -> None:
    """API exceptions are wrapped as JudgeError, not propagated raw."""
    case = get_case_by_id("comparison-saka-vs-palmer")
    fake_client = AsyncMock()
    fake_client.messages.create = AsyncMock(side_effect=RuntimeError("API down"))

    with pytest.raises(JudgeError, match="Anthropic call failed"):
        await judge_case(case, _good_scout_report(), fake_client, user_squad=None)


# ===========================================================================
# Section 4 — Evaluator
# ===========================================================================


@pytest.mark.asyncio
async def test_evaluator_run_case_captures_graph_exception(
    synthetic_fixture: PlayerFixture,
) -> None:
    """A graph that raises must NOT crash run_case — the failure is recorded."""
    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("graph blew up"))

    evaluator = AgentEvaluator(graph=mock_graph, fixture=synthetic_fixture)
    case = get_case_by_id("single-saka-season-view")
    result = await evaluator.run_case(case)

    assert not result.passed
    assert result.error == "graph blew up"
    assert result.agent_report is None
    # The synthetic hard check named graph_invocation should be in the results
    assert any(hc.check_name == "graph_invocation" for hc in result.hard_checks)


@pytest.mark.asyncio
async def test_evaluator_run_all_aggregates_by_category(
    synthetic_fixture: PlayerFixture,
) -> None:
    """run_all builds CategoryStats per category, with correct counts and pass rates."""
    # Build two cases, force one to pass and one to fail by manipulating the report.
    cmp_case = get_case_by_id("comparison-saka-vs-palmer")
    single_case = get_case_by_id("single-saka-season-view")

    pass_state = {
        "final_response": _good_scout_report(),
        "tool_calls_made": list(cmp_case.expected_tools),
        "iteration_count": 1,
        "error": None,
    }
    fail_state = {
        "final_response": _good_scout_report().model_copy(update={"analysis": "X"}),
        "tool_calls_made": [],  # missing required tools
        "iteration_count": 1,
        "error": None,
    }

    # Pick the right state per case via a side_effect list
    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(side_effect=[pass_state, fail_state])

    evaluator = AgentEvaluator(graph=mock_graph, fixture=synthetic_fixture)
    summary = await evaluator.run_all([cmp_case, single_case])

    assert summary.total == 2
    assert summary.hard_check_passed == 1
    assert summary.hard_check_pass_rate == 0.5
    assert "comparison" in summary.by_category
    assert "single-player" in summary.by_category
    assert summary.by_category["comparison"].passed == 1
    assert summary.by_category["single-player"].passed == 0
    assert summary.eval_cases_version == EVAL_CASES_VERSION


# ===========================================================================
# Section 5 — CLI
# ===========================================================================


def test_cli_filter_cases_by_case_ids() -> None:
    module = _load_run_evals_module()
    selected = module.filter_cases(
        EVAL_CASES, case_ids="single-saka-season-view,comparison-saka-vs-palmer"
    )
    assert {c.id for c in selected} == {"single-saka-season-view", "comparison-saka-vs-palmer"}


def test_cli_filter_cases_by_category_with_max_cap() -> None:
    module = _load_run_evals_module()
    selected = module.filter_cases(EVAL_CASES, categories="comparison", max_cases=2)
    assert len(selected) == 2
    assert all(c.category == "comparison" for c in selected)


def test_cli_filter_cases_raises_on_no_matches() -> None:
    module = _load_run_evals_module()
    with pytest.raises(ValueError, match="No cases match"):
        module.filter_cases(EVAL_CASES, case_ids="does-not-exist")


@pytest.mark.parametrize(
    "pass_rate,threshold,expected_exit",
    [
        (1.0, 0.8, 0),
        (0.8, 0.8, 0),  # equal to threshold passes
        (0.79, 0.8, 1),
        (0.0, 0.5, 1),
    ],
)
def test_cli_compute_exit_code(
    pass_rate: float, threshold: float, expected_exit: int
) -> None:
    module = _load_run_evals_module()
    summary = EvalSummary(
        results=[],
        total=10,
        hard_check_passed=int(pass_rate * 10),
        hard_check_pass_rate=pass_rate,
        mean_judge_score=None,
        by_category={},
        by_difficulty={},
        snapshot_version="test",
        eval_cases_version="v1.0",
    )
    assert module.compute_exit_code(summary, threshold) == expected_exit


def test_cli_write_json_round_trips(tmp_path: Path) -> None:
    """JSON written by the CLI must round-trip back into an EvalSummary."""
    module = _load_run_evals_module()
    summary = EvalSummary(
        results=[
            EvalResult(
                case_id="single-saka-season-view",
                passed=True,
                hard_checks=[
                    HardCheckResult(check_name="expected_tools", passed=True, reason="OK")
                ],
                judge=JudgeVerdict(
                    bullet_scores=[
                        BulletScore(bullet="b1", score=4, reasoning="r1")
                    ],
                    overall=4.0,
                    reasoning="ok",
                ),
                agent_report=_empty_scout_report(),
                tool_calls_made=["query_player"],
                iterations_used=1,
                error=None,
                duration_seconds=0.5,
            )
        ],
        total=1,
        hard_check_passed=1,
        hard_check_pass_rate=1.0,
        mean_judge_score=4.0,
        by_category={
            "single-player": CategoryStats(count=1, passed=1, pass_rate=1.0, mean_judge_score=4.0)
        },
        by_difficulty={
            "easy": CategoryStats(count=1, passed=1, pass_rate=1.0, mean_judge_score=4.0)
        },
        snapshot_version="player_db_v1",
        eval_cases_version="v1.0",
    )
    out = tmp_path / "results.json"
    module.write_json(summary, out)
    assert out.exists()
    round_tripped = EvalSummary.model_validate_json(out.read_text())
    assert round_tripped.total == 1
    assert round_tripped.results[0].case_id == "single-saka-season-view"
