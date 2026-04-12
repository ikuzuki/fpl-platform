"""Custom exceptions for data collectors."""


class TeamNotFoundError(Exception):
    """Raised when an FPL team ID returns 404."""

    def __init__(self, team_id: int) -> None:
        self.team_id = team_id
        super().__init__(f"FPL team {team_id} not found (404)")


class FPLAccessError(Exception):
    """Raised when the FPL API returns 403 after retry."""

    def __init__(self, team_id: int, detail: str = "") -> None:
        self.team_id = team_id
        msg = f"FPL access denied for team {team_id} after retry"
        if detail:
            msg += f": {detail}"
        super().__init__(msg)
