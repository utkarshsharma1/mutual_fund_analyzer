"""Tests for scheme query normalization and scheme matching logic."""

from __future__ import annotations

from app.scrapers.benchmark_live import resolve_benchmark_for_category
from app.scrapers.mfapi_live import score_scheme_match


def test_direct_growth_scheme_scoring_preference() -> None:
    """Ensure Direct Plan Growth always ranks above Regular Plan and IDCW variants."""
    query = "Parag Parikh Flexi Cap Fund"
    s_direct_growth = score_scheme_match("Parag Parikh Flexi Cap Fund - Direct Plan - Growth", query)
    s_reg_growth = score_scheme_match("Parag Parikh Flexi Cap Fund - Regular Plan - Growth", query)
    s_direct_idcw = score_scheme_match("Parag Parikh Flexi Cap Fund - Direct Plan - IDCW", query)

    assert s_direct_growth > s_reg_growth
    assert s_direct_growth > s_direct_idcw


def test_sebi_category_to_benchmark_mapping() -> None:
    """Verify SEBI categories resolve to their proper Nifty TRI benchmarks."""
    b_small, _, code_small = resolve_benchmark_for_category("Equity Scheme - Small Cap Fund")
    assert "Smallcap 250" in b_small
    assert code_small == 147623

    b_mid, _, code_mid = resolve_benchmark_for_category("Equity Scheme - Mid Cap Fund")
    assert "Midcap 150" in b_mid
    assert code_mid == 147622

    b_flexi, _, _ = resolve_benchmark_for_category("Equity Scheme - Flexi Cap Fund")
    assert "Nifty 500" in b_flexi

