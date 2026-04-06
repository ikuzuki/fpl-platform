"""Shared fixtures for integration tests using moto (in-memory AWS)."""

import json
from collections.abc import Generator
from typing import Any

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from moto import mock_aws

TEST_BUCKET = "fpl-data-lake-test"
TEST_REGION = "eu-west-2"
TEST_SEASON = "2025-26"
TEST_GAMEWEEK = 31


@pytest.fixture()
def aws_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set dummy AWS env vars so boto3 doesn't look for real credentials."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", TEST_REGION)


@pytest.fixture()
def moto_s3(aws_env: None) -> Generator[str, None, None]:
    """Create an in-memory S3 bucket via moto and yield the bucket name."""
    with mock_aws():
        client = boto3.client("s3", region_name=TEST_REGION)
        client.create_bucket(
            Bucket=TEST_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": TEST_REGION},
        )
        yield TEST_BUCKET


# ---------------------------------------------------------------------------
# Seed data fixtures
# ---------------------------------------------------------------------------


def _bootstrap_raw() -> dict[str, Any]:
    """Realistic raw FPL bootstrap-static response (5 players, 2 teams)."""
    return {
        "elements": [
            _make_player(
                1,
                "Haaland",
                "Erling",
                "Haaland",
                13,
                4,
                144,
                197,
                2413,
                22,
                7,
                10,
                27,
                1,
                0,
                35,
                786,
                28,
                "21.06",
                "1.94",
                "23.00",
                "2.0",
                "6.8",
                "55.0",
                "a",
                "",
                100,
                81351,
                69718,
                "977.0",
                "264.7",
                "1217.0",
                "246.0",
            ),
            _make_player(
                2,
                "Saka",
                "Bukayo",
                "Saka",
                1,
                3,
                110,
                155,
                2200,
                10,
                12,
                6,
                20,
                2,
                0,
                20,
                600,
                26,
                "8.50",
                "7.00",
                "15.50",
                "7.0",
                "6.0",
                "30.0",
                "a",
                "",
                100,
                50000,
                10000,
                "800.0",
                "900.0",
                "700.0",
                "240.0",
            ),
            _make_player(
                3,
                "B.Fernandes",
                "Bruno",
                "Fernandes",
                14,
                3,
                103,
                189,
                2435,
                8,
                17,
                4,
                39,
                3,
                0,
                36,
                795,
                28,
                "10.32",
                "9.03",
                "19.35",
                "11.5",
                "6.8",
                "44.7",
                "a",
                "",
                100,
                156843,
                5157,
                "1030.4",
                "1467.1",
                "510.0",
                "301.0",
            ),
            _make_player(
                4,
                "Chalobah",
                "Trevoh",
                "Chalobah",
                14,
                2,
                45,
                30,
                500,
                0,
                0,
                1,
                15,
                3,
                0,
                1,
                50,
                5,
                "0.20",
                "0.30",
                "0.50",
                "0.5",
                "1.5",
                "2.0",
                "a",
                "",
                75,
                142,
                281314,
                "50.0",
                "20.0",
                "10.0",
                "8.0",
            ),
            _make_player(
                5,
                "Ederson",
                "Ederson",
                "Moraes",
                13,
                1,
                55,
                120,
                2700,
                0,
                0,
                15,
                25,
                1,
                0,
                10,
                400,
                30,
                "0.00",
                "0.50",
                "0.50",
                "4.0",
                "4.0",
                "12.0",
                "a",
                "",
                100,
                20000,
                5000,
                "30.0",
                "10.0",
                "5.0",
                "4.5",
            ),
        ],
        "teams": [
            {"id": 1, "name": "Arsenal", "short_name": "ARS"},
            {"id": 13, "name": "Man City", "short_name": "MCI"},
            {"id": 14, "name": "Man Utd", "short_name": "MUN"},
        ],
        "events": [
            {"id": 31, "finished": True, "is_current": True},
        ],
    }


def _make_player(
    pid: int,
    web_name: str,
    first_name: str,
    second_name: str,
    team: int,
    element_type: int,
    now_cost: int,
    total_points: int,
    minutes: int,
    goals_scored: int,
    assists: int,
    clean_sheets: int,
    goals_conceded: int,
    yellow_cards: int,
    red_cards: int,
    bonus: int,
    bps: int,
    starts: int,
    expected_goals: str,
    expected_assists: str,
    expected_goal_involvements: str,
    form: str,
    points_per_game: str,
    selected_by_percent: str,
    status: str,
    news: str,
    chance_of_playing_next_round: int,
    transfers_in_event: int,
    transfers_out_event: int,
    influence: str,
    creativity: str,
    threat: str,
    ict_index: str,
) -> dict[str, Any]:
    return {
        "id": pid,
        "web_name": web_name,
        "first_name": first_name,
        "second_name": second_name,
        "team": team,
        "element_type": element_type,
        "now_cost": now_cost,
        "total_points": total_points,
        "minutes": minutes,
        "goals_scored": goals_scored,
        "assists": assists,
        "clean_sheets": clean_sheets,
        "goals_conceded": goals_conceded,
        "yellow_cards": yellow_cards,
        "red_cards": red_cards,
        "bonus": bonus,
        "bps": bps,
        "starts": starts,
        "expected_goals": expected_goals,
        "expected_assists": expected_assists,
        "expected_goal_involvements": expected_goal_involvements,
        "form": form,
        "points_per_game": points_per_game,
        "selected_by_percent": selected_by_percent,
        "status": status,
        "news": news,
        "chance_of_playing_next_round": chance_of_playing_next_round,
        "transfers_in_event": transfers_in_event,
        "transfers_out_event": transfers_out_event,
        "influence": influence,
        "creativity": creativity,
        "threat": threat,
        "ict_index": ict_index,
    }


def _understat_data() -> list[dict[str, Any]]:
    """Understat stats for Haaland + Saka (others unmatched → null xG)."""
    return [
        {
            "player_name": "Erling Haaland",
            "xG": "23.14",
            "xA": "4.77",
            "npxG": "20.09",
            "npg": "19",
            "shots": "102",
            "key_passes": "21",
            "xGChain": "26.24",
            "xGBuildup": "4.13",
        },
        {
            "player_name": "Bukayo Saka",
            "xG": "9.00",
            "xA": "8.00",
            "npxG": "8.50",
            "npg": "9",
            "shots": "60",
            "key_passes": "40",
            "xGChain": "15.00",
            "xGBuildup": "6.00",
        },
    ]


def _fixtures_raw() -> list[dict[str, Any]]:
    """Raw fixtures JSON with 4 GWs, 3 fixtures each."""
    fixtures = []
    teams = [(1, 13), (14, 1), (13, 14)]  # home, away pairs
    for gw in range(31, 35):
        for home, away in teams:
            fixtures.append(
                {
                    "id": gw * 100 + home,
                    "event": gw,
                    "team_h": home,
                    "team_a": away,
                    "team_h_difficulty": 3,
                    "team_a_difficulty": 3,
                    "kickoff_time": f"2026-04-{gw - 26:02d}T15:00:00Z",
                }
            )
    return fixtures


@pytest.fixture()
def seed_raw_data(moto_s3: str) -> str:
    """Write minimal raw data (bootstrap, fixtures, understat) to moto S3."""
    client = boto3.client("s3", region_name=TEST_REGION)
    season = TEST_SEASON
    ts = "2026-04-05T08-00-00"

    # Bootstrap
    client.put_object(
        Bucket=moto_s3,
        Key=f"raw/fpl-api/season={season}/bootstrap/{ts}.json",
        Body=json.dumps(_bootstrap_raw()),
    )

    # Fixtures
    client.put_object(
        Bucket=moto_s3,
        Key=f"raw/fpl-api/season={season}/fixtures/{ts}.json",
        Body=json.dumps(_fixtures_raw()),
    )

    # Understat
    client.put_object(
        Bucket=moto_s3,
        Key=f"raw/understat/season={season}/league_stats/{ts}.json",
        Body=json.dumps(_understat_data()),
    )

    return moto_s3


@pytest.fixture()
def seed_clean_data(seed_raw_data: str) -> str:
    """Run transform logic and write clean Parquet to moto S3.

    This builds on seed_raw_data so raw files are also present.
    """
    from fpl_data.transformers.player_transformer import (
        deduplicate,
        flatten_player_data,
        join_understat,
    )

    bootstrap = _bootstrap_raw()
    understat = _understat_data()

    df = flatten_player_data(bootstrap, TEST_SEASON)
    df = join_understat(df, understat)
    df = deduplicate(df, ["id"])

    table = pa.Table.from_pandas(df)
    import io

    buf = io.BytesIO()
    pq.write_table(table, buf, compression="zstd")
    buf.seek(0)

    client = boto3.client("s3", region_name=TEST_REGION)
    client.put_object(
        Bucket=seed_raw_data,
        Key=f"clean/players/season={TEST_SEASON}/gameweek={TEST_GAMEWEEK:02d}/players.parquet",
        Body=buf.getvalue(),
    )

    return seed_raw_data


@pytest.fixture()
def seed_enriched_data(seed_clean_data: str) -> str:
    """Write pre-built enriched Parquet to moto S3.

    Uses the same 4-player enriched data structure as curate's conftest,
    plus the 5th unenriched player.
    """
    enriched_rows = _build_enriched_rows()
    table = pa.Table.from_pylist(enriched_rows)

    import io

    buf = io.BytesIO()
    pq.write_table(table, buf, compression="zstd")
    buf.seek(0)

    client = boto3.client("s3", region_name=TEST_REGION)
    client.put_object(
        Bucket=seed_clean_data,
        Key=f"enriched/player_summaries/season={TEST_SEASON}/gameweek={TEST_GAMEWEEK:02d}/summaries.parquet",
        Body=buf.getvalue(),
    )

    return seed_clean_data


def _build_enriched_rows() -> list[dict[str, Any]]:
    """Build enriched player rows with LLM enrichment columns.

    Uses the production prefix convention (player_summary_, injury_signal_, etc.)
    matching what merge_enrichments.py produces.
    """
    base_players = _bootstrap_raw()["elements"]
    understat = _understat_data()

    from fpl_data.transformers.player_transformer import flatten_player_data, join_understat

    df = flatten_player_data({"elements": base_players}, TEST_SEASON)
    df = join_understat(df, understat)
    players = df.to_dict("records")

    enrichment_data = {
        1: {  # Haaland
            "player_summary_summary": "Haaland has delivered 22 goals and 7 assists this season.",
            "player_summary_form_trend": "stable",
            "player_summary_confidence": 0.95,
            "injury_signal_risk_score": 0,
            "injury_signal_reasoning": "No injury concerns.",
            "injury_signal_injury_type": None,
            "injury_signal_sources": [],
            "sentiment_sentiment": "positive",
            "sentiment_score": 0.85,
            "sentiment_key_themes": ["clinical", "prolific"],
            "fixture_outlook_difficulty_score": 3,
            "fixture_outlook_recommendation": "Hold — mixed fixtures ahead.",
            "fixture_outlook_best_gameweeks": [33, 35],
        },
        2: {  # Saka
            "player_summary_summary": "Saka is a consistent performer on the right wing this season.",
            "player_summary_form_trend": "improving",
            "player_summary_confidence": 0.90,
            "injury_signal_risk_score": 2,
            "injury_signal_reasoning": "Minor knock reported.",
            "injury_signal_injury_type": "knock",
            "injury_signal_sources": ["BBC Sport"],
            "sentiment_sentiment": "positive",
            "sentiment_score": 0.6,
            "sentiment_key_themes": ["creative", "consistent"],
            "fixture_outlook_difficulty_score": 4,
            "fixture_outlook_recommendation": "Tough run ahead.",
            "fixture_outlook_best_gameweeks": [35, 36],
        },
        3: {  # B.Fernandes
            "player_summary_summary": "Bruno Fernandes in strong form with high assist returns.",
            "player_summary_form_trend": "improving",
            "player_summary_confidence": 0.88,
            "injury_signal_risk_score": 0,
            "injury_signal_reasoning": "No injury data.",
            "injury_signal_injury_type": None,
            "injury_signal_sources": [],
            "sentiment_sentiment": "neutral",
            "sentiment_score": 0.0,
            "sentiment_key_themes": ["no coverage"],
            "fixture_outlook_difficulty_score": 3,
            "fixture_outlook_recommendation": "GW32 home fixture is favorable.",
            "fixture_outlook_best_gameweeks": [32, 34, 35],
        },
        4: {  # Chalobah
            "player_summary_summary": "Chalobah has struggled for consistent game time this season.",
            "player_summary_form_trend": "declining",
            "player_summary_confidence": 0.70,
            "injury_signal_risk_score": 5,
            "injury_signal_reasoning": "Limited minutes suggest fitness concern.",
            "injury_signal_injury_type": None,
            "injury_signal_sources": [],
            "sentiment_sentiment": "negative",
            "sentiment_score": -0.4,
            "sentiment_key_themes": ["benched", "transfer rumours"],
            "fixture_outlook_difficulty_score": 3,
            "fixture_outlook_recommendation": "Mixed fixtures.",
            "fixture_outlook_best_gameweeks": [32],
        },
    }

    enriched = []
    for player in players:
        row = dict(player)
        pid = row["id"]
        if pid in enrichment_data:
            row.update(enrichment_data[pid])
        enriched.append(row)

    return enriched
