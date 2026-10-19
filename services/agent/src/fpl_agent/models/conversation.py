"""A remembered question and answer, stored per conversation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from fpl_agent.models.responses import ScoutReport

ANALYSIS_CHARS = 600


class Turn(BaseModel):
    """One remembered question and the agent's answer to it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question: str
    players: list[str]
    analysis: str
    recommendation: str

    @classmethod
    def from_report(cls, question: str, report: ScoutReport) -> Turn:
        names = [p.player_name for p in report.players]
        if report.comparison is not None:
            names += [p.player_name for p in report.comparison.players]
        return cls(
            question=question,
            players=list(dict.fromkeys(names)),
            analysis=report.analysis[:ANALYSIS_CHARS],
            recommendation=report.recommendation,
        )
