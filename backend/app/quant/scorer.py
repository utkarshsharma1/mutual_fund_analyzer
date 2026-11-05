"""100-Point Mutual Fund Evaluation Scorer & Recommendation Verdict Engine.

Grades any Indian mutual fund out of 100 across 5 institutional pillars:
1. Performance Consistency (30 pts)
2. Downside Protection & Risk Control (25 pts)
3. Alpha & Risk-Adjusted Return (20 pts)
4. Cost, Size & Liquidity Health (15 pts)
5. Portfolio & Manager Quality (10 pts)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.quant.metrics import FundQuantReport
from app.scrapers.fund_web_scraper import ScrapedFundFundamentals


@dataclass
class PillarScore:
    """Score and explanation for one of the 5 evaluation pillars."""

    name: str
    score: float
    max_score: float
    rating_label: str
    rationale: str


@dataclass
class FundScorecard:
    """Complete 100-point scorecard, verdict, pros/cons, and investor suitability recommendation."""

    scheme_code: int
    scheme_name: str
    sebi_category: str
    benchmark_name: str
    total_score: float
    max_score: float
    letter_grade: str
    verdict: str
    verdict_badge_color: str
    executive_summary: str
    pillars: list[PillarScore] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    risks_and_red_flags: list[str] = field(default_factory=list)
    investor_suitability: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clamp(val: float, low: float, high: float) -> float:
    return max(low, min(high, val))


def _label_for_ratio(ratio: float) -> str:
    if ratio >= 0.80:
        return "Excellent"
    if ratio >= 0.65:
        return "Strong"
    if ratio >= 0.50:
        return "Average"
    return "Weak"


def evaluate_fund_scorecard(
    quant: FundQuantReport,
    fundamentals: ScrapedFundFundamentals,
    sebi_category: str = "",
) -> FundScorecard:
    """Evaluate a mutual fund on the 100-point rubric and generate actionable suggestions."""
    cat = (sebi_category or fundamentals.sebi_category or "Equity Scheme").strip()
    cat_lower = cat.lower()

    strengths: list[str] = []
    red_flags: list[str] = []

    # -------------------------------------------------------------------------
    # Pillar 1: Performance Consistency (Max 30 pts)
    # -------------------------------------------------------------------------
    roll_3y = quant.rolling_returns.get("3Y") or quant.rolling_returns.get("1Y")
    roll_5y = quant.rolling_returns.get("5Y")

    if roll_3y:
        # Outperformance consistency % (0-100%) -> up to 16 pts
        consistency_pts = _clamp((roll_3y.outperformance_consistency_pct / 100.0) * 16.0, 0.0, 16.0)
        # Rolling median excess return over benchmark (-3% to +5% mapped to 0..10 pts)
        excess_pts = _clamp(((roll_3y.excess_median_cagr_pct + 2.0) / 6.0) * 10.0, 0.0, 10.0)
        p1_score = consistency_pts + excess_pts

        if roll_5y:
            bonus_5y = _clamp((roll_5y.outperformance_consistency_pct / 100.0) * 4.0, 0.0, 4.0)
            p1_score += bonus_5y
        else:
            p1_score = _clamp(p1_score * (30.0 / 26.0), 0.0, 30.0)

        p1_score = round(_clamp(p1_score, 0.0, 30.0), 1)
        p1_rationale = (
            f"Beat {quant.benchmark_name} in {roll_3y.outperformance_consistency_pct:.1f}% of "
            f"{roll_3y.window_years}Y rolling periods with a median rolling return of "
            f"{roll_3y.fund_median_cagr_pct:.2f}% vs benchmark {roll_3y.benchmark_median_cagr_pct:.2f}% "
            f"(+{roll_3y.excess_median_cagr_pct:.2f}% median spread)."
        )
        if roll_3y.outperformance_consistency_pct >= 75.0:
            strengths.append(
                f"High Rolling Return Consistency: Outperformed {quant.benchmark_name} in "
                f"{roll_3y.outperformance_consistency_pct:.1f}% of {roll_3y.window_years}Y rolling periods "
                f"(median {roll_3y.fund_median_cagr_pct:.2f}% CAGR)."
            )
        elif roll_3y.outperformance_consistency_pct < 45.0:
            red_flags.append(
                f"Low Benchmark Consistency: Beat {quant.benchmark_name} in only "
                f"{roll_3y.outperformance_consistency_pct:.1f}% of {roll_3y.window_years}Y rolling windows."
            )
    else:
        p1_score = 15.0
        p1_rationale = "Limited historical NAV window (<1Y) for multi-year rolling consistency."

    # -------------------------------------------------------------------------
    # Pillar 2: Downside Protection & Risk Control (Max 25 pts)
    # -------------------------------------------------------------------------
    rm = quant.risk_metrics
    # Downside Capture (< 100% is desirable; 70% -> 12 pts, 100% -> 7 pts, 125% -> 2 pts)
    dc_pts = _clamp(12.0 - ((rm.downside_capture_ratio - 70.0) / 55.0) * 10.0, 0.0, 12.0)

    # Sortino relative to benchmark & absolute threshold (up to 8 pts)
    sortino_diff = rm.sortino_ratio - rm.benchmark_sortino_ratio
    sortino_pts = _clamp(4.5 + sortino_diff * 3.5, 0.0, 8.0)

    # Max Drawdown cushion vs benchmark (up to 5 pts)
    dd_improvement = rm.max_drawdown_pct - rm.benchmark_max_drawdown_pct  # positive means shallower drawdown
    dd_pts = _clamp(3.0 + (dd_improvement / 5.0) * 2.0, 0.0, 5.0)

    p2_score = round(_clamp(dc_pts + sortino_pts + dd_pts, 0.0, 25.0), 1)
    p2_rationale = (
        f"Downside capture of {rm.downside_capture_ratio:.1f}% (upside capture {rm.upside_capture_ratio:.1f}%), "
        f"Sortino ratio of {rm.sortino_ratio:.2f} (vs {rm.benchmark_sortino_ratio:.2f}), and "
        f"max drawdown of {rm.max_drawdown_pct:.2f}%."
    )

    if rm.downside_capture_ratio <= 90.0:
        strengths.append(
            f"Superior Downside Cushion: Captures only {rm.downside_capture_ratio:.1f}% of benchmark falls "
            f"while capturing {rm.upside_capture_ratio:.1f}% of market rallies."
        )
    elif rm.downside_capture_ratio >= 110.0:
        red_flags.append(
            f"Elevated Downside Vulnerability: Downside capture of {rm.downside_capture_ratio:.1f}% "
            f"indicates steeper drawdowns than {quant.benchmark_name} during market corrections."
        )

    # -------------------------------------------------------------------------
    # Pillar 3: Alpha & Risk-Adjusted Return (Max 20 pts)
    # -------------------------------------------------------------------------
    # Jensen's Alpha (-3% to +5% mapped to 0..12 pts)
    alpha_pts = _clamp(((rm.jensen_alpha_pct + 2.5) / 7.5) * 12.0, 0.0, 12.0)
    # Sharpe & Information Ratio (up to 8 pts)
    sharpe_diff = rm.sharpe_ratio - rm.benchmark_sharpe_ratio
    sharpe_pts = _clamp(4.0 + sharpe_diff * 4.0 + rm.information_ratio * 1.5, 0.0, 8.0)

    p3_score = round(_clamp(alpha_pts + sharpe_pts, 0.0, 20.0), 1)
    p3_rationale = (
        f"Annualized Jensen's Alpha of {rm.jensen_alpha_pct:+.2f}% with Beta {rm.beta:.2f}, "
        f"Sharpe ratio {rm.sharpe_ratio:.2f} (vs {rm.benchmark_sharpe_ratio:.2f}), and "
        f"Information ratio {rm.information_ratio:.2f}."
    )

    if rm.jensen_alpha_pct >= 2.0:
        strengths.append(
            f"Strong Risk-Adjusted Alpha: Generated {rm.jensen_alpha_pct:+.2f}% annualized Jensen's Alpha "
            f"(Beta {rm.beta:.2f}, Sharpe {rm.sharpe_ratio:.2f})."
        )
    elif rm.jensen_alpha_pct < -1.0:
        red_flags.append(
            f"Negative Risk-Adjusted Alpha ({rm.jensen_alpha_pct:+.2f}%): Active stock selection has "
            f"lagged a low-cost {quant.benchmark_name} index fund on a risk-adjusted basis."
        )

    # -------------------------------------------------------------------------
    # Pillar 4: Cost, Size & Liquidity Health (Max 15 pts)
    # -------------------------------------------------------------------------
    ter = fundamentals.expense_ratio_pct
    aum = fundamentals.aum_crores

    # TER score (max 8 pts)
    if ter is not None:
        is_index = "index" in cat_lower or "index" in quant.scheme_name.lower()
        target_ter = 0.25 if is_index else 0.75
        ter_pts = _clamp(8.0 - max(0.0, ter - target_ter) * 4.5, 1.5, 8.0)
        if ter <= 0.65:
            strengths.append(f"Competitive Cost Structure: Low Direct Plan Expense Ratio of {ter:.2f}%.")
        elif ter >= 1.25:
            red_flags.append(f"High Expense Drag: Expense Ratio of {ter:.2f}% is above Direct Plan category norms.")
    else:
        ter_pts = 5.5

    # AUM Health score (max 7 pts)
    if aum is not None:
        is_small_cap = "small" in cat_lower
        is_mid_cap = "mid" in cat_lower and "large" not in cat_lower
        if aum < 200:
            aum_pts = 3.5
            red_flags.append(f"Sub-scale AUM (₹{aum:,.0f} Cr): Small asset base may face higher expense or concentration risk.")
        elif is_small_cap and aum > 35000:
            aum_pts = 4.0
            red_flags.append(
                f"AUM Size Bloat in Small Cap (₹{aum:,.0f} Cr): Large corpus can constrain liquidity and nimble entry/exit in small-cap stocks."
            )
        elif is_mid_cap and aum > 55000:
            aum_pts = 4.5
            red_flags.append(
                f"Large Mid-Cap Corpus (₹{aum:,.0f} Cr): High AUM requires careful monitoring for liquidity and mid-cap capacity."
            )
        else:
            aum_pts = 6.5
    else:
        aum_pts = 5.0

    p4_score = round(_clamp(ter_pts + aum_pts, 0.0, 15.0), 1)
    ter_str = f"{ter:.2f}%" if ter is not None else "N/A"
    aum_str = f"₹{aum:,.0f} Cr" if aum is not None else "N/A"
    p4_rationale = f"Expense ratio of {ter_str} and AUM of {aum_str} relative to {cat} liquidity norms."

    # -------------------------------------------------------------------------
    # Pillar 5: Portfolio & Manager Quality (Max 10 pts)
    # -------------------------------------------------------------------------
    top_10_wt = sum(h.weight_pct for h in fundamentals.top_holdings[:10]) if fundamentals.top_holdings else 0.0
    tenure = fundamentals.manager_tenure_years

    # Manager tenure (max 5 pts)
    if tenure is not None:
        tenure_pts = _clamp(2.0 + (tenure / 5.0) * 3.0, 1.5, 5.0)
        if tenure >= 4.0:
            strengths.append(
                f"Experienced Fund Management: {fundamentals.fund_manager or 'Lead manager'} has {tenure:.1f}+ years tenure on the scheme."
            )
    elif fundamentals.fund_manager:
        tenure_pts = 3.8
    else:
        tenure_pts = 3.5

    # Concentration & diversification (max 5 pts)
    if top_10_wt > 0:
        if 30.0 <= top_10_wt <= 58.0:
            conc_pts = 4.5
        elif top_10_wt > 65.0:
            conc_pts = 2.8
            red_flags.append(
                f"High Top-10 Stock Concentration ({top_10_wt:.1f}%): Portfolio carries elevated single-stock/sector risk."
            )
        else:
            conc_pts = 3.8
    else:
        conc_pts = 3.8

    p5_score = round(_clamp(tenure_pts + conc_pts, 0.0, 10.0), 1)
    p5_rationale = (
        f"Manager: {fundamentals.fund_manager or 'Institutional Team'}"
        + (f" ({tenure:.1f} yrs tenure)" if tenure else "")
        + (f"; Top-10 holdings represent {top_10_wt:.1f}% of portfolio." if top_10_wt > 0 else ".")
    )

    # -------------------------------------------------------------------------
    # Total Score, Grade & Verdict
    # -------------------------------------------------------------------------
    pillars = [
        PillarScore("Performance Consistency", p1_score, 30.0, _label_for_ratio(p1_score / 30.0), p1_rationale),
        PillarScore("Downside Protection & Risk", p2_score, 25.0, _label_for_ratio(p2_score / 25.0), p2_rationale),
        PillarScore("Alpha & Risk-Adjusted Return", p3_score, 20.0, _label_for_ratio(p3_score / 20.0), p3_rationale),
        PillarScore("Cost, Size & Liquidity Health", p4_score, 15.0, _label_for_ratio(p4_score / 15.0), p4_rationale),
        PillarScore("Portfolio & Manager Quality", p5_score, 10.0, _label_for_ratio(p5_score / 10.0), p5_rationale),
    ]

    total_score = round(sum(p.score for p in pillars), 1)

    if total_score >= 82.0:
        grade = "A+"
        verdict = "STRONG CONTENDER / CORE BUY"
        badge_color = "emerald"
    elif total_score >= 74.0:
        grade = "A"
        verdict = "STRONG CONTENDER / CORE BUY"
        badge_color = "emerald"
    elif total_score >= 65.0:
        grade = "B+"
        verdict = "WORTH CONSIDERING / HOLD"
        badge_color = "blue"
    elif total_score >= 55.0:
        grade = "B"
        verdict = "WATCHLIST / NEUTRAL"
        badge_color = "amber"
    elif total_score >= 45.0:
        grade = "C"
        verdict = "WATCHLIST / NEUTRAL"
        badge_color = "amber"
    else:
        grade = "D"
        verdict = "AVOID / SWITCH CANDIDATE"
        badge_color = "rose"

    if not strengths:
        strengths.append(
            f"Regulated {cat} exposure with {quant.fund_age_years:.1f} years of operational track record."
        )
    if not red_flags:
        red_flags.append(
            "Subject to standard equity market cyclicality; monitor rolling 3Y alpha semi-annually."
        )

    # Investor suitability profile
    if any(k in cat_lower for k in ("small", "mid")):
        horizon = "7+ Years (Full Market Cycle)"
        mode = "Staggered SIP / STP strongly preferred over Lumpsum due to valuation volatility"
        risk_appetite = "High / Aggressive Equity Investors"
        allocation_role = "Satellite Portfolio Allocation (15%–25% of equity book)"
    elif any(k in cat_lower for k in ("flexi", "multi", "large", "value", "contra", "elss")):
        horizon = "5+ Years"
        mode = "Core SIP or Staggered Lumpsum on market dips"
        risk_appetite = "Moderate-to-High Equity Investors"
        allocation_role = "Core Portfolio Anchor (40%–60% of equity book)"
    else:
        horizon = "3–5+ Years"
        mode = "SIP or Lumpsum aligned with asset allocation"
        risk_appetite = "Moderate Investors"
        allocation_role = "Diversifier / Tactical Allocation"

    exec_summary = (
        f"{quant.scheme_name} scores {total_score}/100 (Grade {grade}: {verdict}). "
        f"Over {rm.evaluation_window_years:.1f}Y, it delivered {rm.jensen_alpha_pct:+.2f}% annualized Jensen's Alpha "
        f"with a Sharpe ratio of {rm.sharpe_ratio:.2f} and {rm.downside_capture_ratio:.1f}% downside capture vs {quant.benchmark_name}."
    )

    return FundScorecard(
        scheme_code=quant.scheme_code,
        scheme_name=quant.scheme_name,
        sebi_category=cat,
        benchmark_name=quant.benchmark_name,
        total_score=total_score,
        max_score=100.0,
        letter_grade=grade,
        verdict=verdict,
        verdict_badge_color=badge_color,
        executive_summary=exec_summary,
        pillars=pillars,
        strengths=strengths,
        risks_and_red_flags=red_flags,
        investor_suitability={
            "recommended_horizon": horizon,
            "investment_mode": mode,
            "risk_profile": risk_appetite,
            "portfolio_role": allocation_role,
        },
    )

