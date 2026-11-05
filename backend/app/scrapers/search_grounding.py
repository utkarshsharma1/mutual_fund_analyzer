"""Live Web Search & Gemini Google Search Grounding for qualitative mutual fund intelligence.

Uses the Gemini Interactions API (`client.interactions.create` with `tools=[{"type": "google_search"}]`)
to retrieve real-time fund manager commentary, AMC news, subscription restrictions (e.g., lumpsum caps),
and factsheet highlights with source URL citations. Also includes a direct HTML web-search fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from google import genai
import httpx

from app.config import settings
from app.scrapers.mfapi_live import InMemoryTTLCache

_grounding_cache = InMemoryTTLCache(ttl_seconds=settings.cache_ttl_seconds)


@dataclass
class GroundedFundIntel:
    """Qualitative intelligence and citations gathered from live web search."""

    scheme_name: str
    summary_markdown: str
    search_queries: list[str] = field(default_factory=list)
    citations: list[dict[str, str]] = field(default_factory=list)


async def fetch_grounded_fund_intel(
    scheme_name: str,
    amc_name: str = "",
    specific_question: str = "",
) -> GroundedFundIntel:
    """Fetch real-time qualitative intelligence on an Indian mutual fund using Gemini Google Search Grounding."""
    cache_key = f"grounding:{scheme_name.lower()}:{specific_question.lower()[:60]}"
    cached = _grounding_cache.get(cache_key)
    if cached is not None:
        return cached

    if settings.gemini_api_key:
        try:
            client = genai.Client(api_key=settings.gemini_api_key)
            prompt = (
                f"Search the web for the latest factsheet, fund manager tenure, investment strategy, "
                f"portfolio positioning, expense ratio, AUM, and any recent news or subscription limits "
                f"(such as lumpsum restrictions or manager changes) for the Indian mutual fund: "
                f"'{scheme_name}' ({amc_name}). "
            )
            if specific_question:
                prompt += f"\nAlso specifically address: {specific_question}\n"
            prompt += (
                "Provide a concise, factual summary bulleted under: "
                "1) Strategy & Positioning, 2) Fund Manager & AMC Track Record, "
                "3) Recent Developments / Red Flags."
            )

            interaction = client.interactions.create(
                model=settings.gemini_model,
                input=prompt,
                tools=[{"type": "google_search"}],
            )

            queries: list[str] = []
            citations: list[dict[str, str]] = []
            seen_urls: set[str] = set()

            for step in getattr(interaction, "steps", []) or []:
                step_type = getattr(step, "type", None)
                if step_type == "google_search_call":
                    args = getattr(step, "arguments", {}) or {}
                    if isinstance(args, dict):
                        queries.extend(args.get("queries", []) or [])
                elif step_type == "model_output":
                    for block in getattr(step, "content", []) or []:
                        for ann in getattr(block, "annotations", []) or []:
                            url = getattr(ann, "url", None)
                            title = getattr(ann, "title", None) or url
                            if url and url not in seen_urls:
                                seen_urls.add(url)
                                citations.append({"title": str(title), "url": str(url)})

            intel = GroundedFundIntel(
                scheme_name=scheme_name,
                summary_markdown=interaction.output_text or "No additional grounded notes found.",
                search_queries=queries,
                citations=citations,
            )
            _grounding_cache.set(cache_key, intel)
            return intel
        except Exception:
            pass

    # Fallback: Direct live web search scrape via DuckDuckGo HTML if GEMINI_API_KEY is not configured or fails
    intel = await _fallback_web_search_scrape(scheme_name, amc_name)
    _grounding_cache.set(cache_key, intel)
    return intel


async def _fallback_web_search_scrape(scheme_name: str, amc_name: str = "") -> GroundedFundIntel:
    """Scrape live web search snippets for the mutual fund when running without Gemini Search Grounding."""
    q = f"{scheme_name} {amc_name} mutual fund review expense ratio manager portfolio"
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(q)}"
    snippets: list[str] = []
    citations: list[dict[str, str]] = []

    try:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout_seconds,
            headers={"User-Agent": settings.user_agent},
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for res in soup.select(".result")[:5]:
                    title_el = res.select_one(".result__a")
                    snippet_el = res.select_one(".result__snippet")
                    if title_el and snippet_el:
                        title = title_el.get_text(" ", strip=True)
                        href = str(title_el.get("href", ""))
                        text = snippet_el.get_text(" ", strip=True)
                        snippets.append(f"- **{title}**: {text}")
                        if href:
                            citations.append({"title": title, "url": href})
    except Exception:
        pass

    summary = (
        "\n".join(snippets)
        if snippets
        else f"Live quantitative NAV and portal fundamentals scraped for {scheme_name}."
    )
    return GroundedFundIntel(
        scheme_name=scheme_name,
        summary_markdown=summary,
        search_queries=[q],
        citations=citations,
    )

