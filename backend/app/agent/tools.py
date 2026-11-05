"""Live Tool Registry & Execution Pipeline for the Indian Mutual Fund Evaluation Agent."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any

from app.quant.metrics import compute_fund_quant_report
from app.quant.overlap import compute_portfolio_overlap
from app.quant.scorer import evaluate_fund_scorecard
from app.scrapers.benchmark_live import fetch_benchmark_live
from app.scrapers.fund_web_scraper import (
    ScrapedFundFundamentals,
    scrape_fund_fundamentals_live,
)
from app.scrapers.mfapi_live import fetch_scheme_nav_live, search_schemes_live
from app.scrapers.search_grounding import fetch_grounded_fund_intel


# Gemini Interactions API Function Declarations
EVALUATE_MUTUAL_FUND_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "evaluate_mutual_fund",
    "description": (
        "Evaluates an Indian mutual fund on demand by searching its AMFI scheme code, "
        "fetching live historical NAVs and SEBI TRI benchmark index data, scraping live "
        "fundamentals (TER, AUM, Exit Load, Fund Manager, Top Holdings, Sector Split, Peers), "
        "and computing a 100-Point Composite Score with rolling returns, Sharpe, Sortino, "
        "Jensen's Alpha, Beta, and Downside Capture."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "fund_query": {
                "type": "string",
                "description": "Name of the Indian mutual fund to analyze, e.g. 'Parag Parikh Flexi Cap Fund'",
            },
            "scheme_code": {
                "type": "integer",
                "description": "Optional explicit AMFI scheme code if already known",
            },
        },
        "required": ["fund_query"],
    },
}

COMPARE_MUTUAL_FUNDS_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "compare_mutual_funds_and_overlap",
    "description": (
        "Compares 2 to 4 Indian mutual funds side-by-side (computing each fund's 100-point scorecard, "
        "rolling returns, Sharpe, Sortino, Alpha, Downside Capture, TER, and AUM) and calculates "
        "their pairwise portfolio stock & sector overlap matrix."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "fund_queries": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of 2 to 4 mutual fund names to compare and check portfolio overlap",
            }
        },
        "required": ["fund_queries"],
    },
}

SEARCH_SCHEMES_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "search_indian_mutual_funds",
    "description": "Searches AMFI mutual fund schemes by keyword and returns matching scheme codes and names.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search keyword, e.g., 'HDFC Mid Cap' or 'SBI Contra'",
            }
        },
        "required": ["query"],
    },
}

AGENT_TOOLS: list[dict[str, Any]] = [
    EVALUATE_MUTUAL_FUND_TOOL,
    COMPARE_MUTUAL_FUNDS_TOOL,
    SEARCH_SCHEMES_TOOL,
]


async def evaluate_mutual_fund_live(
    fund_query: str,
    scheme_code: int | None = None,
    include_web_grounding: bool = True,
) -> dict[str, Any]:
    """End-to-end live evaluation pipeline for a single Indian mutual fund."""
    steps: list[str] = []

    # 1. Resolve AMFI scheme code if not explicitly provided
    if scheme_code is None:
        if fund_query.strip().isdigit():
            scheme_code = int(fund_query.strip())
            steps.append(f"Using explicit AMFI scheme code {scheme_code}")
        else:
            matches = await search_schemes_live(fund_query, prefer_direct_growth=True, limit=5)
            if not matches:
                raise ValueError(
                    f"Could not find any Indian mutual fund matching '{fund_query}'. "
                    "Try a more specific AMC or fund name (e.g., 'Parag Parikh Flexi Cap', 'HDFC Mid-Cap')."
                )
            scheme_code = int(matches[0]["scheme_code"])
            steps.append(
                f"Resolved '{fund_query}' -> {matches[0]['scheme_name']} (AMFI Code: {scheme_code})"
            )

    # 2. Fetch live historical NAVs from mfapi.in
    nav_data = await fetch_scheme_nav_live(scheme_code)
    steps.append(
        f"Fetched {nav_data.total_trading_days:,} daily NAV records for {nav_data.scheme_name} "
        f"(Latest NAV: ₹{nav_data.latest_nav} as of {nav_data.latest_nav_date})"
    )

    # 3. In parallel: fetch live Benchmark TRI series, scrape live portal fundamentals/holdings, and run web grounding
    bench_task = asyncio.create_task(
        fetch_benchmark_live(nav_data.scheme_category, nav_data.scheme_name)
    )
    scrape_task = asyncio.create_task(
        scrape_fund_fundamentals_live(
            nav_data.scheme_name,
            scheme_code=nav_data.scheme_code,
            isin_growth=nav_data.isin_growth,
        )
    )
    if include_web_grounding:
        ground_task = asyncio.create_task(
            fetch_grounded_fund_intel(nav_data.scheme_name, nav_data.fund_house)
        )
        benchmark_series, fundamentals, grounded_intel = await asyncio.gather(
            bench_task, scrape_task, ground_task
        )
    else:
        benchmark_series, fundamentals = await asyncio.gather(bench_task, scrape_task)
        grounded_intel = None

    steps.append(f"Loaded benchmark time series: {benchmark_series.benchmark_name}")
    steps.append(
        f"Scraped live fund metadata: TER={fundamentals.expense_ratio_pct}%, "
        f"AUM=₹{fundamentals.aum_crores} Cr, Holdings={len(fundamentals.top_holdings)} stocks"
    )

    # 4. Compute deterministic quantitative report & 100-Point Scorecard in memory
    quant_report = compute_fund_quant_report(
        scheme_code=nav_data.scheme_code,
        scheme_name=nav_data.scheme_name,
        benchmark_name=benchmark_series.benchmark_name,
        fund_nav_df=nav_data.nav_df,
        benchmark_nav_df=benchmark_series.df,
    )
    scorecard = evaluate_fund_scorecard(
        quant=quant_report,
        fundamentals=fundamentals,
        sebi_category=fundamentals.sebi_category or nav_data.scheme_category,
    )
    steps.append(
        f"Computed 100-Point Composite Score: {scorecard.total_score}/100 "
        f"({scorecard.letter_grade} — {scorecard.verdict})"
    )

    citations: list[dict[str, str]] = [
        {"title": f"AMFI / MFAPI NAV History ({nav_data.scheme_code})", "url": f"https://api.mfapi.in/mf/{nav_data.scheme_code}"}
    ]
    for u in fundamentals.source_urls:
        citations.append({"title": "Scraped Portal Fundamentals & Holdings", "url": u})
    if grounded_intel and grounded_intel.citations:
        citations.extend(grounded_intel.citations)

    return {
        "scheme_code": nav_data.scheme_code,
        "scheme_name": nav_data.scheme_name,
        "fund_house": nav_data.fund_house,
        "sebi_category": scorecard.sebi_category,
        "isin_growth": nav_data.isin_growth,
        "inception_date": nav_data.inception_date,
        "latest_nav": nav_data.latest_nav,
        "latest_nav_date": nav_data.latest_nav_date,
        "scorecard": scorecard.to_dict(),
        "quant_report": quant_report.to_dict(),
        "fundamentals": asdict(fundamentals),
        "qualitative_intel": asdict(grounded_intel) if grounded_intel else None,
        "execution_steps": steps,
        "citations": citations,
    }


async def compare_mutual_funds_live(
    fund_queries: list[str],
    include_web_grounding: bool = False,
) -> dict[str, Any]:
    """Evaluate 2 to 5 mutual funds in parallel and compute their portfolio overlap matrix."""
    steps: list[str] = [f"Comparing {len(fund_queries)} mutual funds in parallel..."]

    tasks = [
        evaluate_mutual_fund_live(q, include_web_grounding=include_web_grounding)
        for q in fund_queries[:5]
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    valid_evaluations: list[dict[str, Any]] = []
    scraped_list: list[ScrapedFundFundamentals] = []
    citations: list[dict[str, str]] = []

    for q, res in zip(fund_queries, results):
        if isinstance(res, Exception):
            steps.append(f"Warning: Could not evaluate '{q}': {res}")
            continue
        valid_evaluations.append(res)
        steps.extend(res.get("execution_steps", []))
        citations.extend(res.get("citations", []))
        f_dict = res["fundamentals"]
        from app.scrapers.fund_web_scraper import HoldingItem

        scraped_list.append(
            ScrapedFundFundamentals(
                scheme_name=res["scheme_name"],
                amc_name=res["fund_house"],
                sebi_category=res["sebi_category"],
                expense_ratio_pct=f_dict.get("expense_ratio_pct"),
                aum_crores=f_dict.get("aum_crores"),
                top_holdings=[HoldingItem(**h) for h in f_dict.get("top_holdings", [])],
                sector_allocation=f_dict.get("sector_allocation", {}),
            )
        )

    if not valid_evaluations:
        raise ValueError("Could not resolve any of the requested mutual funds.")

    # Rank compared funds by total_score descending
    valid_evaluations.sort(key=lambda x: x["scorecard"]["total_score"], reverse=True)

    overlap_result = None
    if len(scraped_list) >= 2:
        overlap_result = compute_portfolio_overlap(scraped_list)
        steps.append("Computed pairwise stock & sector portfolio overlap matrix.")

    return {
        "compared_funds": valid_evaluations,
        "overlap_analysis": overlap_result,
        "execution_steps": steps,
        "citations": citations,
    }

