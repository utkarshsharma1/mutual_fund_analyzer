"""FastAPI Entrypoint for the Stateless Indian Mutual Fund Evaluation Agent."""

from __future__ import annotations

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from app.api.routes import router as api_router

app = FastAPI(
    title="Indian Mutual Fund Evaluation Agent",
    description=(
        "Stateless, on-demand AI Analyst for Indian Mutual Funds. "
        "Combines live AMFI NAV & TRI benchmark time-series, live web scraping of TER/AUM/Holdings, "
        "Gemini Google Search Grounding, and an in-memory 100-Point Quantitative Scorer."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

STATIC_INDEX = Path(__file__).parent / "static" / "index.html"


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_dashboard():
    """Serve the interactive Analyst Chat + 100-Point Live Scorecard UI."""
    if STATIC_INDEX.exists():
        return FileResponse(STATIC_INDEX)
    return HTMLResponse("<h1>Indian Mutual Fund Evaluation Agent API is running. Visit /docs</h1>")

