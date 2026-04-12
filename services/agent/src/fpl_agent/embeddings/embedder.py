"""Embed player profiles using sentence-transformers all-MiniLM-L6-v2.

Runs locally on CPU — no API key needed. ~500 players takes <5 seconds.
"""

from __future__ import annotations

import logging
from typing import Any

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class PlayerEmbedder:
    """Generates 384-dim embeddings for player profiles."""

    MODEL_NAME = "all-MiniLM-L6-v2"
    EMBEDDING_DIM = 384

    def __init__(self) -> None:
        self._model: SentenceTransformer | None = None

    def _get_model(self) -> SentenceTransformer:
        """Lazy-load the sentence-transformer model on first use."""
        if self._model is None:
            logger.info("Loading sentence-transformer model: %s", self.MODEL_NAME)
            self._model = SentenceTransformer(self.MODEL_NAME)
        return self._model

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text string into a 384-dim vector."""
        embedding: list[float] = self._get_model().encode(text).tolist()
        return embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts into 384-dim vectors."""
        if not texts:
            return []
        embeddings: list[list[float]] = self._get_model().encode(texts).tolist()
        return embeddings

    @staticmethod
    def build_profile_text(player: dict[str, Any]) -> str:
        """Combine player stats and enrichments into a single text for embedding.

        Args:
            player: Dict of player data from the curated player_dashboard layer.

        Returns:
            Natural language profile string suitable for embedding.
        """
        web_name = player.get("web_name", "Unknown")
        position = player.get("position", "N/A")
        team_name = player.get("team_name", "N/A")
        price = player.get("price", "N/A")
        form = player.get("form", "N/A")
        total_points = player.get("total_points", "N/A")
        goals_scored = player.get("goals_scored", "N/A")
        assists = player.get("assists", "N/A")
        llm_summary = player.get("llm_summary") or "No summary available"
        form_trend = player.get("form_trend") or "N/A"
        injury_risk = player.get("injury_risk") if player.get("injury_risk") is not None else "N/A"
        fdr_next_3 = player.get("fdr_next_3") if player.get("fdr_next_3") is not None else "N/A"

        return (
            f"{web_name} ({position}, {team_name}). Price: £{price}m. Form: {form}.\n"
            f"Points: {total_points}. Goals: {goals_scored}, Assists: {assists}.\n"
            f"Summary: {llm_summary}\n"
            f"Form trend: {form_trend}. Injury risk: {injury_risk}/10.\n"
            f"Fixture difficulty (next 3): {fdr_next_3}/5."
        )
