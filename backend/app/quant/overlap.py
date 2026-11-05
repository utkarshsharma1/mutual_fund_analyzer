"""On-the-fly Portfolio Holdings & Sector Overlap Calculator for Indian Mutual Funds."""

from __future__ import annotations

import re
from typing import Any

from app.scrapers.fund_web_scraper import ScrapedFundFundamentals


def _normalize_company_key(name: str) -> str:
    """Normalize company name for cross-fund holding matching."""
    s = name.lower()
    s = re.sub(r"\b(ltd|limited|india|industries|corp|corporation|co|pvt|inc|the)\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def compute_portfolio_overlap(
    funds: list[ScrapedFundFundamentals],
) -> dict[str, Any]:
    """Compute pairwise stock weight overlap matrix, common stocks, and aggregate look-through exposure."""
    if len(funds) < 2:
        return {"error": "At least 2 funds are required to compute portfolio overlap."}

    fund_maps: list[dict[str, tuple[str, float, str]]] = []
    for f in funds:
        cmap: dict[str, tuple[str, float, str]] = {}
        for h in f.top_holdings:
            key = (h.isin or "").strip().upper() or _normalize_company_key(h.company_name)
            if not key:
                continue
            prev = cmap.get(key)
            if prev:
                cmap[key] = (prev[0], round(prev[1] + h.weight_pct, 2), prev[2])
            else:
                cmap[key] = (h.company_name, round(h.weight_pct, 2), h.sector)
        fund_maps.append(cmap)

    n = len(funds)
    pairwise_matrix: list[dict[str, Any]] = []

    for i in range(n):
        for j in range(i + 1, n):
            map_a = fund_maps[i]
            map_b = fund_maps[j]
            common_keys = set(map_a.keys()) & set(map_b.keys())

            weight_overlap = 0.0
            common_stocks: list[dict[str, Any]] = []
            for k in common_keys:
                name_a, wt_a, sec_a = map_a[k]
                _, wt_b, _ = map_b[k]
                ov = min(wt_a, wt_b)
                weight_overlap += ov
                common_stocks.append(
                    {
                        "company_name": name_a,
                        "sector": sec_a,
                        "weight_fund_a_pct": wt_a,
                        "weight_fund_b_pct": wt_b,
                        "overlap_weight_pct": round(ov, 2),
                    }
                )

            common_stocks.sort(key=lambda x: x["overlap_weight_pct"], reverse=True)
            weight_overlap = round(weight_overlap, 2)

            if weight_overlap >= 45.0:
                diagnosis = "High Redundancy — Holding both adds minimal diversification."
            elif weight_overlap >= 25.0:
                diagnosis = "Moderate Overlap — Acceptable if funds follow distinct market-cap or style tilts."
            else:
                diagnosis = "Low Overlap — Strong complementary diversification."

            pairwise_matrix.append(
                {
                    "fund_a": funds[i].scheme_name,
                    "fund_b": funds[j].scheme_name,
                    "weight_overlap_pct": weight_overlap,
                    "common_stocks_count": len(common_stocks),
                    "diagnosis": diagnosis,
                    "top_overlapping_stocks": common_stocks[:10],
                }
            )

    # Equal-weighted aggregate look-through portfolio
    equal_wt = 1.0 / n
    combined_stocks: dict[str, dict[str, Any]] = {}
    combined_sectors: dict[str, float] = {}

    for idx, cmap in enumerate(fund_maps):
        for k, (cname, wt, sec) in cmap.items():
            eff_wt = wt * equal_wt
            if k not in combined_stocks:
                combined_stocks[k] = {
                    "company_name": cname,
                    "sector": sec,
                    "effective_portfolio_weight_pct": 0.0,
                    "held_by_funds_count": 0,
                }
            combined_stocks[k]["effective_portfolio_weight_pct"] = round(
                combined_stocks[k]["effective_portfolio_weight_pct"] + eff_wt, 2
            )
            combined_stocks[k]["held_by_funds_count"] += 1
            combined_sectors[sec] = round(combined_sectors.get(sec, 0.0) + eff_wt, 2)

    top_lookthrough = sorted(
        combined_stocks.values(),
        key=lambda x: x["effective_portfolio_weight_pct"],
        reverse=True,
    )[:15]
    top_sectors = dict(sorted(combined_sectors.items(), key=lambda kv: kv[1], reverse=True)[:10])

    return {
        "funds_analyzed": [f.scheme_name for f in funds],
        "pairwise_overlap": pairwise_matrix,
        "aggregate_top_lookthrough_stocks": top_lookthrough,
        "aggregate_sector_exposure_pct": top_sectors,
    }

