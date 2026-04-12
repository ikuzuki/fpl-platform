"""Tests for sync_embeddings."""

from unittest.mock import AsyncMock, MagicMock

import pyarrow as pa
import pytest

from fpl_agent.embeddings.embedder import PlayerEmbedder
from fpl_agent.embeddings.sync_embeddings import sync_embeddings
from fpl_lib.clients.neon import NeonClient
from fpl_lib.clients.s3 import S3Client


def _sample_players() -> list[dict]:
    """Return a list of sample curated player dicts."""
    return [
        {
            "player_id": 1,
            "web_name": "Salah",
            "team_name": "Liverpool",
            "position": "MID",
            "price": 13.0,
            "total_points": 180,
            "form": 8.2,
            "goals_scored": 15,
            "assists": 10,
            "minutes": 2400,
            "llm_summary": "Top scorer this season.",
            "form_trend": "improving",
            "injury_risk": 2,
            "fdr_next_3": 2.5,
        },
        {
            "player_id": 2,
            "web_name": "Haaland",
            "team_name": "Man City",
            "position": "FWD",
            "price": 14.5,
            "total_points": 160,
            "form": 7.0,
            "goals_scored": 18,
            "assists": 3,
            "minutes": 2200,
            "llm_summary": "Clinical finisher but rotation risk.",
            "form_trend": "stable",
            "injury_risk": 3,
            "fdr_next_3": 3.0,
        },
        {
            "player_id": 3,
            "web_name": "Saka",
            "team_name": "Arsenal",
            "position": "MID",
            "price": 10.0,
            "total_points": 140,
            "form": 6.5,
            "goals_scored": 10,
            "assists": 8,
            "minutes": 2100,
            "llm_summary": None,
            "form_trend": None,
            "injury_risk": None,
            "fdr_next_3": None,
        },
    ]


@pytest.fixture
def mock_s3_client() -> MagicMock:
    client = MagicMock(spec=S3Client)
    table = pa.Table.from_pylist(_sample_players())
    client.read_parquet.return_value = table
    return client


@pytest.fixture
def mock_neon_client() -> AsyncMock:
    client = AsyncMock(spec=NeonClient)
    client.execute.return_value = "INSERT 0 1"
    return client


@pytest.fixture
def mock_embedder() -> MagicMock:
    emb = MagicMock(spec=PlayerEmbedder)
    emb.build_profile_text.side_effect = lambda p: f"Profile for {p.get('web_name', 'Unknown')}"
    emb.embed_batch.return_value = [[0.1] * 384, [0.2] * 384, [0.3] * 384]
    return emb


# --- sync_embeddings tests ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sync_reads_curated_data(
    mock_s3_client: MagicMock,
    mock_neon_client: AsyncMock,
    mock_embedder: MagicMock,
) -> None:
    await sync_embeddings(
        s3_client=mock_s3_client,
        neon_client=mock_neon_client,
        embedder=mock_embedder,
        bucket="test-bucket",
        season="2025-26",
        gameweek=10,
    )
    mock_s3_client.read_parquet.assert_called_once_with(
        "test-bucket",
        "curated/player_dashboard/season=2025-26/gameweek=10/player_dashboard.parquet",
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sync_upserts_correct_count(
    mock_s3_client: MagicMock,
    mock_neon_client: AsyncMock,
    mock_embedder: MagicMock,
) -> None:
    await sync_embeddings(
        s3_client=mock_s3_client,
        neon_client=mock_neon_client,
        embedder=mock_embedder,
        bucket="test-bucket",
        season="2025-26",
        gameweek=10,
    )
    assert mock_neon_client.execute.call_count == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sync_returns_correct_response(
    mock_s3_client: MagicMock,
    mock_neon_client: AsyncMock,
    mock_embedder: MagicMock,
) -> None:
    result = await sync_embeddings(
        s3_client=mock_s3_client,
        neon_client=mock_neon_client,
        embedder=mock_embedder,
        bucket="test-bucket",
        season="2025-26",
        gameweek=10,
    )
    assert result["players_synced"] == 3
    assert result["embedding_dim"] == 384
    assert isinstance(result["duration_seconds"], float)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sync_handles_empty_dataframe(
    mock_neon_client: AsyncMock,
    mock_embedder: MagicMock,
) -> None:
    empty_s3 = MagicMock(spec=S3Client)
    empty_s3.read_parquet.return_value = pa.Table.from_pylist([])

    result = await sync_embeddings(
        s3_client=empty_s3,
        neon_client=mock_neon_client,
        embedder=mock_embedder,
        bucket="test-bucket",
        season="2025-26",
        gameweek=1,
    )
    assert result["players_synced"] == 0
    mock_neon_client.execute.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sync_handles_missing_enrichments(
    mock_neon_client: AsyncMock,
    mock_embedder: MagicMock,
) -> None:
    """Player with no enrichment fields should sync without error."""
    sparse_player = [{"player_id": 99, "web_name": "Unknown", "position": "DEF"}]
    sparse_s3 = MagicMock(spec=S3Client)
    sparse_s3.read_parquet.return_value = pa.Table.from_pylist(sparse_player)
    mock_embedder.embed_batch.return_value = [[0.0] * 384]

    result = await sync_embeddings(
        s3_client=sparse_s3,
        neon_client=mock_neon_client,
        embedder=mock_embedder,
        bucket="test-bucket",
        season="2025-26",
        gameweek=5,
    )
    assert result["players_synced"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sync_passes_correct_s3_path(
    mock_s3_client: MagicMock,
    mock_neon_client: AsyncMock,
    mock_embedder: MagicMock,
) -> None:
    """Gameweek should be zero-padded in the S3 key."""
    await sync_embeddings(
        s3_client=mock_s3_client,
        neon_client=mock_neon_client,
        embedder=mock_embedder,
        bucket="my-bucket",
        season="2024-25",
        gameweek=3,
    )
    call_args = mock_s3_client.read_parquet.call_args
    key = call_args[0][1]
    assert "gameweek=03" in key
