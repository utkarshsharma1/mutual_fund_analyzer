"""Live SEBI Benchmark Index resolver and time-series fetcher.

Combines Total Return Index (TRI) mutual fund proxies on mfapi.in (which include reinvested dividends
per SEBI TRI standards) with Yahoo Finance index histories (^NSEI, ^CRSLDX) for extended history.
"""

from __future__ import annotations

from dataclasses import dataclass
import httpx
import pandas as pd

from app.config import settings
from app.scrapers.mfapi_live import InMemoryTTLCache, fetch_scheme_nav_live

_benchmark_cache = InMemoryTTLCache(ttl_seconds=settings.cache_ttl_seconds)


@dataclass
class BenchmarkSeries:
    """In-memory benchmark time series aligned for alpha/beta/rolling comparisons."""

    benchmark_name: str
    sebi_category: str
    yfinance_ticker: str
    tri_proxy_scheme_code: int
    df: pd.DataFrame  # columns: ['date', 'nav']


# Mapping of SEBI category keywords to (Benchmark Name, Yahoo Ticker, TRI Index Fund AMFI Code)
CATEGORY_BENCHMARK_MAP: list[tuple[list[str], str, str, int]] = [
    (
        ["small cap", "small-cap", "smallcap"],
        "Nifty Smallcap 250 TRI",
        "^CRSLDX",
        147623,  # Motilal Oswal Nifty Smallcap 250 Index Fund - Direct Growth
    ),
    (
        ["mid cap", "mid-cap", "midcap"],
        "Nifty Midcap 150 TRI",
        "^CRSLDX",
        147622,  # Motilal Oswal Nifty Midcap 150 Index Fund - Direct Growth
    ),
    (
        ["large & mid", "large and mid"],
        "Nifty LargeMidcap 250 TRI",
        "^CRSLDX",
        147625,  # Motilal Oswal Nifty 500 Index Fund - Direct Growth
    ),
    (
        ["large cap", "large-cap", "bluechip", "nifty 50", "sensex"],
        "Nifty 50 TRI",
        "^NSEI",
        120716,  # UTI Nifty 50 Index Fund - Direct Growth (long history since 2013)
    ),
    (
        ["flexi cap", "flexicap", "multi cap", "multicap", "elss", "tax", "value", "contra", "focused", "dividend yield"],
        "Nifty 500 TRI",
        "^CRSLDX",
        120716,  # Fallback long-history TRI backbone + spliced Nifty 500 TRI (147625)
    ),
    (
        ["balanced", "aggressive hybrid", "dynamic asset", "hybrid", "multi asset", "arbitrage", "equity savings"],
        "CRISIL Hybrid 35+65 / Nifty 50 Hybrid Composite",
        "^NSEI",
        120716,
    ),
]


def resolve_benchmark_for_category(sebi_category: str, scheme_name: str = "") -> tuple[str, str, int]:
    """Return (benchmark_name, yfinance_ticker, tri_proxy_scheme_code) for a given SEBI category."""
    combined = f"{sebi_category} {scheme_name}".lower()
    for keywords, b_name, yf_ticker, proxy_code in CATEGORY_BENCHMARK_MAP:
        if any(kw in combined for kw in keywords):
            return b_name, yf_ticker, proxy_code
    return "Nifty 500 TRI", "^CRSLDX", 120716


async def _fetch_yahoo_chart_series(ticker: str, range_str: str = "10y") -> pd.DataFrame | None:
    """Fetch daily close series directly from Yahoo Finance v8 chart endpoint via httpx."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"range": range_str, "interval": "1d"}
    try:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout_seconds,
            headers={"User-Agent": settings.user_agent},
            follow_redirects=True,
        ) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return None
            data = resp.json()
            result = data["chart"]["result"][0]
            timestamps = result["timestamp"]
            closes = result["indicators"]["quote"][0]["close"]
            rows = []
            for ts, close in zip(timestamps, closes):
                if close is not None and close > 0:
                    dt = pd.to_datetime(ts, unit="s").tz_localize(None).normalize()
                    rows.append((dt, float(close)))
            if not rows:
                return None
            df = pd.DataFrame(rows, columns=["date", "nav"])
            return df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    except Exception:
        return None


async def fetch_benchmark_live(sebi_category: str, scheme_name: str = "") -> BenchmarkSeries:
    """Fetch live daily benchmark time series for a mutual fund's SEBI category.

    Uses the TRI Index Fund proxy from mfapi.in (which includes dividend reinvestment)
    and splices earlier history from UTI Nifty 50 Index (120716) or Yahoo Finance so 5Y+ rolling
    windows are always available.
    """
    b_name, yf_ticker, proxy_code = resolve_benchmark_for_category(sebi_category, scheme_name)
    cache_key = f"bench:{b_name}:{proxy_code}"
    cached = _benchmark_cache.get(cache_key)
    if cached is not None:
        return cached

    primary_df: pd.DataFrame | None = None
    try:
        # If Nifty 500 TRI, try Motilal Oswal Nifty 500 Index first (since 2019), spliced with 120716 for pre-2019
        target_code = 147625 if b_name == "Nifty 500 TRI" else proxy_code
        proxy_nav = await fetch_scheme_nav_live(target_code)
        primary_df = proxy_nav.nav_df.copy()
    except Exception:
        primary_df = None

    # Fetch long-history backbone (UTI Nifty 50 Index Direct Growth since Jan 2013 or Yahoo Finance)
    backbone_df: pd.DataFrame | None = None
    if primary_df is None or (primary_df["date"].max() - primary_df["date"].min()).days < 365 * 6:
        try:
            backbone_nav = await fetch_scheme_nav_live(120716)
            backbone_df = backbone_nav.nav_df.copy()
        except Exception:
            backbone_df = await _fetch_yahoo_chart_series(yf_ticker, range_str="10y")

    if primary_df is not None and backbone_df is not None and not primary_df.empty and not backbone_df.empty:
        first_primary_date = primary_df["date"].iloc[0]
        first_primary_val = float(primary_df["nav"].iloc[0])
        earlier = backbone_df[backbone_df["date"] <= first_primary_date].copy()
        if len(earlier) > 1:
            scale = first_primary_val / float(earlier["nav"].iloc[-1])
            earlier["nav"] = earlier["nav"] * scale
            merged = pd.concat([earlier.iloc[:-1], primary_df], ignore_index=True)
            final_df = merged.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
        else:
            final_df = primary_df
    elif primary_df is not None and not primary_df.empty:
        final_df = primary_df
    elif backbone_df is not None and not backbone_df.empty:
        final_df = backbone_df
    else:
        raise RuntimeError(f"Unable to fetch benchmark data for {b_name}")

    series = BenchmarkSeries(
        benchmark_name=b_name,
        sebi_category=sebi_category,
        yfinance_ticker=yf_ticker,
        tri_proxy_scheme_code=proxy_code,
        df=final_df,
    )
    _benchmark_cache.set(cache_key, series)
    return series

