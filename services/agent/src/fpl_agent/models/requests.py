"""Request models for the agent HTTP API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from fpl_agent.models.responses import UserSquad


class ChatRequest(BaseModel):
    """Payload for ``POST /chat`` and ``POST /chat/sync``.

    Session identity is carried by the ``X-Session-Id`` header (canonical
    since PR #93's Langfuse wiring) — there is no body field for it. The
    rate limiter falls back to client IP when the header is absent.

    ``squad`` is the enriched user squad fetched out-of-band by the dashboard
    via ``GET /team``. When present, the agent seeds it into ``user_squad``
    state instead of calling ``fetch_user_squad`` itself; the planner prompt
    gates that tool out and the executor short-circuits as a belt-and-braces.

    ``extra='forbid'`` so typos and stale field names (e.g. ``team_id``,
    ``session_id``) surface as 422 instead of being silently dropped.
    """

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=500)
    squad: UserSquad | None = Field(default=None)
