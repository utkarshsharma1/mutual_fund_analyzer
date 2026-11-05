"""Gemini Agent Orchestrator (`google-genai` Interactions API) + Deterministic Report Synthesizer."""

from __future__ import annotations

import json
import re
from typing import Any

from google import genai

from app.agent.prompts import SYSTEM_INSTRUCTION
from app.agent.schemas import AgentResponsePayload
from app.agent.tools import (
    AGENT_TOOLS,
    compare_mutual_funds_live,
    evaluate_mutual_fund_live,
)
from app.config import settings
from app.scrapers.mfapi_live import search_schemes_live


def _compact_fund_payload_for_llm(eval_data: dict[str, Any]) -> dict[str, Any]:
    """Strip bulky time-series chart arrays before sending tool results to the LLM context."""
    q = dict(eval_data.get("quant_report", {}))
    q.pop("chart_rolling_3y", None)
    q.pop("chart_drawdown", None)
    q.pop("chart_nav_rebased", None)

    f = dict(eval_data.get("fundamentals", {}))
    if f.get("top_holdings"):
        f["top_holdings"] = f["top_holdings"][:10]

    return {
        "scheme_code": eval_data.get("scheme_code"),
        "scheme_name": eval_data.get("scheme_name"),
        "fund_house": eval_data.get("fund_house"),
        "sebi_category": eval_data.get("sebi_category"),
        "latest_nav": eval_data.get("latest_nav"),
        "latest_nav_date": eval_data.get("latest_nav_date"),
        "scorecard": eval_data.get("scorecard"),
        "quant_metrics": q,
        "fundamentals": f,
        "qualitative_intel": eval_data.get("qualitative_intel"),
    }


def format_single_fund_markdown(eval_data: dict[str, Any]) -> str:
    """Generate a structured, institutional-grade Markdown analysis & suggestion from live evaluation data."""
    sc = eval_data["scorecard"]
    qr = eval_data["quant_report"]
    rm = qr["risk_metrics"]
    fn = eval_data["fundamentals"]
    intel = eval_data.get("qualitative_intel")

    ter_str = f"{fn['expense_ratio_pct']:.2f}%" if fn.get("expense_ratio_pct") is not None else "N/A"
    aum_str = f"₹{fn['aum_crores']:,.0f} Cr" if fn.get("aum_crores") is not None else "N/A"
    mgr_str = fn.get("fund_manager") or "AMC Equity Team"
    if fn.get("manager_tenure_years"):
        mgr_str += f" ({fn['manager_tenure_years']:.1f} yrs)"

    lines: list[str] = [
        f"## {eval_data['scheme_name']}",
        f"**Category:** {eval_data['sebi_category']} | **Benchmark:** {qr['benchmark_name']} | "
        f"**Latest NAV:** ₹{eval_data['latest_nav']} ({eval_data['latest_nav_date']})",
        "",
        f"### Final Score: **{sc['total_score']} / 100** (Grade **{sc['letter_grade']}** — `{sc['verdict']}`)",
        f"> {sc['executive_summary']}",
        "",
        "### 1. 100-Point Scorecard Breakdown",
        "| Evaluation Pillar | Score | Rating | Key Evidence |",
        "| :--- | :---: | :---: | :--- |",
    ]
    for p in sc["pillars"]:
        lines.append(
            f"| **{p['name']}** | **{p['score']} / {p['max_score']:.0f}** | `{p['rating_label']}` | {p['rationale']} |"
        )

    lines.extend(
        [
            "",
            "### 2. Rolling vs Trailing Return Analysis",
            "| Horizon | Fund Trailing CAGR | Benchmark CAGR | Active Alpha Spread | Rolling Median CAGR | Rolling Outperformance Consistency |",
            "| :--- | :---: | :---: | :---: | :---: | :---: |",
        ]
    )
    for h in ("1Y", "3Y", "5Y"):
        tr = qr["trailing_returns_cagr_pct"].get(h, {})
        rl = qr["rolling_returns"].get(h)
        f_cagr = f"{tr['fund_cagr_pct']:.2f}%" if tr.get("fund_cagr_pct") is not None else "—"
        b_cagr = f"{tr['benchmark_cagr_pct']:.2f}%" if tr.get("benchmark_cagr_pct") is not None else "—"
        ex_cagr = f"{tr['excess_cagr_pct']:+.2f}%" if tr.get("excess_cagr_pct") is not None else "—"
        r_med = f"{rl['fund_median_cagr_pct']:.2f}% (vs {rl['benchmark_median_cagr_pct']:.2f}%)" if rl else "—"
        r_cons = f"**{rl['outperformance_consistency_pct']:.1f}%** of windows" if rl else "—"
        lines.append(f"| **{h}** | {f_cagr} | {b_cagr} | {ex_cagr} | {r_med} | {r_cons} |")

    lines.extend(
        [
            "",
            "### 3. Risk, Alpha & Capture Ratios & Fundamentals",
            f"- **Jensen's Alpha (Annualized):** `{rm['jensen_alpha_pct']:+.2f}%` | **Beta:** `{rm['beta']:.2f}` | **R-Squared:** `{rm['r_squared']:.2f}`",
            f"- **Sharpe Ratio:** `{rm['sharpe_ratio']:.2f}` (Benchmark: `{rm['benchmark_sharpe_ratio']:.2f}`) | **Sortino Ratio:** `{rm['sortino_ratio']:.2f}` (Benchmark: `{rm['benchmark_sortino_ratio']:.2f}`)",
            f"- **Market Capture:** Upside Capture `{rm['upside_capture_ratio']:.1f}%` | Downside Capture `{rm['downside_capture_ratio']:.1f}%` | Max Drawdown `{rm['max_drawdown_pct']:.2f}%`",
            f"- **Scraped Fundamentals:** Expense Ratio (TER): **{ter_str}** | AUM: **{aum_str}** | Fund Manager: **{mgr_str}** | Exit Load: *{fn.get('exit_load') or 'Standard'}*",
            "",
            "### 4. Detailed Investment Suggestion",
            "#### Why Consider This Fund (Key Strengths)",
        ]
    )
    for s in sc["strengths"]:
        lines.append(f"- ✅ {s}")

    lines.append("\n#### Key Risks & Watchouts")
    for r in sc["risks_and_red_flags"]:
        lines.append(f"- ⚠️ {r}")

    suit = sc["investor_suitability"]
    lines.extend(
        [
            "",
            "#### Portfolio Fit & Deployment Advice",
            f"- **Recommended Horizon:** {suit['recommended_horizon']}",
            f"- **Deployment Strategy:** {suit['investment_mode']}",
            f"- **Ideal Investor Risk Profile:** {suit['risk_profile']}",
            f"- **Suggested Portfolio Role:** {suit['portfolio_role']}",
        ]
    )

    if intel and intel.get("summary_markdown"):
        lines.extend(
            [
                "",
                "### 5. Live Web Search & Qualitative Context",
                intel["summary_markdown"],
            ]
        )

    lines.extend(
        [
            "",
            "---",
            "*Disclaimer: Mutual Fund investments are subject to market risks, read all scheme-related documents carefully. Quantitative scores and suggestions are computed deterministically from historical AMFI NAVs and public disclosures for educational and research purposes.*",
        ]
    )
    return "\n".join(lines)


def format_comparison_markdown(comp_data: dict[str, Any]) -> str:
    """Generate a structured Markdown comparison & portfolio overlap report."""
    funds = comp_data.get("compared_funds", [])
    overlap = comp_data.get("overlap_analysis")

    lines: list[str] = [
        "## Multi-Fund Comparison & Portfolio Overlap Analysis",
        "",
        "### 1. Head-to-Head Scorecard & Quantitative Ranking",
        "| Rank | Mutual Fund | Score (100) | Verdict | 3Y Rolling Median | 3Y Consistency | 3Y Alpha | Sortino | Downside Capture | TER | AUM |",
        "| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for idx, f in enumerate(funds, start=1):
        sc = f["scorecard"]
        qr = f["quant_report"]
        rm = qr["risk_metrics"]
        fn = f["fundamentals"]
        r3 = qr["rolling_returns"].get("3Y") or qr["rolling_returns"].get("1Y")
        r3_med = f"{r3['fund_median_cagr_pct']:.2f}%" if r3 else "—"
        r3_con = f"{r3['outperformance_consistency_pct']:.1f}%" if r3 else "—"
        ter = f"{fn['expense_ratio_pct']:.2f}%" if fn.get("expense_ratio_pct") is not None else "—"
        aum = f"₹{fn['aum_crores']:,.0f} Cr" if fn.get("aum_crores") is not None else "—"
        lines.append(
            f"| **#{idx}** | **{f['scheme_name']}** | **{sc['total_score']}** (`{sc['letter_grade']}`) | `{sc['verdict']}` | "
            f"{r3_med} | {r3_con} | `{rm['jensen_alpha_pct']:+.2f}%` | {rm['sortino_ratio']:.2f} | "
            f"{rm['downside_capture_ratio']:.1f}% | {ter} | {aum} |"
        )

    if overlap and overlap.get("pairwise_overlap"):
        lines.extend(
            [
                "",
                "### 2. Pairwise Portfolio Holdings Overlap",
                "| Fund A | Fund B | Weight Overlap | Common Stocks | Diversification Diagnosis |",
                "| :--- | :--- | :---: | :---: | :--- |",
            ]
        )
        for pair in overlap["pairwise_overlap"]:
            lines.append(
                f"| {pair['fund_a']} | {pair['fund_b']} | **{pair['weight_overlap_pct']:.1f}%** | "
                f"{pair['common_stocks_count']} | {pair['diagnosis']} |"
            )

    if funds:
        winner = funds[0]
        lines.extend(
            [
                "",
                "### 3. Analyst Recommendation",
                f"- **Top Ranked Pick:** **{winner['scheme_name']}** leads with a score of **{winner['scorecard']['total_score']}/100** "
                f"(`{winner['scorecard']['verdict']}`), backed by `{winner['quant_report']['risk_metrics']['jensen_alpha_pct']:+.2f}%` annualized alpha "
                f"and `{winner['quant_report']['risk_metrics']['downside_capture_ratio']:.1f}%` downside capture.",
            ]
        )

    lines.extend(
        [
            "",
            "---",
            "*Disclaimer: Mutual Fund investments are subject to market risks. Past performance may or may not be sustained in the future.*",
        ]
    )
    return "\n".join(lines)


def _extract_fund_queries_from_message(message: str) -> tuple[str, list[str]]:
    """Heuristic parser to detect single-fund analysis vs multi-fund comparison from natural language."""
    cleaned = message.strip()
    # Check for comparison patterns ("compare X and Y", "X vs Y", "overlap between X and Y")
    if re.search(r"\b(compare|vs\.?|versus|overlap|between)\b", cleaned, re.IGNORECASE):
        stripped = re.sub(
            r"^(please\s+)?(can you\s+)?(compare|check overlap between|analyze overlap of|evaluate)\s+",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        parts = re.split(r"\s+(?:vs\.?|versus|and|with|,)\s+", stripped, flags=re.IGNORECASE)
        parts = [p.strip(" ?.!\"'") for p in parts if len(p.strip(" ?.!\"'")) >= 3]
        if len(parts) >= 2:
            return "compare", parts[:4]

    # Single fund extraction
    single = re.sub(
        r"^(please\s+)?(can you\s+)?(analyze|evaluate|review|score|check|tell me about|should i invest in|how is)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip(" ?.!\"'")
    return "single", [single or cleaned]


async def run_agent_query(
    message: str,
    previous_interaction_id: str | None = None,
) -> AgentResponsePayload:
    """Execute a conversational query using Gemini Interactions API with live scraping & quant tools.

    Automatically falls back to direct deterministic pipeline execution if GEMINI_API_KEY is not set.
    """
    primary_fund: dict[str, Any] | None = None
    compared_funds: list[dict[str, Any]] = []
    overlap_analysis: dict[str, Any] | None = None
    execution_steps: list[str] = []
    citations: list[dict[str, str]] = []

    if settings.gemini_api_key:
        try:
            client = genai.Client(api_key=settings.gemini_api_key)
            create_kwargs: dict[str, Any] = {
                "model": settings.gemini_model,
                "system_instruction": SYSTEM_INSTRUCTION,
                "tools": AGENT_TOOLS + [{"type": "google_search"}],
                "input": message,
            }
            if previous_interaction_id:
                create_kwargs["previous_interaction_id"] = previous_interaction_id

            interaction = client.interactions.create(**create_kwargs)

            # Handle up to 3 rounds of tool calling
            for _ in range(3):
                fn_calls = [
                    step
                    for step in (getattr(interaction, "steps", []) or [])
                    if getattr(step, "type", None) == "function_call"
                ]
                if not fn_calls:
                    break

                fn_results_input: list[dict[str, Any]] = []
                for fc in fn_calls:
                    fn_name = getattr(fc, "name", "")
                    fn_id = getattr(fc, "id", "")
                    fn_args = getattr(fc, "arguments", {}) or {}

                    try:
                        if fn_name == "evaluate_mutual_fund":
                            f_query = str(fn_args.get("fund_query", message))
                            s_code = fn_args.get("scheme_code")
                            eval_res = await evaluate_mutual_fund_live(
                                f_query,
                                scheme_code=int(s_code) if s_code else None,
                                include_web_grounding=True,
                            )
                            primary_fund = eval_res
                            execution_steps.extend(eval_res.get("execution_steps", []))
                            citations.extend(eval_res.get("citations", []))
                            tool_payload = _compact_fund_payload_for_llm(eval_res)

                        elif fn_name == "compare_mutual_funds_and_overlap":
                            f_queries = list(fn_args.get("fund_queries") or [])
                            comp_res = await compare_mutual_funds_live(f_queries, include_web_grounding=False)
                            compared_funds = comp_res.get("compared_funds", [])
                            if compared_funds and not primary_fund:
                                primary_fund = compared_funds[0]
                            overlap_analysis = comp_res.get("overlap_analysis")
                            execution_steps.extend(comp_res.get("execution_steps", []))
                            citations.extend(comp_res.get("citations", []))
                            tool_payload = {
                                "compared_funds": [_compact_fund_payload_for_llm(cf) for cf in compared_funds],
                                "overlap_analysis": overlap_analysis,
                            }

                        elif fn_name == "search_indian_mutual_funds":
                            sq = str(fn_args.get("query", message))
                            matches = await search_schemes_live(sq, limit=8)
                            execution_steps.append(f"Searched AMFI schemes for '{sq}' ({len(matches)} results)")
                            tool_payload = {"matches": matches}

                        else:
                            tool_payload = {"error": f"Unknown tool: {fn_name}"}

                    except Exception as exc:
                        execution_steps.append(f"Tool '{fn_name}' error: {exc}")
                        tool_payload = {"error": str(exc)}

                    fn_results_input.append(
                        {
                            "type": "function_result",
                            "name": fn_name,
                            "call_id": fn_id,
                            "result": {
                                "content": [
                                    {"type": "text", "text": json.dumps(tool_payload, default=str)}
                                ]
                            },
                        }
                    )

                interaction = client.interactions.create(
                    model=settings.gemini_model,
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=AGENT_TOOLS + [{"type": "google_search"}],
                    previous_interaction_id=interaction.id,
                    input=fn_results_input,
                )

            md_text = interaction.output_text
            if not md_text:
                if compared_funds:
                    md_text = format_comparison_markdown(
                        {"compared_funds": compared_funds, "overlap_analysis": overlap_analysis}
                    )
                elif primary_fund:
                    md_text = format_single_fund_markdown(primary_fund)
                else:
                    md_text = "Completed evaluation."

            return AgentResponsePayload(
                query=message,
                interaction_id=getattr(interaction, "id", None),
                markdown_report=md_text,
                primary_fund=primary_fund,
                compared_funds=compared_funds,
                overlap_analysis=overlap_analysis,
                execution_steps=execution_steps,
                citations=citations,
            )
        except Exception as gemini_err:
            execution_steps.append(
                f"Gemini API fallback triggered ({gemini_err}); running direct quantitative & scraping pipeline."
            )

    # Direct Deterministic Pipeline Execution (used when GEMINI_API_KEY is not set or as fallback)
    mode, queries = _extract_fund_queries_from_message(message)
    if mode == "compare" and len(queries) >= 2:
        comp_res = await compare_mutual_funds_live(queries, include_web_grounding=True)
        compared_funds = comp_res["compared_funds"]
        primary_fund = compared_funds[0] if compared_funds else None
        overlap_analysis = comp_res.get("overlap_analysis")
        execution_steps.extend(comp_res.get("execution_steps", []))
        citations.extend(comp_res.get("citations", []))
        md_report = format_comparison_markdown(comp_res)
    else:
        eval_res = await evaluate_mutual_fund_live(queries[0], include_web_grounding=True)
        primary_fund = eval_res
        execution_steps.extend(eval_res.get("execution_steps", []))
        citations.extend(eval_res.get("citations", []))
        md_report = format_single_fund_markdown(eval_res)

    return AgentResponsePayload(
        query=message,
        interaction_id=None,
        markdown_report=md_report,
        primary_fund=primary_fund,
        compared_funds=compared_funds,
        overlap_analysis=overlap_analysis,
        execution_steps=execution_steps,
        citations=citations,
    )

