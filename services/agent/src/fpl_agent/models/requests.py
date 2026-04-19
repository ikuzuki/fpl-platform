"""Request models for the agent HTTP API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    """Payload for ``POST /chat`` and ``POST /chat/sync``.

    ``session_id`` is optional — the rate limiter falls back to the client
    IP when it's absent. ``extra='forbid'`` so typos in the body surface
    as 422 instead of silently being ignored.
    """

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=500)
    session_id: str | None = Field(default=None, max_length=128)
