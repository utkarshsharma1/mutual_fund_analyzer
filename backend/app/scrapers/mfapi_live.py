"""Live AMFI scheme resolver and historical NAV fetcher via mfapi.in (stateless, in-memory TTL cache)."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
import pandas as pd

from app.config import settings

MFAPI_BASE_URL = "https://api.mfapi.in/mf"

# Common Indian MF aliases -> canonical search strings for mfapi.in
COMMON_ALIASES: dict[str, str] = {
    "ppfas": "Parag Parikh Flexi Cap",
    "parag parikh": "Parag Parikh Flexi Cap",
    "hdfc flexi": "HDFC Flexi Cap",
    "hdfc mid": "HDFC Mid-Cap Opportunities",
    "hdfc midcap": "HDFC Mid-Cap Opportunities",
    "nippon small": "Nippon India Small Cap",
    "sbi small": "SBI Small Cap",
    "sbi contra": "SBI Contra",
    "quant small": "Quant Small Cap",
    "quant mid": "Quant Mid Cap",
    "quant active": "Quant Active",
    "motilal mid": "Motilal Oswal Midcap",
    "motilal oswal midcap": "Motilal Oswal Midcap",
    "icici bluechip": "ICICI Prudential Bluechip",
    "icici value": "ICICI Prudential Value Discovery",
    "Mirae large": "Mirae Asset Large Cap",
    "uti nifty 50": "UTI Nifty 50 Index",
    "axis bluechip": "Axis Bluechip",
    "axis midcap": "Axis Midcap",
    "axis small": "Axis Small Cap",
    "kotak emerging": "Kotak Emerging Equity",
    "bandhan small": "Bandhan Small Cap",
    "tata small": "Tata Small Cap",
}


@dataclass
class SchemeNavData:
    """In-memory representation of a scheme's metadata and historical NAV series."""

    scheme_code: int
    scheme_name: str
    fund_house: str
    scheme_type: str
    scheme_category: str
    isin_growth: str | None
    nav_df: pd.DataFrame  # columns: ['date', 'nav'], sorted ascending by date
    latest_nav: float
    latest_nav_date: str
    inception_date: str
    total_trading_days: int
    extra_meta: dict[str, Any] = field(default_factory=dict)


class InMemoryTTLCache:
    """Lightweight thread-safe in-memory TTL cache requiring zero external database."""

    def __init__(self, ttl_seconds: int = 1800, maxsize: int = 256) -> None:
        self.ttl = ttl_seconds
        self.maxsize = maxsize
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if not item:
            return None
        expires_at, val = item
        if time.time() > expires_at:
            self._store.pop(key, None)
            return None
        return val

    def set(self, key: str, value: Any) -> None:
        if len(self._store) >= self.maxsize:
            oldest_key = min(self._store, key=lambda k: self._store[k][0])
            self._store.pop(oldest_key, None)
        self._store[key] = (time.time() + self.ttl, value)


_search_cache = InMemoryTTLCache(ttl_seconds=settings.cache_ttl_seconds)
_nav_cache = InMemoryTTLCache(ttl_seconds=settings.cache_ttl_seconds)


def _normalize_query(query: str) -> list[str]:
    """Produce candidate search queries for mfapi.in."""
    cleaned = re.sub(r"\s+", " ", query.strip())
    lower = cleaned.lower()

    candidates: list[str] = []
    for alias, target in COMMON_ALIASES.items():
        if alias.lower() in lower:
            candidates.append(target)

    # Strip noise words that sometimes break exact substring search on mfapi.in
    stripped = re.sub(
        r"\b(direct|regular|growth|plan|option|fund|scheme|idcw|dividend)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    stripped = re.sub(r"\s+", " ", stripped).strip()
    if stripped and stripped not in candidates:
        candidates.append(stripped)
    if cleaned not in candidates:
        candidates.append(cleaned)

    # Also add first 2-3 significant words as fallback
    words = [w for w in stripped.split() if len(w) > 2]
    if len(words) >= 2:
        short_q = " ".join(words[:3])
        if short_q not in candidates:
            candidates.append(short_q)

    return candidates


def score_scheme_match(scheme_name: str, original_query: str, prefer_direct_growth: bool = True) -> float:
    """Rank how well an AMFI scheme name matches the user's query.

    Strongly prefers 'Direct Plan' + 'Growth' unless the user explicitly asked for Regular or IDCW.
    """
    name_lower = scheme_name.lower()
    query_lower = original_query.lower()

    score = 0.0
    # Token overlap
    query_tokens = [
        t for t in re.split(r"[^a-z0-9]+", query_lower)
        if t and t not in {"fund", "scheme", "plan", "option", "the"}
    ]
    for token in query_tokens:
        if token in name_lower:
            score += 12.0

    wants_regular = "regular" in query_lower
    wants_idcw = any(w in query_lower for w in ("idcw", "dividend", "payout", "reinvestment"))

    if prefer_direct_growth and not wants_regular:
        if "direct" in name_lower:
            score += 30.0
        elif "regular" in name_lower:
            score -= 25.0

    if prefer_direct_growth and not wants_idcw:
        if "growth" in name_lower:
            score += 25.0
        if any(w in name_lower for w in ("idcw", "dividend", "payout", "bonus", "segregated", "unclaimed")):
            score -= 40.0

    # Penalize institutional / defunct / interval variants
    if any(w in name_lower for w in ("institutional", "segregated", "unclaimed", "bonus", "weekly", "daily", "monthly")):
        score -= 30.0

    # Shorter, cleaner names win ties
    score -= len(scheme_name) * 0.05
    return score


async def search_schemes_live(
    query: str,
    prefer_direct_growth: bool = True,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Search AMFI schemes live on mfapi.in and return ranked results."""
    cache_key = f"search:{query.lower().strip()}:{prefer_direct_growth}:{limit}"
    cached = _search_cache.get(cache_key)
    if cached is not None:
        return cached

    candidates = _normalize_query(query)
    seen_codes: set[int] = set()
    raw_results: list[dict[str, Any]] = []

    async with httpx.AsyncClient(
        timeout=settings.http_timeout_seconds,
        headers={"User-Agent": settings.user_agent},
        follow_redirects=True,
    ) as client:
        for cand in candidates:
            try:
                resp = await client.get(f"{MFAPI_BASE_URL}/search", params={"q": cand})
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        for item in data:
                            code = item.get("schemeCode")
                            name = item.get("schemeName")
                            if code and name and int(code) not in seen_codes:
                                seen_codes.add(int(code))
                                raw_results.append(
                                    {
                                        "scheme_code": int(code),
                                        "scheme_name": str(name).strip(),
                                        "match_score": round(
                                            score_scheme_match(str(name), query, prefer_direct_growth), 2
                                        ),
                                    }
                                )
                if len(raw_results) >= 15:
                    break
            except Exception:
                continue

    raw_results.sort(key=lambda x: x["match_score"], reverse=True)
    top_results = raw_results[:limit]
    if top_results:
        _search_cache.set(cache_key, top_results)
    return top_results


async def fetch_scheme_nav_live(scheme_code: int) -> SchemeNavData:
    """Fetch full historical daily NAV and metadata for an AMFI scheme code from mfapi.in."""
    cache_key = f"nav:{scheme_code}"
    cached = _nav_cache.get(cache_key)
    if cached is not None:
        return cached

    async with httpx.AsyncClient(
        timeout=settings.http_timeout_seconds,
        headers={"User-Agent": settings.user_agent},
        follow_redirects=True,
    ) as client:
        resp = await client.get(f"{MFAPI_BASE_URL}/{scheme_code}")
        resp.raise_for_status()
        payload = resp.json()

    meta = payload.get("meta", {}) or {}
    raw_data = payload.get("data", []) or []
    if not raw_data:
        raise ValueError(f"No historical NAV data returned for scheme_code={scheme_code}")

    records: list[tuple[pd.Timestamp, float]] = []
    for row in raw_data:
        try:
            dt = pd.to_datetime(row["date"], format="%d-%m-%Y", errors="coerce")
            nav_val = float(row["nav"])
            if pd.notna(dt) and nav_val > 0:
                records.append((dt, nav_val))
        except (KeyError, ValueError, TypeError):
            continue

    if not records:
        raise ValueError(f"Could not parse valid NAV entries for scheme_code={scheme_code}")

    df = pd.DataFrame(records, columns=["date", "nav"])
    df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)

    latest_row = df.iloc[-1]
    first_row = df.iloc[0]

    result = SchemeNavData(
        scheme_code=int(meta.get("scheme_code") or scheme_code),
        scheme_name=str(meta.get("scheme_name") or f"Scheme {scheme_code}"),
        fund_house=str(meta.get("fund_house") or "Unknown AMC"),
        scheme_type=str(meta.get("scheme_type") or "Open Ended Schemes"),
        scheme_category=str(meta.get("scheme_category") or "Equity Scheme"),
        isin_growth=meta.get("isin_growth"),
        nav_df=df,
        latest_nav=round(float(latest_row["nav"]), 4),
        latest_nav_date=latest_row["date"].strftime("%Y-%m-%d"),
        inception_date=first_row["date"].strftime("%Y-%m-%d"),
        total_trading_days=len(df),
        extra_meta=meta,
    )
    _nav_cache.set(cache_key, result)
    return result

