"""API endpoints for live mutual fund search, deep-dive evaluation, peer comparison, and AI chat."""

from __future__ import annotations

import json
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.agent.orchestrator import (
    format_comparison_markdown,
    format_single_fund_markdown,
    run_agent_query,
)
from app.agent.schemas import (
    AgentResponsePayload,
    AnalyzeFundRequest,
    ChatAgentRequest,
    CompareFundsRequest,
)
from app.agent.tools import compare_mutual_funds_live, evaluate_mutual_fund_live
from app.config import settings
from app.scrapers.mfapi_live import search_schemes_live

router = APIRouter(prefix="/api", tags=["Mutual Fund Analyzer"])


@router.get("/health")
async def health_check() -> dict[str, object]:
    """Check service readiness and configuration."""
    return {
        "status": "ok",
        "mode": "stateless_on_demand",
        "gemini_configured": bool(settings.gemini_api_key),
        "gemini_model": settings.gemini_model,
        "risk_free_rate_pct": round(settings.risk_free_rate * 100.0, 2),
    }


@router.get("/search")
async def search_funds(
    q: str = Query(..., min_length=2, description="Mutual fund name or keyword"),
    direct_only: bool = Query(default=True, description="Prefer Direct Plan Growth schemes"),
    limit: int = Query(default=8, ge=1, le=20),
) -> dict[str, object]:
    """Search live AMFI mutual fund schemes by name."""
    results = await search_schemes_live(q, prefer_direct_growth=direct_only, limit=limit)
    return {"query": q, "count": len(results), "results": results}


@router.post("/analyze", response_model=AgentResponsePayload)
async def analyze_fund(req: AnalyzeFundRequest) -> AgentResponsePayload:
    """Evaluate a single Indian mutual fund on demand and return its 100-point scorecard & report."""
    try:
        eval_res = await evaluate_mutual_fund_live(
            fund_query=req.query,
            scheme_code=req.scheme_code,
            include_web_grounding=req.include_web_grounding,
        )
        md = format_single_fund_markdown(eval_res)
        return AgentResponsePayload(
            query=req.query,
            markdown_report=md,
            primary_fund=eval_res,
            compared_funds=[],
            overlap_analysis=None,
            execution_steps=eval_res.get("execution_steps", []),
            citations=eval_res.get("citations", []),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to evaluate mutual fund: {exc}") from exc


@router.post("/compare", response_model=AgentResponsePayload)
async def compare_funds(req: CompareFundsRequest) -> AgentResponsePayload:
    """Compare 2 to 5 mutual funds side-by-side and compute portfolio holdings overlap."""
    try:
        comp_res = await compare_mutual_funds_live(req.queries, include_web_grounding=False)
        compared = comp_res.get("compared_funds", [])
        md = format_comparison_markdown(comp_res)
        return AgentResponsePayload(
            query=" vs ".join(req.queries),
            markdown_report=md,
            primary_fund=compared[0] if compared else None,
            compared_funds=compared,
            overlap_analysis=comp_res.get("overlap_analysis"),
            execution_steps=comp_res.get("execution_steps", []),
            citations=comp_res.get("citations", []),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to compare mutual funds: {exc}") from exc


@router.post("/chat", response_model=AgentResponsePayload)
async def chat_with_agent(req: ChatAgentRequest) -> AgentResponsePayload:
    """Conversational endpoint powered by Gemini Interactions API + live scraping & quant tools."""
    try:
        return await run_agent_query(
            message=req.message,
            previous_interaction_id=req.previous_interaction_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {exc}") from exc


@router.post("/chat/stream")
async def chat_with_agent_stream(req: ChatAgentRequest) -> StreamingResponse:
    """SSE streaming endpoint emitting live step updates and final AgentResponsePayload."""

    async def event_generator() -> AsyncGenerator[str, None]:
        yield f"data: {json.dumps({'type': 'status', 'message': 'Searching AMFI schemes & scraping live fund data...'})}\n\n"
        try:
            payload = await run_agent_query(
                message=req.message,
                previous_interaction_id=req.previous_interaction_id,
            )
            for step in payload.execution_steps:
                yield f"data: {json.dumps({'type': 'step', 'message': step})}\n\n"
            yield f"data: {json.dumps({'type': 'result', 'payload': payload.model_dump()})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

