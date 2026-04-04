"""Player domain models."""

from pydantic import BaseModel, Field


class Player(BaseModel):
    """FPL player data from the Bootstrap API."""

    id: int
    web_name: str
    team: int
    team_name: str = ""
    element_type: int = Field(description="1=GKP, 2=DEF, 3=MID, 4=FWD")
    total_points: int = 0
    minutes: int = 0
    goals_scored: int = 0
    assists: int = 0
    clean_sheets: int = 0
    goals_conceded: int = 0
    own_goals: int = 0
    penalties_saved: int = 0
    penalties_missed: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    saves: int = 0
    bonus: int = 0
    bps: int = 0
    now_cost: int = Field(default=0, description="Current price in tenths (e.g. 100 = £10.0m)")
    selected_by_percent: str = "0.0"
    form: str = "0.0"
    points_per_game: str = "0.0"


class PlayerSummary(BaseModel):
    """LLM-generated player summary with metadata."""

    player_id: int
    summary: str
    form_trend: str = Field(description="improving, stable, declining")
    confidence: float = Field(ge=0.0, le=1.0, description="Model confidence in assessment")
    prompt_version: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
