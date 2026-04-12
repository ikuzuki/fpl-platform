"""Tests for PlayerEmbedder."""

import pytest

from fpl_agent.embeddings.embedder import PlayerEmbedder


@pytest.fixture(scope="module")
def embedder() -> PlayerEmbedder:
    """Load the sentence-transformer model once for all tests in this module."""
    emb = PlayerEmbedder()
    # Force model load so timing is in fixture, not first test.
    emb._get_model()
    return emb


def _complete_player() -> dict:
    """Return a player dict with all fields populated."""
    return {
        "player_id": 1,
        "web_name": "Salah",
        "position": "MID",
        "team_name": "Liverpool",
        "price": 13.0,
        "form": 8.2,
        "total_points": 180,
        "goals_scored": 15,
        "assists": 10,
        "minutes": 2400,
        "llm_summary": "Consistent performer with excellent goal output.",
        "form_trend": "improving",
        "injury_risk": 2,
        "fdr_next_3": 2.5,
    }


# --- embed_text tests ---


@pytest.mark.unit
def test_embed_text_returns_384_dims(embedder: PlayerEmbedder) -> None:
    result = embedder.embed_text("Mohamed Salah is a top FPL midfielder.")
    assert len(result) == 384


@pytest.mark.unit
def test_embed_text_returns_floats(embedder: PlayerEmbedder) -> None:
    result = embedder.embed_text("Test input text.")
    assert all(isinstance(x, float) for x in result)


# --- embed_batch tests ---


@pytest.mark.unit
def test_embed_batch_returns_correct_count(embedder: PlayerEmbedder) -> None:
    texts = ["Player one", "Player two", "Player three"]
    result = embedder.embed_batch(texts)
    assert len(result) == 3
    assert all(len(v) == 384 for v in result)


@pytest.mark.unit
def test_embed_batch_empty_list(embedder: PlayerEmbedder) -> None:
    result = embedder.embed_batch([])
    assert result == []


# --- build_profile_text tests ---


@pytest.mark.unit
def test_build_profile_text_includes_all_fields() -> None:
    player = _complete_player()
    text = PlayerEmbedder.build_profile_text(player)

    assert "Salah" in text
    assert "MID" in text
    assert "Liverpool" in text
    assert "13.0" in text
    assert "8.2" in text
    assert "180" in text
    assert "15" in text
    assert "10" in text
    assert "Consistent performer" in text
    assert "improving" in text
    assert "2" in text
    assert "2.5" in text


@pytest.mark.unit
def test_build_profile_text_handles_missing_fields() -> None:
    player = {"web_name": "Salah", "position": "MID"}
    text = PlayerEmbedder.build_profile_text(player)

    assert "Salah" in text
    assert "MID" in text
    assert "N/A" in text
    assert "No summary available" in text


@pytest.mark.unit
def test_build_profile_text_handles_none_values() -> None:
    player = _complete_player()
    player["llm_summary"] = None
    player["form_trend"] = None
    player["injury_risk"] = None
    player["fdr_next_3"] = None

    text = PlayerEmbedder.build_profile_text(player)

    assert "Salah" in text
    assert "No summary available" in text
    assert "N/A" in text
