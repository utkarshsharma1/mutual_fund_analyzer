"""Live Web & API Scraper for Indian Mutual Fund fundamentals, holdings, sector split, and peers.

Queries multiple live public sources in cascade:
1. Groww Mutual Fund Entity Search & Scheme Details JSON API / __NEXT_DATA__
2. Kuvera Public Scheme JSON API (by ISIN)
3. Direct HTML metadata extraction fallback
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any

from bs4 import BeautifulSoup
import httpx

from app.config import settings
from app.scrapers.mfapi_live import InMemoryTTLCache

_fundamentals_cache = InMemoryTTLCache(ttl_seconds=settings.cache_ttl_seconds)


@dataclass
class HoldingItem:
    """Single portfolio holding (stock, debt, or cash instrument)."""

    company_name: str
    weight_pct: float
    sector: str = "Diversified"
    asset_class: str = "Equity"
    isin: str | None = None


@dataclass
class ScrapedFundFundamentals:
    """Live-scraped fundamentals, portfolio holdings, and category metadata for a mutual fund."""

    scheme_name: str
    amc_name: str = ""
    sebi_category: str = ""
    expense_ratio_pct: float | None = None
    aum_crores: float | None = None
    exit_load: str | None = None
    fund_manager: str | None = None
    manager_tenure_years: float | None = None
    min_sip: float | None = None
    min_lumpsum: float | None = None
    turnover_ratio_pct: float | None = None
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    top_holdings: list[HoldingItem] = field(default_factory=list)
    sector_allocation: dict[str, float] = field(default_factory=dict)
    asset_allocation: dict[str, float] = field(default_factory=dict)
    category_avg_returns: dict[str, float] = field(default_factory=dict)
    peer_funds: list[dict[str, Any]] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)


def _clean_scheme_query_for_portal(scheme_name: str) -> str:
    """Clean AMFI verbose scheme name into a crisp portal search query."""
    cleaned = re.sub(
        r"\s*-\s*(direct|regular)\s*(plan)?.*$",
        "",
        scheme_name,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(direct|regular|growth|plan|option|idcw|dividend)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"[^\w\s&]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


async def _scrape_from_groww(
    client: httpx.AsyncClient,
    scheme_name: str,
    scheme_code: int | None = None,
) -> ScrapedFundFundamentals | None:
    """Search and scrape fund details & holdings from Groww's public MF endpoints."""
    clean_q = _clean_scheme_query_for_portal(scheme_name)
    search_url = "https://groww.in/v1/api/search/v1/entity"
    params = {
        "app": "false",
        "entity_type": "scheme",
        "page": "0",
        "q": clean_q,
        "size": "6",
    }

    search_id: str | None = None
    try:
        s_resp = await client.get(search_url, params=params)
        if s_resp.status_code == 200:
            content = s_resp.json().get("content", [])
            if content:
                # Prefer direct growth match or matching scheme_code
                best = content[0]
                for item in content:
                    title = str(item.get("title", "")).lower()
                    b_id = str(item.get("bse_scheme_code") or item.get("scheme_code") or "")
                    if scheme_code and b_id == str(scheme_code):
                        best = item
                        break
                    if "direct" in title and ("growth" in title or "idcw" not in title):
                        best = item
                        break
                search_id = best.get("search_id") or best.get("id")
    except Exception:
        search_id = None

    if not search_id:
        # Slug fallback from cleaned name
        slug = re.sub(r"[^a-z0-9]+", "-", clean_q.lower()).strip("-")
        search_id = f"{slug}-direct-growth"

    # Try v4 and v1 scheme detail JSON APIs on Groww
    detail_urls = [
        f"https://groww.in/v1/api/data/mf/web/v4/scheme/search/{search_id}",
        f"https://groww.in/v1/api/data/mf/web/v1/scheme/search/{search_id}",
    ]

    data: dict[str, Any] | None = None
    used_url = f"https://groww.in/mutual-funds/{search_id}"

    for d_url in detail_urls:
        try:
            d_resp = await client.get(d_url)
            if d_resp.status_code == 200:
                payload = d_resp.json()
                if isinstance(payload, dict) and (
                    payload.get("scheme_name") or payload.get("holdings") or payload.get("aum")
                ):
                    data = payload
                    break
        except Exception:
            continue

    # Fallback: fetch the HTML page and parse __NEXT_DATA__
    if data is None:
        try:
            html_resp = await client.get(used_url)
            if html_resp.status_code == 200:
                soup = BeautifulSoup(html_resp.text, "html.parser")
                next_script = soup.find("script", id="__NEXT_DATA__")
                if next_script and next_script.string:
                    next_json = json.loads(next_script.string)
                    page_props = next_json.get("props", {}).get("pageProps", {})
                    data = page_props.get("mfServerSideData") or page_props.get("schemeData") or page_props
        except Exception:
            data = None

    if not data or not isinstance(data, dict):
        return None

    return _parse_groww_payload(data, scheme_name, used_url)


def _parse_groww_payload(
    data: dict[str, Any],
    fallback_name: str,
    source_url: str,
) -> ScrapedFundFundamentals:
    """Parse Groww scheme JSON payload into ScrapedFundFundamentals."""
    exp_ratio = None
    if data.get("expense_ratio") is not None:
        try:
            exp_ratio = round(float(data["expense_ratio"]), 2)
        except (ValueError, TypeError):
            pass

    aum = None
    if data.get("aum") is not None:
        try:
            aum = round(float(data["aum"]), 2)
        except (ValueError, TypeError):
            pass

    # Fund manager & tenure
    manager_str = data.get("fund_manager")
    tenure_years = None
    manager_details = data.get("fund_manager_details") or []
    if isinstance(manager_details, list) and manager_details:
        names = []
        for m in manager_details:
            if isinstance(m, dict) and m.get("person_name"):
                names.append(str(m["person_name"]))
                date_from = m.get("date_from")
                if date_from and tenure_years is None:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(str(date_from).replace("Z", "")[:10])
                        tenure_years = round(max((datetime.now() - dt).days / 365.25, 0.5), 1)
                    except Exception:
                        pass
        if names:
            manager_str = ", ".join(names)

    # Holdings & sector aggregation
    raw_holdings = data.get("holdings") or []
    top_holdings: list[HoldingItem] = []
    sector_totals: dict[str, float] = {}
    asset_totals: dict[str, float] = {}

    for h in raw_holdings:
        if not isinstance(h, dict):
            continue
        comp = str(h.get("company_name") or h.get("instrument_name") or "").strip()
        try:
            wt = float(h.get("corpus_per") or h.get("pe_percentage") or h.get("weight") or 0.0)
        except (ValueError, TypeError):
            wt = 0.0
        if not comp or wt <= 0:
            continue
        sec = str(h.get("sector_name") or "Others").strip()
        nat = str(h.get("nature_name") or h.get("instrument_name") or "Equity").strip()
        top_holdings.append(
            HoldingItem(
                company_name=comp,
                weight_pct=round(wt, 2),
                sector=sec,
                asset_class=nat,
                isin=h.get("isin"),
            )
        )
        sector_totals[sec] = round(sector_totals.get(sec, 0.0) + wt, 2)
        asset_totals[nat] = round(asset_totals.get(nat, 0.0) + wt, 2)

    top_holdings.sort(key=lambda x: x.weight_pct, reverse=True)
    sorted_sectors = dict(sorted(sector_totals.items(), key=lambda kv: kv[1], reverse=True)[:10])

    # Category average returns & peer comparison
    cat_avg: dict[str, float] = {}
    return_stats = data.get("return_stats") or []
    if isinstance(return_stats, list):
        for stat in return_stats:
            if isinstance(stat, dict) and stat.get("cat_return3y") is not None:
                for k, label in [("cat_return1y", "1Y"), ("cat_return3y", "3Y"), ("cat_return5y", "5Y")]:
                    if stat.get(k) is not None:
                        try:
                            cat_avg[label] = round(float(stat[k]), 2)
                        except (ValueError, TypeError):
                            pass
                break

    peers: list[dict[str, Any]] = []
    raw_peers = data.get("peer_comparison") or data.get("similar_funds") or []
    if isinstance(raw_peers, list):
        for p in raw_peers[:6]:
            if isinstance(p, dict) and p.get("scheme_name"):
                peers.append(
                    {
                        "scheme_name": p.get("scheme_name"),
                        "scheme_code": p.get("scheme_code"),
                        "return_3y": p.get("return3y"),
                        "return_5y": p.get("return5y"),
                        "aum_crores": p.get("aum"),
                        "expense_ratio": p.get("expense_ratio"),
                    }
                )

    return ScrapedFundFundamentals(
        scheme_name=str(data.get("scheme_name") or fallback_name),
        amc_name=str(data.get("amc") or data.get("fund_house") or ""),
        sebi_category=str(data.get("sub_category") or data.get("category") or ""),
        expense_ratio_pct=exp_ratio,
        aum_crores=aum,
        exit_load=str(data.get("exit_load") or "Nil / Refer Scheme Information Document"),
        fund_manager=str(manager_str) if manager_str else None,
        manager_tenure_years=tenure_years,
        min_sip=_safe_float(data.get("min_sip_investment")),
        min_lumpsum=_safe_float(data.get("min_investment_amount")),
        turnover_ratio_pct=_safe_float(data.get("portfolio_turnover")),
        top_holdings=top_holdings[:25],
        sector_allocation=sorted_sectors,
        asset_allocation=asset_totals,
        category_avg_returns=cat_avg,
        peer_funds=peers,
        source_urls=[source_url],
    )


async def _scrape_from_kuvera_by_isin(
    client: httpx.AsyncClient,
    isin: str,
    scheme_name: str,
) -> ScrapedFundFundamentals | None:
    """Fallback live JSON fetch from Kuvera's public scheme API using the scheme's ISIN."""
    if not isin:
        return None
    url = f"https://api.kuvera.in/mf/api/v4/fund_schemes/{isin}.json"
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return None
        payload = resp.json()
        if isinstance(payload, list) and payload:
            item = payload[0]
        elif isinstance(payload, dict):
            item = payload
        else:
            return None

        return ScrapedFundFundamentals(
            scheme_name=str(item.get("name") or scheme_name),
            amc_name=str(item.get("fund_house") or ""),
            sebi_category=str(item.get("subcategory") or item.get("category") or ""),
            expense_ratio_pct=_safe_float(item.get("expense_ratio")),
            aum_crores=round(float(item["aum"]) / 10.0, 2) if _safe_float(item.get("aum")) else None,
            exit_load=str(item.get("exit_load") or ""),
            fund_manager=str(item.get("fund_manager") or "") or None,
            turnover_ratio_pct=_safe_float(item.get("portfolio_turnover")),
            source_urls=[f"https://kuvera.in/mutual-funds/scheme/{isin}"],
        )
    except Exception:
        return None


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return round(float(val), 2)
    except (ValueError, TypeError):
        return None


async def scrape_fund_fundamentals_live(
    scheme_name: str,
    scheme_code: int | None = None,
    isin_growth: str | None = None,
) -> ScrapedFundFundamentals:
    """Scrape live fund fundamentals, holdings, sector allocation, and peers across Indian portals."""
    cache_key = f"fund_meta:{scheme_code or scheme_name.lower()}"
    cached = _fundamentals_cache.get(cache_key)
    if cached is not None:
        return cached

    async with httpx.AsyncClient(
        timeout=settings.http_timeout_seconds,
        headers={"User-Agent": settings.user_agent, "Accept": "application/json, text/html"},
        follow_redirects=True,
    ) as client:
        groww_data = await _scrape_from_groww(client, scheme_name, scheme_code)
        kuvera_data = await _scrape_from_kuvera_by_isin(client, isin_growth or "", scheme_name)

    if groww_data and kuvera_data:
        # Enrich any missing fields in groww_data from kuvera_data
        if groww_data.expense_ratio_pct is None:
            groww_data.expense_ratio_pct = kuvera_data.expense_ratio_pct
        if groww_data.aum_crores is None:
            groww_data.aum_crores = kuvera_data.aum_crores
        if not groww_data.fund_manager:
            groww_data.fund_manager = kuvera_data.fund_manager
        if groww_data.turnover_ratio_pct is None:
            groww_data.turnover_ratio_pct = kuvera_data.turnover_ratio_pct
        groww_data.source_urls.extend(kuvera_data.source_urls)
        result = groww_data
    elif groww_data:
        result = groww_data
    elif kuvera_data:
        result = kuvera_data
    else:
        result = ScrapedFundFundamentals(scheme_name=scheme_name)

    _fundamentals_cache.set(cache_key, result)
    return result

