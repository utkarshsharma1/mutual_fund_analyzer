"""Integration tests for the FastAPI endpoints and Markdown report formatting."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.agent.orchestrator import (
    _extract_fund_queries_from_message,
    format_comparison_markdown,
    format_single_fund_markdown,
)
from app.agent.schemas import CompareFundsRequest
from app.main import app
from app.quant.metrics import compute_fund_quant_report
from app.quant.scorer import evaluate_fund_scorecard
from app.scrapers.fund_web_scraper import HoldingItem, ScrapedFundFundamentals
from tests.test_quant_scorer import _generate_benchmark_and_fund_series

client = TestClient(app)


def test_health_and_dashboard_routes() -> None:
    """Verify /api/health and the root interactive dashboard HTML load properly."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["mode"] == "stateless_on_demand"

    dash = client.get("/")
    assert dash.status_code == 200
    assert "Indian Mutual Fund AI Evaluation Agent" in dash.text


def test_markdown_report_synthesis() -> None:
    """Verify the single-fund Markdown report formatter includes all 5 pillars, metrics, and suggestion."""
    bench_df, fund_df = _generate_benchmark_and_fund_series()
    quant = compute_fund_quant_report(
        scheme_code=122639,
        scheme_name="Parag Parikh Flexi Cap Fund - Direct Plan - Growth",
        benchmark_name="Nifty 500 TRI",
        fund_nav_df=fund_df,
        benchmark_nav_df=bench_df,
    )
    fundamentals = ScrapedFundFundamentals(
        scheme_name="Parag Parikh Flexi Cap Fund - Direct Plan - Growth",
        amc_name="PPFAS Mutual Fund",
        sebi_category="Flexi Cap Fund",
        expense_ratio_pct=0.63,
        aum_crores=82000.0,
        fund_manager="Rajeev Thakkar",
        manager_tenure_years=11.0,
        top_holdings=[
            HoldingItem(company_name="HDFC Bank Ltd", weight_pct=8.1, sector="Financials"),
        ],
    )
    scorecard = evaluate_fund_scorecard(quant, fundamentals, sebi_category="Flexi Cap Fund")

    eval_payload = {
        "scheme_code": 122639,
        "scheme_name": fundamentals.scheme_name,
        "fund_house": fundamentals.amc_name,
        "sebi_category": "Flexi Cap Fund",
        "latest_nav": quant.latest_nav,
        "latest_nav_date": quant.as_of_date,
        "scorecard": scorecard.to_dict(),
        "quant_report": quant.to_dict(),
        "fundamentals": {
            "expense_ratio_pct": 0.63,
            "aum_crores": 82000.0,
            "fund_manager": "Rajeev Thakkar",
            "manager_tenure_years": 11.0,
            "exit_load": "2% within 365 days",
        },
        "qualitative_intel": {
            "summary_markdown": "- **Strategy**: Value-oriented flexi-cap with international equity exposure."
        },
    }

    md = format_single_fund_markdown(eval_payload)
    assert "100-Point Scorecard Breakdown" in md
    assert "Rolling vs Trailing Return Analysis" in md
    assert "Detailed Investment Suggestion" in md
    assert "STRONG CONTENDER / CORE BUY" in md


def test_five_fund_comparison_support() -> None:
    """Verify 5+ mutual fund comparison extraction, schema validation, and markdown leaderboard."""
    five_funds = [
        "Parag Parikh Flexi Cap Fund",
        "HDFC Flexi Cap Fund",
        "JM Flexicap Fund",
        "Quant Flexi Cap Fund",
        "Kotak Flexicap Fund",
        "UTI Flexi Cap Fund",
    ]
    req = CompareFundsRequest(queries=five_funds)
    assert len(req.queries) == 6

    mode, parsed = _extract_fund_queries_from_message(
        "Compare Parag Parikh Flexi Cap, HDFC Flexi Cap, JM Flexicap, Quant Flexi Cap, and Kotak Flexicap"
    )
    assert mode == "compare"
    assert len(parsed) == 5

    bench_df, fund_df = _generate_benchmark_and_fund_series()
    quant = compute_fund_quant_report(
        scheme_code=122639,
        scheme_name="Fund 1",
        benchmark_name="Nifty 500 TRI",
        fund_nav_df=fund_df,
        benchmark_nav_df=bench_df,
    )
    fundamentals = ScrapedFundFundamentals(
        scheme_name="Fund 1",
        sebi_category="Flexi Cap Fund",
        expense_ratio_pct=0.60,
        aum_crores=15000.0,
    )
    sc = evaluate_fund_scorecard(quant, fundamentals, sebi_category="Flexi Cap Fund")

    compared_payloads = [
        {
            "scheme_code": 100000 + i,
            "scheme_name": name,
            "fund_house": "AMC",
            "sebi_category": "Flexi Cap Fund",
            "scorecard": sc.to_dict(),
            "quant_report": quant.to_dict(),
            "fundamentals": {"expense_ratio_pct": 0.6, "aum_crores": 15000.0},
        }
        for i, name in enumerate(five_funds[:5])
    ]

    comp_md = format_comparison_markdown({"compared_funds": compared_payloads, "overlap_analysis": None})
    assert "5 Funds Evaluated" in comp_md
    assert "5-Pillar Score Breakdown Across Compared Funds" in comp_md


