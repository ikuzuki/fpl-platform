"""Golden eval set for the scout report agent.

29 cases across 11 categories. Designed to exercise:

* **Tool routing** — the planner picks the minimum-sufficient tool set per
  question type. Each case declares ``expected_tools`` (must be called) and
  ``forbidden_tools`` (must not be called).
* **Failure modes** — unknown players, vague questions, ambiguous names. The
  agent must degrade gracefully and flag uncertainty in ``caveats`` rather
  than inventing data.
* **Output shape** — comparison questions must populate ``ComparisonResult``;
  squad-aware questions must reference picks from the loaded ``UserSquad``.
* **Narrative quality** — judged by Haiku against a per-case rubric. Rubrics
  are deliberately specific (e.g. "names a concrete captain pick") rather
  than vague ("good answer") so that the judge has something to anchor on.

The cases are typed inline so the file is self-contained for review. When
the framework lands the model will move to ``evaluation/models.py`` with the
rest of the result types.

Design choices baked into v1
----------------------------
* **Clean phrasing, not scrappy real-user input.** Every question is
  grammatically complete and unambiguous. A v2 eval set will mirror the
  uglier shape of real chat input (typos, fragments, missing punctuation)
  with its own rubric — mixing the two muddies what you're measuring.
* **Snapshot dependencies are documented per case.** Cases that rely on a
  specific player being present declare it in ``pinned_roster_facts``. When
  regenerating the snapshot, fail loud if any pinned fact no longer holds.
* **Judge gets ``UserSquad`` for squad-aware cases.** The judge prompt for
  any case with ``has_user_squad=True`` MUST receive the same squad fixture
  the agent saw. Without it, the judge can't verify "captain pick is one of
  the user's starters" and the score is unreliable. Enforced in
  ``evaluation/judge.py`` when that lands.
* **Deferred categories.** Chip-strategy (wildcard, bench boost, free hit,
  triple captain), DGW/BGW awareness, and gameweek-specific timing
  questions are out of scope for v1 — the current tool set has no concept
  of gameweeks or chips. Build the tools first, then the cases.

Player names below assume the snapshot at ``tests/fixtures/player_db_v1.parquet``.
Regenerate with ``scripts/snapshot_player_db.py`` and assert each case's
``pinned_roster_facts`` hold before committing the new snapshot.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Bump when the case set changes meaningfully — added/removed cases, rubric edits,
# or any change that should invalidate prior baseline scores. Stored in EvalSummary
# so saved runs are tagged with the version they were graded against.
EVAL_CASES_VERSION = "v1.1"

Category = Literal[
    "single-player",
    "comparison",
    "criteria-search",
    "injury-concern",
    "differential",
    "form-analysis",
    "squad-aware",
    "vague",
    "unknown-player",
    "multi-position",
    "edge-case",
]

Difficulty = Literal["easy", "medium", "hard"]

ToolName = Literal[
    "query_player",
    "search_similar_players",
    "query_players_by_criteria",
    "get_fixture_outlook",
    "get_injury_signals",
]


class EvalCase(BaseModel):
    """One row of the golden eval set."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(description="Stable slug — used as the result key and log line prefix.")
    question: str
    category: Category
    difficulty: Difficulty
    has_user_squad: bool = Field(
        default=False,
        description="True for cases that require a UserSquad in context. The squad fixture "
        "is built by the evaluator from a canned manager profile; see fixture_data.py.",
    )
    expected_tools: frozenset[ToolName] = Field(
        description="Tools that MUST be called. Subset check — extra tools are allowed unless "
        "they appear in ``forbidden_tools``."
    )
    forbidden_tools: frozenset[ToolName] = Field(
        default=frozenset(),
        description="Tools that must NOT be called. Used to catch over-fetching (e.g. similarity "
        "search when the user named the players explicitly).",
    )
    must_mention_players: tuple[str, ...] = Field(
        default=(),
        description="Player names that must appear in either ``ScoutReport.analysis`` or any "
        "``PlayerAnalysis.player_name``. Matching is case-insensitive; see "
        "``match_word_boundary`` for substring-vs-token behaviour.",
    )
    match_word_boundary: bool = Field(
        default=True,
        description="If True, ``must_mention_players`` entries match only on word boundaries — "
        "so 'Saka' matches 'Saka' but not 'Sakai'. Set False for partial-name cases where the "
        "match is intentionally permissive.",
    )
    must_set_comparison: bool = Field(
        default=False,
        description="If True, ``ScoutReport.comparison`` must be populated; if False, it must be null.",
    )
    must_have_empty_players_list: bool = Field(
        default=False,
        description="If True, ``ScoutReport.players`` must be empty — used by unknown-player "
        "cases to enforce 'no fabricated PlayerAnalysis' as a hard check (the empty-tuple "
        "``must_mention_players`` doesn't enforce this — it just no-ops).",
    )
    min_caveats: int = Field(
        default=0,
        description="Minimum number of entries in ``ScoutReport.caveats``. Cases with known data "
        "gaps (unknown players, vague questions, fixture staleness) set this > 0.",
    )
    pinned_roster_facts: tuple[str, ...] = Field(
        default=(),
        description="Roster assumptions this case depends on — e.g. 'Robertson present in "
        "snapshot'. The snapshot regeneration script asserts each fact still holds; if not, "
        "the case is flagged for human review rather than silently rotting.",
    )
    judge_rubric: tuple[str, ...] = Field(
        description="3–5 specific criteria the Haiku judge scores 1–5 each. The rubric is the "
        "soft layer on top of the hard checks above."
    )


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------
# Grouped by category for readability. The eval runner shuffles before
# execution to avoid order effects on prompt-cache warm-up.

EVAL_CASES: tuple[EvalCase, ...] = (
    # -- Single-player analysis ----------------------------------------------
    EvalCase(
        id="single-saka-season-view",
        question="How is Saka doing this season?",
        category="single-player",
        difficulty="easy",
        expected_tools=frozenset({"query_player"}),
        must_mention_players=("Saka",),
        min_caveats=1,
        pinned_roster_facts=("Saka present in snapshot",),
        judge_rubric=(
            "Analysis references concrete stats (points, form, price) — not vague praise.",
            "Recommendation is actionable (own / sell / hold), not hedged waffle.",
            "Traffic-light fixture_outlook is consistent with the fixture_difficulty value "
            "returned by query_player (green ≤2.5, amber 2.5–3.5, red >3.5).",
            "Caveats flag the lack of per-GW fixture breakdown.",
        ),
    ),
    EvalCase(
        id="single-salah-buy-decision",
        question="Should I buy Salah?",
        category="single-player",
        difficulty="easy",
        expected_tools=frozenset({"query_player", "get_fixture_outlook"}),
        must_mention_players=("Salah",),
        pinned_roster_facts=("Salah present in snapshot",),
        judge_rubric=(
            "Recommendation states a position (buy / hold / skip) OR explicitly defers with the "
            "specific data gap blocking the call — not generic hedging.",
            "Price-to-points value is addressed explicitly with concrete numbers.",
            "Fixture difficulty is woven into the buy/hold reasoning, not just listed alongside.",
        ),
    ),
    EvalCase(
        id="single-haaland-form-check",
        question="What's Haaland's form like right now?",
        category="single-player",
        difficulty="easy",
        expected_tools=frozenset({"query_player"}),
        forbidden_tools=frozenset({"search_similar_players"}),
        must_mention_players=("Haaland",),
        pinned_roster_facts=("Haaland present in snapshot",),
        judge_rubric=(
            "Form is given as a concrete number or trend, not adjectives only.",
            "Recent points trajectory is mentioned if available in form_trend.",
            "No speculative comparison to other forwards (forbidden tool check).",
        ),
    ),
    EvalCase(
        id="single-palmer-full-picture",
        question="Tell me everything I should know about Cole Palmer before this gameweek.",
        category="single-player",
        difficulty="medium",
        # query_player does SELECT * (player_tools.py:79–86) which already includes
        # fixture_difficulty, injury_risk_score, form_trend, and summary. The targeted
        # tools wrap the same columns — calling them for an "everything" question is
        # redundant. Test that the planner is efficient, not encyclopaedic.
        expected_tools=frozenset({"query_player"}),
        must_mention_players=("Palmer",),
        min_caveats=1,
        pinned_roster_facts=("Palmer present in snapshot",),
        judge_rubric=(
            "Analysis covers form, fixtures, and injury — drawn from the query_player row.",
            "Confidence is < 1.0 and grounded in actual data completeness.",
            "Recommendation gives a clear pre-deadline action.",
            "No redundant follow-up tool calls (planner trusts SELECT * coverage).",
        ),
    ),
    # -- Head-to-head comparison ---------------------------------------------
    EvalCase(
        id="comparison-saka-vs-palmer",
        question="Saka or Palmer?",
        category="comparison",
        difficulty="medium",
        expected_tools=frozenset({"query_player", "get_fixture_outlook"}),
        forbidden_tools=frozenset({"search_similar_players"}),
        must_mention_players=("Saka", "Palmer"),
        must_set_comparison=True,
        pinned_roster_facts=("Saka present in snapshot", "Palmer present in snapshot"),
        judge_rubric=(
            "comparison.winner is set OR null is justified in reasoning as genuinely too close "
            "to call given the data available — not left null by default.",
            "Reasoning grounds the verdict in specific numbers (points, form, fixture score).",
            "Both players appear in comparison.players.",
            "Recommendation matches the comparison winner (or the deferral framing if null).",
        ),
    ),
    EvalCase(
        id="comparison-watkins-vs-isak",
        question="Watkins vs Isak — who's the better forward right now?",
        category="comparison",
        difficulty="medium",
        # Dropped get_injury_signals from required set — assuming a flagged injury at
        # snapshot time makes the case brittle to roster regeneration. The rubric still
        # rewards weighing injury data if it surfaces from query_player.
        expected_tools=frozenset({"query_player"}),
        must_mention_players=("Watkins", "Isak"),
        must_set_comparison=True,
        pinned_roster_facts=("Watkins present in snapshot", "Isak present in snapshot"),
        judge_rubric=(
            "If query_player surfaces non-zero injury_risk_score for either player, the verdict "
            "weighs it; if not, no fabricated injury claims appear.",
            "comparison.winner is set OR explicit deferral with reasoning; reasoning explains "
            "the margin in concrete terms.",
            "Both forwards' goal threat and form are addressed — not just one axis.",
        ),
    ),
    EvalCase(
        id="comparison-trippier-vs-robertson",
        question="Trippier or Robertson for the rest of the season?",
        category="comparison",
        difficulty="medium",
        expected_tools=frozenset({"query_player", "get_fixture_outlook"}),
        must_mention_players=("Trippier", "Robertson"),
        must_set_comparison=True,
        pinned_roster_facts=(
            "Trippier present in snapshot (verify team affiliation hasn't rotated)",
            "Robertson present in snapshot (verify team affiliation hasn't rotated)",
        ),
        judge_rubric=(
            "Fixture outlook is the primary axis given the 'rest of the season' framing.",
            "Both defenders' attacking returns are addressed, not just clean-sheet odds.",
            "comparison.winner is set OR explicit deferral with reasoning.",
        ),
    ),
    # -- Criteria search -----------------------------------------------------
    EvalCase(
        id="criteria-best-mids-under-8m",
        question="Who are the best midfielders under £8m?",
        category="criteria-search",
        difficulty="easy",
        expected_tools=frozenset({"query_players_by_criteria"}),
        forbidden_tools=frozenset({"query_player"}),
        judge_rubric=(
            "At least 3 distinct midfielders surfaced in players[].",
            "All listed players are under £8m and position == MID.",
            "Ranking rationale references total_points or form.",
        ),
    ),
    EvalCase(
        id="criteria-cheap-in-form-defenders",
        question="Find me cheap defenders with good form.",
        category="criteria-search",
        difficulty="medium",
        expected_tools=frozenset({"query_players_by_criteria"}),
        judge_rubric=(
            "'Cheap' is interpreted as a concrete price ceiling that's stated, not left ambiguous.",
            "'Good form' is interpreted as a concrete min_form threshold that's stated.",
            "Players returned all satisfy both filters as the agent defined them.",
            "Caveats flag the interpretation of 'cheap' and 'good form' so the user can adjust.",
        ),
    ),
    EvalCase(
        id="criteria-best-arsenal-players",
        question="Who are the best Arsenal players to own right now?",
        category="criteria-search",
        difficulty="easy",
        expected_tools=frozenset({"query_players_by_criteria"}),
        judge_rubric=(
            "All recommended players are from Arsenal.",
            "At least one player per position group is considered or filtering rationale explained.",
            "Output isn't just one player — at least 3 distinct names.",
        ),
    ),
    EvalCase(
        id="criteria-defender-good-fixtures",
        question="Pick me a defender with a good run of fixtures.",
        category="criteria-search",
        difficulty="medium",
        expected_tools=frozenset({"query_players_by_criteria"}),
        min_caveats=1,
        judge_rubric=(
            "Fixture outlook (via fixture_difficulty) drives the pick, not just total_points.",
            "Recommendation names ONE specific defender — not a shortlist.",
            "Caveat acknowledges that fixture_difficulty is a single aggregate, not a per-GW "
            "breakdown — so 'good run' is approximated.",
        ),
    ),
    # -- Injury concern ------------------------------------------------------
    EvalCase(
        id="injury-saliba-fitness",
        question="Is Saliba fit for this gameweek?",
        category="injury-concern",
        difficulty="easy",
        expected_tools=frozenset({"get_injury_signals", "query_player"}),
        must_mention_players=("Saliba",),
        min_caveats=1,
        pinned_roster_facts=("Saliba present in snapshot",),
        judge_rubric=(
            "injury_risk_score is referenced explicitly with its value.",
            "Caveat acknowledges that the injury signal may not reflect the latest team news.",
            "Recommendation gives a hold/bench/transfer-out call, not just 'monitor'.",
        ),
    ),
    EvalCase(
        id="injury-grealish-risk",
        question="How risky is keeping Grealish in my team?",
        category="injury-concern",
        difficulty="medium",
        expected_tools=frozenset({"query_player", "get_injury_signals", "get_fixture_outlook"}),
        must_mention_players=("Grealish",),
        min_caveats=1,
        pinned_roster_facts=(
            "Grealish present in snapshot with high injury_risk_score "
            "(replaced Maddison who was filtered from the active pool)",
        ),
        judge_rubric=(
            "Risk is decomposed into injury + fixture + form components — all three present.",
            "Concrete numerical injury_risk_score appears in the analysis "
            "(scale: 0-10 integers per the production schema).",
            "Recommendation states a position (hold or transfer) with a price-recovery caveat.",
        ),
    ),
    # -- Differential picks --------------------------------------------------
    # Tests category-error recognition: the agent should refuse to claim
    # "differential" without the data that makes the term meaningful (ownership).
    # "Pick and caveat" was the wrong call — it trains the agent that it can
    # always produce something, which is the FPL-hallucination failure mode.
    EvalCase(
        id="differential-mid-no-ownership-data",
        question="Give me a differential midfielder.",
        category="differential",
        difficulty="hard",
        expected_tools=frozenset({"query_players_by_criteria"}),
        min_caveats=1,
        judge_rubric=(
            "Report explicitly acknowledges that ownership data isn't in the snapshot — the "
            "category that defines 'differential' is missing.",
            "Agent declines to label any pick as 'differential' OR clearly names the proxy used "
            "(e.g. low total_points + good form) and states it isn't equivalent to low ownership.",
            "Caveat states the limitation in plain terms, not buried in hedging language.",
            "If the agent picks at all, it picks on the proxy and names the proxy explicitly.",
        ),
    ),
    # -- Form analysis -------------------------------------------------------
    EvalCase(
        id="form-trending-forwards",
        question="Which forwards are trending up right now?",
        category="form-analysis",
        difficulty="medium",
        expected_tools=frozenset({"query_players_by_criteria"}),
        judge_rubric=(
            "Reasoning references form_trend, not just current form value.",
            "Players returned all have an upward trend (or the caveat explains why a flat-trend "
            "player made the cut).",
            "Ranking explains why one forward edges another beyond raw points.",
        ),
    ),
    EvalCase(
        id="form-falling-off",
        question="Which expensive midfielders have seen their form fall off?",
        category="form-analysis",
        difficulty="hard",
        expected_tools=frozenset({"query_players_by_criteria"}),
        judge_rubric=(
            "'Expensive' is interpreted as a concrete price floor (≥ £9m or similar).",
            "Form decline is supported by form_trend, not just a low current form.",
            "Recommendation names players to consider selling, not just listing the data.",
        ),
    ),
    # -- Squad-aware (require user_squad) ------------------------------------
    EvalCase(
        id="squad-captain-pick",
        question="Who should I captain this week?",
        category="squad-aware",
        difficulty="medium",
        has_user_squad=True,
        expected_tools=frozenset({"query_player", "get_fixture_outlook"}),
        judge_rubric=(
            "Captain pick is one of the user's actual starters (from user_squad).",
            "At least 2 candidates are weighed before the final call.",
            "Fixture outlook is the dominant factor in the verdict.",
            "Recommendation gives a single named captain — not 'either of X or Y'.",
        ),
    ),
    EvalCase(
        id="squad-transfer-out-mid",
        question="Which of my midfielders should I transfer out?",
        category="squad-aware",
        difficulty="hard",
        has_user_squad=True,
        expected_tools=frozenset({"query_player", "get_injury_signals"}),
        judge_rubric=(
            "Only midfielders from the user's squad are considered.",
            "Each candidate is evaluated on form + fixtures + injury, not just one axis.",
            "Recommendation names ONE player to transfer out with reasoning.",
            "Caveat acknowledges price-change risk if the move isn't urgent.",
        ),
    ),
    EvalCase(
        id="squad-bench-strength",
        question="Is my bench strong enough or do I need to upgrade it?",
        category="squad-aware",
        difficulty="medium",
        has_user_squad=True,
        expected_tools=frozenset({"query_player"}),
        judge_rubric=(
            "All four bench players from user_squad are evaluated.",
            "'Strong enough' is operationalised against a concrete bar (e.g. starts-likelihood).",
            "Recommendation gives a binary verdict + one concrete upgrade if needed.",
        ),
    ),
    EvalCase(
        id="squad-bench-or-start-salah",
        question="Salah's fixtures look tough — should I bench him this week?",
        category="squad-aware",
        difficulty="medium",
        has_user_squad=True,
        expected_tools=frozenset({"query_player", "get_fixture_outlook"}),
        must_mention_players=("Salah",),
        pinned_roster_facts=("Salah present in snapshot and in the canned user_squad fixture",),
        judge_rubric=(
            "Verdict is one of {start, bench, captain elsewhere} stated clearly.",
            "Fixture difficulty is the dominant axis given the framing.",
            "Salah's form is weighed against the fixture concern, not ignored.",
            "If 'bench' is suggested, a viable bench-promotion from user_squad is named.",
        ),
    ),
    EvalCase(
        id="squad-gk-upgrade",
        question="Should I upgrade my goalkeeper?",
        category="squad-aware",
        difficulty="medium",
        has_user_squad=True,
        expected_tools=frozenset({"query_player", "query_players_by_criteria"}),
        judge_rubric=(
            "Current GK from user_squad is identified by name and evaluated.",
            "At least one upgrade option is concretely named with price comparison.",
            "Recommendation gives a yes/no with a specific suggested target if yes.",
            "Caveat notes the price differential and timing if a transfer is recommended.",
        ),
    ),
    # -- Vague questions -----------------------------------------------------
    EvalCase(
        id="vague-what-should-i-do",
        question="What should I do?",
        category="vague",
        difficulty="hard",
        expected_tools=frozenset(),  # Reflector may run zero tools and ask for specificity
        min_caveats=1,
        judge_rubric=(
            "Report acknowledges the question is under-specified rather than guessing.",
            "Caveats explicitly call out the missing context (which gameweek, what concern).",
            "Recommendation either asks a clarifying question or offers a structured menu of "
            "common decisions (captain, transfer, chip).",
            "No invented player-specific stats appear.",
        ),
    ),
    EvalCase(
        id="vague-best-player",
        question="Who is the best player?",
        category="vague",
        difficulty="medium",
        expected_tools=frozenset({"query_players_by_criteria"}),
        min_caveats=1,
        judge_rubric=(
            "Analysis defines what 'best' means in this answer (total points / value / form).",
            "Caveats flag the subjectivity of 'best' and the chosen criterion.",
            "Recommendation gives one named player under the chosen definition.",
        ),
    ),
    # -- Unknown player (graceful failure) -----------------------------------
    EvalCase(
        id="unknown-shaqiri",
        question="Tell me about Xherdan Shaqiri.",
        category="unknown-player",
        difficulty="medium",
        expected_tools=frozenset({"query_player"}),
        must_have_empty_players_list=True,
        min_caveats=1,
        pinned_roster_facts=("Shaqiri NOT present in snapshot (out of Premier League)",),
        judge_rubric=(
            "Report acknowledges the player isn't in the dataset — no invented stats.",
            "Caveat explicitly says no data found or player not in current pool.",
            "ScoutReport.players is empty (enforced as hard check, but rubric scores how "
            "gracefully the absence is communicated).",
            "Recommendation either declines or suggests a similar-archetype alternative.",
        ),
    ),
    EvalCase(
        id="unknown-john-smith",
        question="How is John Smith performing this season?",
        category="unknown-player",
        difficulty="medium",
        expected_tools=frozenset({"query_player"}),
        must_have_empty_players_list=True,
        min_caveats=1,
        pinned_roster_facts=("No 'John Smith' present in snapshot",),
        judge_rubric=(
            "Report acknowledges no match — no invented stats.",
            "ScoutReport.players is empty (enforced as hard check).",
            "Caveat is specific about what failed (lookup) rather than generic.",
        ),
    ),
    # -- Multi-position comparison -------------------------------------------
    EvalCase(
        id="multipos-7m-mid-vs-fwd",
        question="At £7m, should I get a midfielder or a forward?",
        category="multi-position",
        difficulty="hard",
        expected_tools=frozenset({"query_players_by_criteria"}),
        must_set_comparison=True,
        judge_rubric=(
            "Both positions are surveyed at the same price point.",
            "Reasoning weighs position-specific factors (mid double-up, fwd ceiling).",
            "comparison.winner is set to one position OR one specific player.",
            "Recommendation names a concrete pick, not 'either is fine'.",
        ),
    ),
    EvalCase(
        id="multipos-best-value-85m",
        question="Best value pick at £8.5m — defender, mid, or forward?",
        category="multi-position",
        difficulty="hard",
        expected_tools=frozenset({"query_players_by_criteria"}),
        judge_rubric=(
            "All three positions are surveyed at or below £8.5m.",
            "'Value' is defined concretely (points-per-million or similar).",
            "Recommendation names one position AND one specific player within it.",
            "Top candidate from each position is mentioned in the analysis.",
        ),
    ),
    # -- Edge cases ----------------------------------------------------------
    EvalCase(
        id="edge-partial-name-bukayo",
        question="What about Bukayo?",
        category="edge-case",
        difficulty="medium",
        expected_tools=frozenset({"query_player"}),
        must_mention_players=("Saka",),
        # Partial-name match by design: "Bukayo" alone should resolve to "Saka".
        # Disable word-boundary so the substring matcher does the right thing.
        # (Original Trent → Alexander-Arnold case rotted when TAA left Liverpool;
        # Virgil → van Dijk would have semantically broken because FPL stores
        # van Dijk's web_name as "Virgil" — no aliasing needed for that lookup.)
        match_word_boundary=False,
        pinned_roster_facts=(
            "Saka present in snapshot (Bukayo → Saka first-name-to-surname aliasing)",
        ),
        judge_rubric=(
            "First-name lookup resolves to Saka without prompting the user.",
            "Caveat may note the assumption made if the question was ambiguous.",
            "Analysis treats the question as a general 'how is he doing' query.",
        ),
    ),
    EvalCase(
        id="edge-three-way-comparison",
        question="Saka or Palmer or Foden?",
        category="edge-case",
        difficulty="hard",
        expected_tools=frozenset({"query_player", "get_fixture_outlook"}),
        must_mention_players=("Saka", "Palmer", "Foden"),
        must_set_comparison=True,
        pinned_roster_facts=(
            "Saka present in snapshot",
            "Palmer present in snapshot",
            "Foden present in snapshot",
        ),
        judge_rubric=(
            "comparison.players has exactly 3 entries.",
            "comparison.winner is set to one of the three OR null with explicit reasoning.",
            "Reasoning addresses each player's distinct edge — not just ranks them.",
        ),
    ),
)


def get_cases_by_category(category: Category) -> tuple[EvalCase, ...]:
    """Filter the eval set to one category — used for partial runs during iteration."""
    return tuple(c for c in EVAL_CASES if c.category == category)


def get_case_by_id(case_id: str) -> EvalCase:
    """Look up a single case by id. Raises ``KeyError`` if not found."""
    for c in EVAL_CASES:
        if c.id == case_id:
            return c
    raise KeyError(f"No eval case with id {case_id!r}")
