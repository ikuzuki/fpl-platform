"""FastAPI wrapper for the FPL recommendation agent."""

from fastapi import FastAPI

app = FastAPI(title="FPL Agent API", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
