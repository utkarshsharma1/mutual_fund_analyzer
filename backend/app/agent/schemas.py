"""Pydantic request and response schemas for the Mutual Fund Evaluation Agent API."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class AnalyzeFundRequest(BaseModel):
    """Request payload to evaluate a single mutual fund by name or AMFI scheme code."""

    query: str = Field(..., description="Mutual fund name or AMFI scheme code, e.g., 'Parag Parikh Flexi Cap Direct Growth'")
    scheme_code: int | None = Field(default=None, description="Optional explicit AMFI scheme code")
    include_web_grounding: bool = Field(default=True, description="Whether to run live web search / Gemini grounding")


class CompareFundsRequest(BaseModel):
    """Request payload to compare 2 to 4 mutual funds and compute portfolio overlap."""

    queries: list[str] = Field(
        ...,
        min_length=2,
        max_length=5,
        description="List of 2-5 mutual fund names or scheme codes to compare",
    )


class ChatAgentRequest(BaseModel):
    """Conversational agent query payload."""

    message: str = Field(..., description="User question or instruction about Indian mutual funds")
    previous_interaction_id: str | None = Field(
        default=None,
        description="Optional Gemini Interactions API previous_interaction_id for multi-turn state",
    )


class AgentResponsePayload(BaseModel):
    """Unified response returned by the Mutual Fund Evaluation Agent."""

    query: str
    interaction_id: str | None = None
    markdown_report: str
    primary_fund: dict[str, Any] | None = None
    compared_funds: list[dict[str, Any]] = Field(default_factory=list)
    overlap_analysis: dict[str, Any] | None = None
    execution_steps: list[str] = Field(default_factory=list)
    citations: list[dict[str, str]] = Field(default_factory=list)

