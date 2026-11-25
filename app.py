"""HTTP entry point for the Waypoint travel-planning application."""

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

from backend import run_travel_agent


app = FastAPI(title="Waypoint Travel Planner")
STATIC_DIR = Path(__file__).parent / "static"
INDEX_FILE = STATIC_DIR / "index.html"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class TravelRequest(BaseModel):
    """Validated request body used by the travel-planning endpoint.

    The question is trimmed before field constraints are applied, then limited
    to 3–2,000 characters to reject blank or excessively large requests.
    """

    question: str = Field(min_length=3, max_length=2000)

    @field_validator("question", mode="before")
    @classmethod
    def trim_question(cls, value: Any) -> Any:
        """Strip surrounding whitespace before validating string questions.

        Non-string values are left unchanged so Pydantic can report its normal
        type-validation error rather than raising from ``strip``.
        """
        return value.strip() if isinstance(value, str) else value


@app.get("/", include_in_schema=False)
async def home() -> FileResponse:
    """Serve the single-page web application from the static directory."""
    return FileResponse(INDEX_FILE)


@app.post("/api/ask")
async def ask_travel_agent(request: TravelRequest) -> dict:
    """Run the synchronous travel graph without blocking the async event loop.

    Args:
        request: A validated user question.

    Returns:
        The agent's answer, research details, thread identifier, and call count.
    """
    return await run_in_threadpool(run_travel_agent, request.question)
