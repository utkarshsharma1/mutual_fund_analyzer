"""Unit tests for the in-memory quantitative engine, 100-point scorer, and portfolio overlap calculator."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.quant.metrics import compute_fund_quant_report
from app.quant.overlap import compute_portfolio_overlap
from app.quant.scorer import evaluate_fund_scorecard
from app.scrapers.fund_web_scraper import HoldingItem, ScrapedFundFundamentals


def _generate_benchmark_and_fund_series(
    years: int = 6,
    bench_annual_drift: float = 0.14,
    alpha_annual: float = 0.045,
    beta: float = 0.88,
    seed: int = 7,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create correlated daily benchmark and outperforming fund NAV series over `years`."""
    rng = np.random.default_rng(seed)
    days = years * 252
    dates = pd.bdate_range(end="2026-11-01", periods=days)

    bench_daily_mu = bench_annual_drift / 252.0
    bench_daily_sigma = 0.13 / np.sqrt(252.0)
    bench_rets = bench_daily_mu + rng.normal(0.0, bench_daily_sigma, size=days)

    alpha_daily = alpha_annual / 252.0
    idio_sigma = 0.04 / np.sqrt(252.0)
    fund_rets = alpha_daily + beta * bench_rets + rng.normal(0.0, idio_sigma, size=days)

    bench_navs = 100.0 * np.cumprod(1.0 + bench_rets)
    fund_navs = 100.0 * np.cumprod(1.0 + fund_rets)

    bench_df = pd.DataFrame({"date": dates, "nav": bench_navs})
    fund_df = pd.DataFrame({"date": dates, "nav": fund_navs})
    return bench_df, fund_df


def test_quant_report_and_100_point_scorecard() -> None:
    """Verify rolling return distributions, alpha/beta/sharpe math, and 100-point rubric scoring."""
    bench_df, fund_df = _generate_benchmark_and_fund_series()

    quant = compute_fund_quant_report(
        scheme_code=122639,
        scheme_name="Synthetic Flexi Cap Direct Growth",
        benchmark_name="Nifty 500 TRI",
        fund_nav_df=fund_df,
        benchmark_nav_df=bench_df,
    )

    assert "1Y" in quant.rolling_returns
    assert "3Y" in quant.rolling_returns
    assert "5Y" in quant.rolling_returns
    assert quant.risk_metrics.sharpe_ratio > 0.5
    assert quant.risk_metrics.jensen_alpha_pct > 2.0
    assert 0.70 <= quant.risk_metrics.beta <= 1.05
    assert quant.risk_metrics.downside_capture_ratio < 98.0
    assert len(quant.chart_rolling_3y) > 10
    assert len(quant.chart_drawdown) > 10

    fundamentals = ScrapedFundFundamentals(
        scheme_name="Synthetic Flexi Cap Direct Growth",
        amc_name="Test AMC",
        sebi_category="Flexi Cap Fund",
        expense_ratio_pct=0.58,
        aum_crores=12500.0,
        fund_manager="Rajeev Thakkar",
        manager_tenure_years=8.5,
        top_holdings=[
            HoldingItem(company_name="HDFC Bank Ltd", weight_pct=8.2, sector="Financials"),
            HoldingItem(company_name="ICICI Bank Ltd", weight_pct=6.5, sector="Financials"),
            HoldingItem(company_name="Infosys Ltd", weight_pct=5.4, sector="Technology"),
            HoldingItem(company_name="ITC Ltd", weight_pct=4.8, sector="FMCG"),
            HoldingItem(company_name="Bharti Airtel Ltd", weight_pct=4.5, sector="Telecom"),
            HoldingItem(company_name="Axis Bank Ltd", weight_pct=4.2, sector="Financials"),
        ],
    )

    scorecard = evaluate_fund_scorecard(quant, fundamentals, sebi_category="Flexi Cap Fund")
    assert 0.0 <= scorecard.total_score <= 100.0
    assert len(scorecard.pillars) == 5
    assert scorecard.total_score >= 74.0
    assert scorecard.letter_grade in {"A+", "A"}
    assert scorecard.verdict == "STRONG CONTENDER / CORE BUY"
    assert len(scorecard.strengths) >= 2


def test_portfolio_overlap_calculation() -> None:
    """Verify pairwise stock weight overlap and common stock extraction."""
    fund_a = ScrapedFundFundamentals(
        scheme_name="Fund A Flexi Cap",
        top_holdings=[
            HoldingItem(company_name="HDFC Bank Limited", weight_pct=9.0, sector="Financials"),
            HoldingItem(company_name="Infosys Ltd", weight_pct=6.0, sector="IT"),
            HoldingItem(company_name="ITC Limited", weight_pct=5.0, sector="FMCG"),
        ],
    )
    fund_b = ScrapedFundFundamentals(
        scheme_name="Fund B Large Cap",
        top_holdings=[
            HoldingItem(company_name="HDFC Bank Ltd", weight_pct=7.5, sector="Financials"),
            HoldingItem(company_name="Infosys Limited", weight_pct=8.0, sector="IT"),
            HoldingItem(company_name="Larsen & Toubro Ltd", weight_pct=4.5, sector="Construction"),
        ],
    )

    overlap = compute_portfolio_overlap([fund_a, fund_b])
    assert len(overlap["pairwise_overlap"]) == 1
    pair = overlap["pairwise_overlap"][0]
    # min(9.0, 7.5) + min(6.0, 8.0) = 7.5 + 6.0 = 13.5%
    assert pair["weight_overlap_pct"] == 13.5
    assert pair["common_stocks_count"] == 2
