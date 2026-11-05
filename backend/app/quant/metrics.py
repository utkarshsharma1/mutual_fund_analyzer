"""In-memory quantitative metrics calculator for Indian Mutual Funds.

Computes trailing CAGR, daily rolling return distributions (1Y, 3Y, 5Y),
outperformance consistency, Sharpe, Sortino, Jensen's Alpha, Beta, R-squared,
Information Ratio, Upside/Downside Capture, Max Drawdown, and Ulcer Index.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from app.config import settings


@dataclass
class RollingWindowStats:
    """Distribution statistics for a k-year daily rolling return window."""

    window_years: int
    observations: int
    fund_median_cagr_pct: float
    fund_mean_cagr_pct: float
    fund_min_cagr_pct: float
    fund_max_cagr_pct: float
    fund_p25_cagr_pct: float
    fund_p75_cagr_pct: float
    benchmark_median_cagr_pct: float
    excess_median_cagr_pct: float
    outperformance_consistency_pct: float  # % of rolling periods where Fund > Benchmark
    positive_return_periods_pct: float     # % of rolling periods where Fund > 0%


@dataclass
class RiskAndRelativeMetrics:
    """Risk and CAPM relative performance metrics computed over the primary evaluation window."""

    evaluation_window_years: float
    risk_free_rate_pct: float
    annualized_volatility_pct: float
    benchmark_volatility_pct: float
    sharpe_ratio: float
    benchmark_sharpe_ratio: float
    sortino_ratio: float
    benchmark_sortino_ratio: float
    max_drawdown_pct: float
    benchmark_max_drawdown_pct: float
    ulcer_index: float
    beta: float
    jensen_alpha_pct: float
    r_squared: float
    information_ratio: float
    upside_capture_ratio: float
    downside_capture_ratio: float


@dataclass
class FundQuantReport:
    """Complete deterministic quantitative tear-sheet for a mutual fund vs its benchmark."""

    scheme_code: int
    scheme_name: str
    benchmark_name: str
    as_of_date: str
    fund_age_years: float
    latest_nav: float
    trailing_returns_cagr_pct: dict[str, dict[str, float | None]]
    rolling_returns: dict[str, RollingWindowStats]
    risk_metrics: RiskAndRelativeMetrics
    chart_rolling_3y: list[dict[str, Any]] = field(default_factory=list)
    chart_drawdown: list[dict[str, Any]] = field(default_factory=list)
    chart_nav_rebased: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _align_nav_series(fund_df: pd.DataFrame, bench_df: pd.DataFrame) -> pd.DataFrame:
    """Align fund and benchmark NAV series on common trading dates with forward-fill for minor holidays."""
    f = fund_df[["date", "nav"]].rename(columns={"nav": "fund_nav"}).sort_values("date")
    b = bench_df[["date", "nav"]].rename(columns={"nav": "bench_nav"}).sort_values("date")

    merged = pd.merge_asof(
        f,
        b,
        on="date",
        direction="backward",
        tolerance=pd.Timedelta(days=7),
    ).dropna(subset=["fund_nav", "bench_nav"])
    return merged.reset_index(drop=True)


def _compute_trailing_cagr(df: pd.DataFrame, col: str, years: float) -> float | None:
    """Compute point-to-point annualized return (CAGR %) over the trailing `years`."""
    if df.empty:
        return None
    end_row = df.iloc[-1]
    end_date = end_row["date"]
    target_date = end_date - pd.Timedelta(days=int(round(years * 365.25)))

    # Require data within 15 days of target_date
    candidates = df[df["date"] <= target_date]
    if candidates.empty:
        return None
    start_row = candidates.iloc[-1]
    if abs((target_date - start_row["date"]).days) > 20:
        return None

    actual_years = (end_date - start_row["date"]).days / 365.25
    if actual_years <= 0:
        return None
    start_val = float(start_row[col])
    end_val = float(end_row[col])
    if start_val <= 0:
        return None

    if years < 1.0:
        ret = (end_val / start_val - 1.0) * 100.0
    else:
        ret = ((end_val / start_val) ** (1.0 / actual_years) - 1.0) * 100.0
    return round(float(ret), 2)


def _compute_rolling_window(
    aligned_df: pd.DataFrame,
    window_years: int,
) -> tuple[RollingWindowStats | None, pd.DataFrame | None]:
    """Compute daily rolling annualized return distribution for `window_years`."""
    approx_days = int(round(window_years * 252))
    if len(aligned_df) < approx_days + 30:
        return None, None

    # Use exact date offset matching via merge_asof for accurate calendar-year rolling windows
    current = aligned_df[["date", "fund_nav", "bench_nav"]].copy()
    current["lookup_date"] = current["date"] - pd.Timedelta(days=int(round(window_years * 365.25)))

    past = aligned_df[["date", "fund_nav", "bench_nav"]].rename(
        columns={
            "date": "past_date",
            "fund_nav": "past_fund_nav",
            "bench_nav": "past_bench_nav",
        }
    )

    rolled = pd.merge_asof(
        current.sort_values("lookup_date"),
        past.sort_values("past_date"),
        left_on="lookup_date",
        right_on="past_date",
        direction="backward",
        tolerance=pd.Timedelta(days=10),
    ).dropna(subset=["past_fund_nav", "past_bench_nav"])

    if len(rolled) < 30:
        return None, None

    rolled = rolled.sort_values("date").reset_index(drop=True)
    actual_yrs = (rolled["date"] - rolled["past_date"]).dt.days / 365.25
    valid = actual_yrs > (window_years * 0.9)
    rolled = rolled[valid].copy()
    actual_yrs = actual_yrs[valid]

    if len(rolled) < 20:
        return None, None

    rolled["fund_cagr"] = ((rolled["fund_nav"] / rolled["past_fund_nav"]) ** (1.0 / actual_yrs) - 1.0) * 100.0
    rolled["bench_cagr"] = ((rolled["bench_nav"] / rolled["past_bench_nav"]) ** (1.0 / actual_yrs) - 1.0) * 100.0
    rolled["excess_cagr"] = rolled["fund_cagr"] - rolled["bench_cagr"]

    f_s = rolled["fund_cagr"]
    b_s = rolled["bench_cagr"]

    outperf_pct = float((f_s > b_s).mean() * 100.0)
    pos_pct = float((f_s > 0.0).mean() * 100.0)

    stats = RollingWindowStats(
        window_years=window_years,
        observations=int(len(rolled)),
        fund_median_cagr_pct=round(float(f_s.median()), 2),
        fund_mean_cagr_pct=round(float(f_s.mean()), 2),
        fund_min_cagr_pct=round(float(f_s.min()), 2),
        fund_max_cagr_pct=round(float(f_s.max()), 2),
        fund_p25_cagr_pct=round(float(f_s.quantile(0.25)), 2),
        fund_p75_cagr_pct=round(float(f_s.quantile(0.75)), 2),
        benchmark_median_cagr_pct=round(float(b_s.median()), 2),
        excess_median_cagr_pct=round(float((f_s - b_s).median()), 2),
        outperformance_consistency_pct=round(outperf_pct, 1),
        positive_return_periods_pct=round(pos_pct, 1),
    )
    return stats, rolled


def _compute_risk_and_relative_metrics(
    aligned_df: pd.DataFrame,
    risk_free_rate: float = settings.risk_free_rate,
) -> tuple[RiskAndRelativeMetrics, pd.DataFrame]:
    """Compute Sharpe, Sortino, Alpha, Beta, R2, Capture Ratios, and Drawdown over trailing 3Y (or available)."""
    end_date = aligned_df["date"].iloc[-1]
    three_yr_cutoff = end_date - pd.Timedelta(days=int(round(3 * 365.25)))
    window_df = aligned_df[aligned_df["date"] >= three_yr_cutoff].copy()

    if len(window_df) < 180:
        window_df = aligned_df.copy()

    window_df = window_df.sort_values("date").reset_index(drop=True)
    eval_years = max((window_df["date"].iloc[-1] - window_df["date"].iloc[0]).days / 365.25, 0.25)

    window_df["fund_ret"] = window_df["fund_nav"].pct_change()
    window_df["bench_ret"] = window_df["bench_nav"].pct_change()
    ret_df = window_df.dropna(subset=["fund_ret", "bench_ret"]).copy()

    rf_daily = (1.0 + risk_free_rate) ** (1.0 / 252.0) - 1.0

    f_ret = ret_df["fund_ret"].to_numpy(dtype=float)
    b_ret = ret_df["bench_ret"].to_numpy(dtype=float)

    # Annualized volatility
    f_vol = float(np.std(f_ret, ddof=1) * np.sqrt(252) * 100.0) if len(f_ret) > 2 else 0.0
    b_vol = float(np.std(b_ret, ddof=1) * np.sqrt(252) * 100.0) if len(b_ret) > 2 else 0.0

    # Annualized geometric return in window
    f_cagr = (float(window_df["fund_nav"].iloc[-1]) / float(window_df["fund_nav"].iloc[0])) ** (1.0 / eval_years) - 1.0
    b_cagr = (float(window_df["bench_nav"].iloc[-1]) / float(window_df["bench_nav"].iloc[0])) ** (1.0 / eval_years) - 1.0

    # Sharpe Ratio
    sharpe = ((f_cagr - risk_free_rate) / (f_vol / 100.0)) if f_vol > 0 else 0.0
    b_sharpe = ((b_cagr - risk_free_rate) / (b_vol / 100.0)) if b_vol > 0 else 0.0

    # Sortino Ratio (downside deviation below daily risk-free rate)
    f_downside_diff = np.minimum(0.0, f_ret - rf_daily)
    b_downside_diff = np.minimum(0.0, b_ret - rf_daily)
    f_down_vol = float(np.sqrt(np.mean(f_downside_diff**2)) * np.sqrt(252))
    b_down_vol = float(np.sqrt(np.mean(b_downside_diff**2)) * np.sqrt(252))

    sortino = ((f_cagr - risk_free_rate) / f_down_vol) if f_down_vol > 0 else 0.0
    b_sortino = ((b_cagr - risk_free_rate) / b_down_vol) if b_down_vol > 0 else 0.0

    # Beta, R-squared, and Jensen's Alpha
    if len(b_ret) > 5 and np.var(b_ret, ddof=1) > 0:
        cov_matrix = np.cov(f_ret, b_ret, ddof=1)
        beta = float(cov_matrix[0, 1] / cov_matrix[1, 1])
        corr = float(np.corrcoef(f_ret, b_ret)[0, 1])
        r_sq = corr**2
    else:
        beta = 1.0
        r_sq = 0.0

    jensen_alpha_pct = ((f_cagr - risk_free_rate) - beta * (b_cagr - risk_free_rate)) * 100.0

    # Information Ratio
    active_ret = f_ret - b_ret
    tracking_error = float(np.std(active_ret, ddof=1) * np.sqrt(252)) if len(active_ret) > 2 else 0.0
    info_ratio = ((f_cagr - b_cagr) / tracking_error) if tracking_error > 0 else 0.0

    # Drawdown & Ulcer Index
    f_cummax = window_df["fund_nav"].cummax()
    b_cummax = window_df["bench_nav"].cummax()
    window_df["fund_dd_pct"] = (window_df["fund_nav"] / f_cummax - 1.0) * 100.0
    window_df["bench_dd_pct"] = (window_df["bench_nav"] / b_cummax - 1.0) * 100.0

    max_dd = float(window_df["fund_dd_pct"].min())
    b_max_dd = float(window_df["bench_dd_pct"].min())
    ulcer_idx = float(np.sqrt(np.mean(window_df["fund_dd_pct"] ** 2)))

    # Upside & Downside Capture Ratios (using monthly resampled returns)
    monthly = (
        window_df.set_index("date")[["fund_nav", "bench_nav"]]
        .resample("ME")
        .last()
        .pct_change()
        .dropna()
    )
    up_months = monthly[monthly["bench_nav"] > 0]
    down_months = monthly[monthly["bench_nav"] < 0]

    upside_capture = 100.0
    if len(up_months) >= 3:
        f_up_geo = float((1.0 + up_months["fund_nav"]).prod() ** (1.0 / len(up_months)) - 1.0)
        b_up_geo = float((1.0 + up_months["bench_nav"]).prod() ** (1.0 / len(up_months)) - 1.0)
        if b_up_geo != 0:
            upside_capture = (f_up_geo / b_up_geo) * 100.0

    downside_capture = 100.0
    if len(down_months) >= 3:
        f_dn_geo = float((1.0 + down_months["fund_nav"]).prod() ** (1.0 / len(down_months)) - 1.0)
        b_dn_geo = float((1.0 + down_months["bench_nav"]).prod() ** (1.0 / len(down_months)) - 1.0)
        if b_dn_geo != 0:
            downside_capture = (f_dn_geo / b_dn_geo) * 100.0

    metrics = RiskAndRelativeMetrics(
        evaluation_window_years=round(eval_years, 2),
        risk_free_rate_pct=round(risk_free_rate * 100.0, 2),
        annualized_volatility_pct=round(f_vol, 2),
        benchmark_volatility_pct=round(b_vol, 2),
        sharpe_ratio=round(sharpe, 2),
        benchmark_sharpe_ratio=round(b_sharpe, 2),
        sortino_ratio=round(sortino, 2),
        benchmark_sortino_ratio=round(b_sortino, 2),
        max_drawdown_pct=round(max_dd, 2),
        benchmark_max_drawdown_pct=round(b_max_dd, 2),
        ulcer_index=round(ulcer_idx, 2),
        beta=round(beta, 2),
        jensen_alpha_pct=round(jensen_alpha_pct, 2),
        r_squared=round(r_sq, 2),
        information_ratio=round(info_ratio, 2),
        upside_capture_ratio=round(upside_capture, 1),
        downside_capture_ratio=round(downside_capture, 1),
    )
    return metrics, window_df


def compute_fund_quant_report(
    scheme_code: int,
    scheme_name: str,
    benchmark_name: str,
    fund_nav_df: pd.DataFrame,
    benchmark_nav_df: pd.DataFrame,
) -> FundQuantReport:
    """Compute a complete, deterministic quantitative report for a mutual fund vs its benchmark."""
    aligned = _align_nav_series(fund_nav_df, benchmark_nav_df)
    if len(aligned) < 30:
        raise ValueError(f"Insufficient aligned NAV history ({len(aligned)} days) for {scheme_name}")

    as_of_date = aligned["date"].iloc[-1].strftime("%Y-%m-%d")
    fund_age_years = round(
        (fund_nav_df["date"].iloc[-1] - fund_nav_df["date"].iloc[0]).days / 365.25,
        2,
    )
    latest_nav = round(float(fund_nav_df["nav"].iloc[-1]), 4)

    # 1. Trailing returns
    horizons = [("1Y", 1.0), ("3Y", 3.0), ("5Y", 5.0), ("7Y", 7.0), ("10Y", 10.0)]
    trailing: dict[str, dict[str, float | None]] = {}
    for label, yrs in horizons:
        f_r = _compute_trailing_cagr(aligned, "fund_nav", yrs)
        b_r = _compute_trailing_cagr(aligned, "bench_nav", yrs)
        spread = round(f_r - b_r, 2) if (f_r is not None and b_r is not None) else None
        trailing[label] = {
            "fund_cagr_pct": f_r,
            "benchmark_cagr_pct": b_r,
            "excess_cagr_pct": spread,
        }

    # 2. Rolling return distributions (1Y, 3Y, 5Y)
    rolling_stats: dict[str, RollingWindowStats] = {}
    rolled_3y_df: pd.DataFrame | None = None
    rolled_1y_df: pd.DataFrame | None = None

    for w_yr in (1, 3, 5):
        st, r_df = _compute_rolling_window(aligned, w_yr)
        if st is not None:
            rolling_stats[f"{w_yr}Y"] = st
        if w_yr == 3 and r_df is not None:
            rolled_3y_df = r_df
        elif w_yr == 1 and r_df is not None:
            rolled_1y_df = r_df

    # 3. Risk & Relative metrics
    risk_metrics, window_df = _compute_risk_and_relative_metrics(aligned)

    # 4. Downsampled chart series for frontend rendering (monthly points)
    chart_rolling_3y: list[dict[str, Any]] = []
    source_roll_df = rolled_3y_df if rolled_3y_df is not None else rolled_1y_df
    if source_roll_df is not None and not source_roll_df.empty:
        sampled = (
            source_roll_df.set_index("date")[["fund_cagr", "bench_cagr"]]
            .resample("ME")
            .last()
            .dropna()
            .tail(60)
        )
        for dt, row in sampled.iterrows():
            chart_rolling_3y.append(
                {
                    "date": dt.strftime("%Y-%m"),
                    "fund_rolling_cagr": round(float(row["fund_cagr"]), 2),
                    "benchmark_rolling_cagr": round(float(row["bench_cagr"]), 2),
                }
            )

    chart_drawdown: list[dict[str, Any]] = []
    sampled_dd = (
        window_df.set_index("date")[["fund_dd_pct", "bench_dd_pct"]]
        .resample("ME")
        .min()
        .dropna()
    )
    for dt, row in sampled_dd.iterrows():
        chart_drawdown.append(
            {
                "date": dt.strftime("%Y-%m"),
                "fund_drawdown_pct": round(float(row["fund_dd_pct"]), 2),
                "benchmark_drawdown_pct": round(float(row["bench_dd_pct"]), 2),
            }
        )

    # Rebased ₹10,000 growth chart over window_df
    chart_nav_rebased: list[dict[str, Any]] = []
    sampled_nav = (
        window_df.set_index("date")[["fund_nav", "bench_nav"]]
        .resample("ME")
        .last()
        .dropna()
    )
    if not sampled_nav.empty:
        f0 = float(sampled_nav["fund_nav"].iloc[0])
        b0 = float(sampled_nav["bench_nav"].iloc[0])
        for dt, row in sampled_nav.iterrows():
            chart_nav_rebased.append(
                {
                    "date": dt.strftime("%Y-%m"),
                    "fund_value_10k": round(10000.0 * float(row["fund_nav"]) / f0, 0),
                    "benchmark_value_10k": round(10000.0 * float(row["bench_nav"]) / b0, 0),
                }
            )

    return FundQuantReport(
        scheme_code=scheme_code,
        scheme_name=scheme_name,
        benchmark_name=benchmark_name,
        as_of_date=as_of_date,
        fund_age_years=fund_age_years,
        latest_nav=latest_nav,
        trailing_returns_cagr_pct=trailing,
        rolling_returns=rolling_stats,
        risk_metrics=risk_metrics,
        chart_rolling_3y=chart_rolling_3y,
        chart_drawdown=chart_drawdown,
        chart_nav_rebased=chart_nav_rebased,
    )

