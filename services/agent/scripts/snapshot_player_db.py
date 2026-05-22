"""Generate the eval snapshot from live Neon.

One-shot script: pulls every row from ``player_embeddings``, validates that
every eval case's assumptions hold against the new data, and writes
``tests/fixtures/player_db_v1.parquet``.

Validation runs BEFORE writing, not after — so a snapshot that would
silently break the eval set is rejected. Two assertion layers:

1. **Schema** — every column in
   :data:`fpl_agent.evaluation.fixture_data.REQUIRED_COLUMNS` must be
   present. A missing column means the table schema drifted and the eval
   tools won't work; fix the snapshot script or migrate the eval.
2. **Pinned facts** — every case's ``must_mention_players`` must resolve
   to a row, and every ``must_have_empty_players_list=True`` case's
   inferred unknown-player name must NOT resolve. Cases that fail either
   check are listed and the script refuses to write unless
   ``--allow-missing-players`` is passed.

Usage:
    export NEON_DATABASE_URL=postgres://...
    python services/agent/scripts/snapshot_player_db.py

Add ``--allow-missing-players`` to override the pinned-fact gate during
partial-snapshot iteration (rare; usually a sign the eval cases need
updating, not the snapshot).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from fpl_agent.evaluation.eval_cases import EVAL_CASES, EvalCase
from fpl_agent.evaluation.fixture_data import DEFAULT_FIXTURE_PATH, REQUIRED_COLUMNS
from fpl_lib.clients.neon import NeonClient

logger = logging.getLogger(__name__)

# Used to extract the "unknown player" name from the question text on
# must_have_empty_players_list cases — we want to assert that name isn't in
# the snapshot. Matches "Xherdan Shaqiri" or "John Smith". Falls back to
# scanning pinned_roster_facts when the heuristic fails.
_NAME_PATTERN = re.compile(r"\b([A-Z][a-z]+(?:[\s-][A-Z][a-z]+)+)\b")


async def fetch_player_data(database_url: str) -> pd.DataFrame:
    """Pull every row from player_embeddings and coerce to a parquet-ready DataFrame."""
    async with NeonClient(database_url) as neon:
        records = await neon.fetch("SELECT * FROM player_embeddings")
    if not records:
        raise RuntimeError("player_embeddings returned zero rows — refusing to snapshot.")
    rows = [dict(r) for r in records]
    df = pd.DataFrame(rows)
    if "embedding" in df.columns:
        df["embedding"] = df["embedding"].apply(_normalise_embedding)
    return df


def _normalise_embedding(value: Any) -> list[float]:
    """Coerce a pgvector value to a list[float] parquet can store.

    pgvector returns either a list-like (when ``pgvector.asyncpg`` is
    registered on the pool) or its text representation ``"[0.1,0.2,...]"``
    when not. Handle both shapes so the snapshot script works in either
    environment without depending on extension registration order.
    """
    if isinstance(value, str):
        cleaned = value.strip("[]")
        if not cleaned:
            return []
        return [float(x) for x in cleaned.split(",")]
    if hasattr(value, "tolist"):
        return [float(x) for x in value.tolist()]
    return [float(x) for x in value]


def assert_pinned_players_present(df: pd.DataFrame) -> list[str]:
    """Verify every ``must_mention_players`` entry resolves in the snapshot."""
    issues: list[str] = []
    web_names_lower = df["web_name"].astype(str).str.lower().tolist()

    for case in EVAL_CASES:
        if case.must_have_empty_players_list:
            # The whole point of these cases is the player isn't present.
            continue
        for player in case.must_mention_players:
            if not _name_in_snapshot(player, web_names_lower):
                issues.append(f"{case.id}: required player {player!r} not found in snapshot")
    return issues


def assert_unknown_players_absent(df: pd.DataFrame) -> list[str]:
    """For unknown-player cases, verify the named player is NOT in the snapshot.

    If we silently add (e.g.) Xherdan Shaqiri to the dataset, the
    ``unknown-shaqiri`` case becomes meaningless — the agent would find
    real data and the rubric would no longer test the "no fabrication"
    failure mode.
    """
    issues: list[str] = []
    web_names_lower = df["web_name"].astype(str).str.lower().tolist()

    for case in EVAL_CASES:
        if not case.must_have_empty_players_list:
            continue
        unknown_name = _infer_unknown_name(case)
        if unknown_name is None:
            logger.warning(
                "Could not infer unknown-player name for %s — manual review needed.",
                case.id,
            )
            continue
        if _name_in_snapshot(unknown_name, web_names_lower):
            issues.append(
                f"{case.id}: {unknown_name!r} unexpectedly present in snapshot — "
                f"case 'unknown-player' premise is broken."
            )
    return issues


def _infer_unknown_name(case: EvalCase) -> str | None:
    """Extract the unknown-player name from the question or pinned_roster_facts.

    Tries the question first ("Tell me about Xherdan Shaqiri." → "Xherdan
    Shaqiri"), falls back to scanning ``pinned_roster_facts`` for entries
    that say "NOT present" or similar.
    """
    matches = _NAME_PATTERN.findall(case.question)
    if matches:
        # First multi-word capitalised span is almost always the player name.
        return matches[0]
    for fact in case.pinned_roster_facts:
        if "NOT present" in fact or "not present" in fact:
            # "Shaqiri NOT present in snapshot (...)" → "Shaqiri"
            return fact.split(" NOT present")[0].split(" not present")[0].strip()
    return None


def _name_in_snapshot(player: str, web_names_lower: list[str]) -> bool:
    """Mirror the production ILIKE behaviour: case-insensitive substring match."""
    needle = player.lower()
    return any(needle in name for name in web_names_lower)


def write_human_review_log(df: pd.DataFrame, path: Path) -> None:
    """Dump every pinned_roster_fact + a small dataset summary so the human can eyeball."""
    seen_facts: set[str] = set()
    for case in EVAL_CASES:
        for fact in case.pinned_roster_facts:
            seen_facts.add(fact)

    summary = {
        "row_count": len(df),
        "unique_teams": int(df["team_name"].nunique()) if "team_name" in df.columns else None,
        "positions": (
            df["position"].value_counts().to_dict() if "position" in df.columns else None
        ),
        "pinned_roster_facts": sorted(seen_facts),
    }
    path.write_text(json.dumps(summary, indent=2, default=str) + "\n")
    logger.info("Wrote snapshot review log to %s", path)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_FIXTURE_PATH,
        help=f"Output parquet path (default: {DEFAULT_FIXTURE_PATH})",
    )
    parser.add_argument(
        "--allow-missing-players",
        action="store_true",
        help="Don't fail if pinned players are missing or unknown-player premises break.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    database_url = os.environ.get("NEON_DATABASE_URL")
    if not database_url:
        logger.error("NEON_DATABASE_URL is not set — refusing to run without a connection string.")
        return 2

    logger.info("Fetching player_embeddings from Neon ...")
    df = await fetch_player_data(database_url)
    logger.info("Fetched %d rows", len(df))

    missing_cols = REQUIRED_COLUMNS - set(df.columns)
    if missing_cols:
        logger.error("Snapshot is missing required columns: %s", sorted(missing_cols))
        return 3

    present_issues = assert_pinned_players_present(df)
    absent_issues = assert_unknown_players_absent(df)
    issues = present_issues + absent_issues

    if issues:
        logger.warning("Eval-case assumption issues detected:")
        for issue in issues:
            logger.warning("  - %s", issue)
        if not args.allow_missing_players:
            logger.error(
                "Refusing to write snapshot with %d unsatisfied case assumptions. "
                "Re-run with --allow-missing-players to override (and update eval_cases.py).",
                len(issues),
            )
            return 4
    else:
        logger.info("All %d eval cases' pinned facts satisfied.", len(EVAL_CASES))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.output, compression="zstd")
    logger.info("Wrote snapshot to %s (%d rows)", args.output, len(df))

    review_log = args.output.with_suffix(".review.json")
    write_human_review_log(df, review_log)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
