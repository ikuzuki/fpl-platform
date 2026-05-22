# Scout Agent — Eval Baseline (v1.1)

First baseline run of the agent evaluation framework against the production-data snapshot. This document is the canonical write-up of methodology, results, and known calibration deltas for the framework described in [`services/agent/src/fpl_agent/evaluation/`](../../services/agent/src/fpl_agent/evaluation/). Raw results in [`baseline-v1.1.json`](baseline-v1.1.json). Closes [#95](https://github.com/ikuzuki/fpl-platform/issues/95).

## Headline

| Metric | Value |
|---|---|
| Cases run | 29 |
| Hard-check pass rate | **24 / 29 (82.8%)** |
| Mean judge score | **4.36 / 5** |
| Eval cases version | `v1.1` |
| Snapshot version | `player_db_v1` (300 players, GW32, 2025–26 season) |
| Run cost | ~£1.50 (Anthropic API) |
| Wall time | ~6 min at concurrency 3 |

Hard-check pass rate sits above the 0.8 threshold (CLI exit 0). The interesting signal is in the failures and the calibration deltas, not the headline number.

## What the framework measures

Each case carries two grading layers, applied independently:

1. **Hard checks** — six deterministic checks per case, no LLM involved. They cover tool routing (`expected_tools`, `forbidden_tools`), narrative content (`must_mention_players` with word-boundary regex), schema shape (`must_set_comparison`, `must_have_empty_players_list`), and caveat discipline (`min_caveats`). Pass/fail is binary. `EvalResult.passed` is the conjunction of every hard check on the case.
2. **Judge verdict** — Claude Haiku scores 3–5 case-specific rubric bullets on a 1–5 scale using `JudgeVerdict.model_json_schema()` for structured output. Bullet count is enforced as a hard contract — mismatched counts raise rather than partial-grade silently.

The two layers measure different things on purpose. Hard checks catch structural failure modes that would slip past prose-level scoring (e.g. invented PlayerAnalysis entries with placeholder stats — see [Notable findings](#notable-findings)). The judge catches narrative quality that no rule can encode (e.g. "the recommendation states a position; doesn't hedge"). Either alone would miss a class of failures the other catches.

Data anchoring is the third axis. Every tool the graph uses reads from a parquet snapshot of `player_embeddings` committed at [`tests/fixtures/player_db_v1.parquet`](../../services/agent/tests/fixtures/player_db_v1.parquet), via a pandas-backed parallel tool registry that mirrors the production pgvector SQL semantics. Scores are deterministic across gameweeks and don't drift with real Premier League results.

## Results by category

| Category | Pass | Mean judge |
|---|---|---|
| comparison | 3/3 (100%) | 4.58 |
| criteria-search | 4/4 (100%) | 4.74 |
| differential | 1/1 (100%) | 4.00 |
| edge-case | 2/2 (100%) | 4.35 |
| form-analysis | 2/2 (100%) | 4.35 |
| injury-concern | 2/2 (100%) | 4.50 |
| multi-position | 2/2 (100%) | 4.75 |
| single-player | 4/4 (100%) | 4.54 |
| **squad-aware** | **2/5 (40%)** | **3.61** |
| **unknown-player** | **0/2 (0%)** | **3.98** |
| vague | 2/2 (100%) | 4.53 |

Nine of eleven categories at 100% pass rate. Two failure clusters, very different stories — analysed below.

## Results by difficulty

| Difficulty | Pass | Mean judge |
|---|---|---|
| easy | 6/6 (100%) | 4.81 |
| medium | 12/16 (75%) | 4.14 |
| hard | 6/7 (85.7%) | 4.46 |

Medium has the lowest pass rate despite hard being a smaller sample. Worth a follow-up at v1.2 — the medium-vs-hard distinction may be miscalibrated.

## Notable findings

### Finding 1 — Unknown-player fabrication is the dominant failure mode

Both unknown-player cases (`unknown-shaqiri`, `unknown-john-smith`) failed the `must_have_empty_players_list` hard check. In both, the agent correctly identified that the player wasn't in the database, gave the right recommendation ("can't pick him"), and exhaustively caveated. But it still filled the `ScoutReport.players[]` slot with a placeholder entry (`price=£0.0`, `form=0.0`, `confidence=0.1`) and explained the placeholders inline.

This is the exact failure mode the `must_have_empty_players_list` check was designed to catch — and it almost shipped as a no-op `must_mention_players=()` tuple (which always trivially passes) before the eval set was reviewed. The hard check now does real work.

**Why this matters:** the prose layer is excellent and Haiku judged it accordingly (4.25 and 3.70). A judge-only eval would have flagged these as marginal passes. The hard check correctly surfaces them as structural failures — a downstream consumer reading just `players[]` would see "Xherdan Shaqiri, MID, £0.0m" and misread the response. This is the case for *both* grading layers existing.

Action for v1.2: the recommender prompt needs an explicit "if tool calls returned no data, leave `players` empty" instruction. Hard check stays; rubric bullet 3 on these cases can be retired (it duplicates the hard check signal).

### Finding 2 — Squad-aware cluster surfaces a planner-prompt design issue

Two squad-aware cases (`squad-transfer-out-mid`, `squad-bench-or-start-salah`) failed because the planner didn't call `query_player`. It called `get_fixture_outlook` and `get_injury_signals` but skipped the underlying player lookup. Two interpretations:

- *Agent doing the right thing:* the `user_squad` payload in the planner prompt carries `web_name`, `price`, and `team_name` — the planner concluded it had enough player identity context and skipped the data fetch.
- *Agent missing fresh data:* the squad payload doesn't carry current form, total_points, or injury status. The targeted tools provide partial coverage but not the full row.

Looking at the actual `ScoutReport` analyses, the agent extracted form numbers from `get_injury_signals` (which incidentally returns `form_trend`). So it had partial form data without explicitly calling `query_player`. The hard check correctly flagged the missing tool, but the agent's reasoning isn't structurally broken — it's running on incomplete data and unaware of the gap.

Action for v1.2: the planner prompt should distinguish between "what the squad gives you" (player identity) and "what tools give you" (live stats). One line of prompt text.

### Finding 3 — A rate-limit infrastructure failure, not an agent failure

`squad-gk-upgrade` crashed with a 429 from Anthropic — the recommender call needed 26,935 input tokens which, at concurrency 3, saturated the 50K input-tokens-per-minute Haiku tier. The Anthropic SDK retried four times then gave up. Re-running the case alone at concurrency 1 produced a clean PASS with judge 4.30/5.

Worth surfacing because it's the kind of failure that gets misread as an agent quality issue if you only look at the hard-check column. The framework distinguishes graph-invocation errors from agent-output errors via the `error` field on `EvalResult` — visible in the JSON, easy to filter.

## Calibration

A judge that's systematically too lenient or too harsh produces meaningless scores. Calibration step: three representative cases hand-rated against the rubric without looking at Haiku's scores, then compared.

| Case | Bullets | Human mean | Haiku mean | Delta |
|---|---|---|---|---|
| comparison-watkins-vs-isak | 3 | 4.00 | 5.00 | −1.00 |
| unknown-shaqiri | 4 | 4.50 | 4.25 | +0.25 |
| squad-bench-or-start-salah | 4 | 4.00 | 2.75 | +1.25 |
| **Mean absolute delta across 11 bullets** | | | | **1.00** |

Three findings from the calibration exercise:

1. **Judge is generous at the top of the scale.** On `comparison-watkins-vs-isak` bullet 3 (*"both forwards' goal threat and form are addressed"*), Haiku scored 5/5 — read literally, both axes were mentioned. The human reviewer gave 3/5 because the analysis spent most of its depth on Watkins with Isak's coverage feeling thinner. The rubric language is too soft. v1.2 fix: tighten to "both forwards get comparable analytical depth, not just both mentioned."

2. **Judge is honest at the bottom.** On `unknown-shaqiri` bullet 3 (the structural emptiness check), Haiku gave 2/5, human gave 3/5. Both recognised the fabrication; human was slightly more lenient. No rubric change needed — the hard check is authoritative and the rubric bullet should be retired (duplicates signal).

3. **Judge reads rubrics literally; humans compensate for broken premises.** On `squad-bench-or-start-salah` bullet 1 (*"verdict is one of {start, bench, captain elsewhere}"*), Haiku gave 1/5 because the agent didn't deliver the requested verdict shape. Human gave 5/5 because the agent correctly noticed the rubric premise was broken (Salah wasn't in the canned squad) and pivoted to the closest defensible answer. The judge was right about the literal rubric; the rubric was the problem.

This is the headline calibration insight. **The judge faithfully measures what you write. If the rubric premise breaks, the judge punishes the agent for handling it intelligently. Humans naturally compensate; judges don't.** The implication is methodological, not numerical: rubric design is the load-bearing piece of the framework, not the model choice.

Action for v1.2 — already applied to the codebase:

- `canned_user_squad` now accepts `must_include_web_names` (default `("Salah",)`). Any squad-aware case that names a specific player can rely on that player being in the squad. Implementation: insert at squad position 1 (= second MID starter), so the named player is owned-and-played-but-not-captained, which is the realistic test condition.

**Validation re-run** ([`baseline-v1.1-case3-rerun.json`](baseline-v1.1-case3-rerun.json)): with the fix applied, `squad-bench-or-start-salah` flipped from FAIL (judge 2.75) to **PASS (judge 4.80)** — a +2.05 delta. The agent now produces a clean start/bench verdict against the Salah-in-squad fixture. This validates two things at once: the fix works, and the calibration delta on this case was rubric-design-driven (not judge-bias-driven) — confirmed because the same judge, same agent, same prompt now scores 4.80 once the rubric premise holds.

Effective baseline with the fix applied is 25/29 (86.2%) hard-check pass rate. The original v1.1 numbers (24/29 in `baseline-v1.1.json`) remain the canonical first-run record — re-running the full suite for a refreshed pass-rate is a v1.2 task once the other v1.2 changelog items below land too.

## Limitations of this baseline

Honest about what the framework deliberately doesn't measure:

- **No chip-strategy / DGW / BGW coverage.** The current tool set has no concept of gameweeks or chips, so adding cases the agent literally cannot answer would only inflate the zero-score column. The framework can be extended once `query_gameweek_fixtures` and chip-aware state land.
- **Approximate cosine similarity, not pgvector IVFFlat.** The fixture tools use exact numpy cosine; production uses pgvector's IVFFlat approximation. Neighbour ordering can differ at the margins. `search_similar_players` isn't in any case's `expected_tools` set, so this never reaches a graded path — but the divergence exists.
- **Single judge model.** Haiku is consistent enough at this rubric structure (calibration above), but a second-judge cross-check with Sonnet would catch judge-model bias. Worth doing on a v1.2 baseline as a one-time sanity pass.
- **Clean phrasing only.** Every question is grammatically complete. A v2 eval set with scrappy real-user phrasing (typos, fragments) is a separate rubric — mixing them muddies what's being measured.

## v1.2 changelog

Shipped in this PR (validated against the case-3 rerun):

- ✅ `canned_user_squad` force-include for squad-aware cases that name a specific player

Planned for v1.2:

- Tighten `comparison-watkins-vs-isak` rubric bullet 3 (analytical depth, not just mention)
- Retire `unknown-shaqiri` and `unknown-john-smith` rubric bullet 3 (duplicates hard check)
- Add planner-prompt note distinguishing squad-context from tool-data
- Add "leave players[] empty when no data" recommender-prompt instruction
- Cross-validate with a Sonnet second-judge on a sampled subset
- Full suite re-run once the above land, producing a v1.2 baseline JSON

## Reproducing this run

```bash
# Set credentials (Anthropic for graph + judge; Neon only for snapshot regen)
export ANTHROPIC_API_KEY=sk-ant-...
export NEON_DATABASE_URL=postgres://...   # only if regenerating the snapshot

# Regenerate the snapshot if needed (asserts pinned roster facts before writing)
python services/agent/scripts/snapshot_player_db.py

# Run the eval
python services/agent/scripts/run_evals.py \
    --concurrency 3 \
    --output docs/evals/baseline-v1.1.json

# Inspect specific cases
python services/agent/scripts/run_evals.py \
    --case-ids unknown-shaqiri,squad-bench-or-start-salah \
    --concurrency 1
```

Reproducibility checklist:

- Snapshot version pinned in `EvalSummary.snapshot_version` (currently `player_db_v1`)
- Eval cases version pinned in `EvalSummary.eval_cases_version` (currently `v1.1`)
- Judge prompt versioned at `evaluation/prompts/v1/judge.md` — bump to `v2/` on meaningful changes
- All eval source code under `services/agent/src/fpl_agent/evaluation/` with 34 unit tests in `tests/test_evaluation.py`

## Cost and run-time

| | Per case | Per run (29 cases) |
|---|---|---|
| Planner + reflector (Haiku ×2 iters typical) | ~$0.004 | ~$0.12 |
| Recommender (Sonnet ×1) | ~$0.027 | ~$0.78 |
| Judge (Haiku ×1) | ~$0.005 | ~$0.15 |
| **Total** | **~$0.04** | **~$1.05** |

Wall time: ~6 minutes at concurrency 3, ~15 minutes serial. Concurrency above 3 risks rate-limit thrashing on the Haiku 50K-input-tokens-per-minute tier.

## What this is for

This framework exists because the gap between "I built an agent and it works" and "I built an agent and here's what it measurably gets right, wrong, and how those numbers move when I change something" is the gap between a tutorial project and production-grade engineering. The eval is the discipline most LLM agent work skips, and the failures it surfaces — especially the unknown-player fabrication finding — are the kind of failure mode every production LLM system has to handle but few measure.
