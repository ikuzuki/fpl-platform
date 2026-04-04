"""Load versioned prompt templates from the prompts directory."""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(enricher_name: str, version: str = "v1") -> str:
    """Load a prompt template from the versioned prompts directory.

    Args:
        enricher_name: Name of the enricher (e.g. 'player_summary').
        version: Prompt version directory (default 'v1').

    Returns:
        The prompt template string.

    Raises:
        FileNotFoundError: If the prompt file does not exist.
    """
    path = _PROMPTS_DIR / version / f"{enricher_name}.txt"
    return path.read_text(encoding="utf-8")
