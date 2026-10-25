"""
Deterministic analysis on top of sourced fundamentals.

Every function returns plain numbers computed from Fact values; nothing
here is estimated or looked up elsewhere. Missing inputs give None rather
than a guess.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from .fundamentals import Fact, Fundamentals, previous_quarter


def _value(fact: Optional[Fact]) -> Optional[float]:
    return None if fact is None else fact.value


def growth(fund: Fundamentals, period: str, metric: str, item: str = "total", back: int = 4) -> Optional[float]:
    """Percent change vs `back` quarters earlier (4 = YoY, 1 = QoQ)"""
    now = _value(fund.get(period, metric, item))
    then = _value(fund.get(previous_quarter(period, back), metric, item))
    if now is None or then is None or then == 0:
        return None
    return (now / then - 1) * 100 if then > 0 else None


def margin(fund: Fundamentals, period: str, metric: str, item: str = "total") -> Optional[float]:
    """metric as a percent of revenue for the same segment and period"""
    num = _value(fund.get(period, metric, item))
    rev = _value(fund.get(period, "revenue", item))
    if num is None or not rev:
        return None
    return num / rev * 100


def mix(fund: Fundamentals, period: str) -> Dict[str, float]:
    """Share of total revenue per segment, in percent"""
    total = _value(fund.get(period, "revenue"))
    if not total:
        return {}
    shares = {}
    for segment in fund.segments:
        value = _value(fund.get(period, "revenue", segment))
        if value is not None:
            shares[segment] = value / total * 100
    return shares


def trailing(fund: Fundamentals, end: str, metric: str, item: str = "total", quarters: int = 4) -> Optional[float]:
    """Sum over the `quarters` quarters ending at `end` (TTM by default)"""
    values = [_value(fund.get(previous_quarter(end, k), metric, item)) for k in range(quarters)]
    if any(v is None for v in values):
        return None
    return sum(values)


def latest_balance_sheet(fund: Fundamentals, on_or_before: str) -> Optional[str]:
    dates = sorted(d for d in fund.balance_sheet if d <= on_or_before)
    return dates[-1] if dates else None


@dataclass
class Valuation:
    price: float
    price_date: str
    balance_sheet_date: Optional[str]
    shares_m: float
    net_cash: float
    market_cap: float
    enterprise_value: float
    ttm_end: str
    ttm_revenue: Optional[float]
    ttm_adj_ebitda: Optional[float]
    run_rate_revenue: Optional[float]
    mcap_to_ttm_revenue: Optional[float]
    ev_to_ttm_revenue: Optional[float]
    ev_to_run_rate_revenue: Optional[float]
    ev_to_ttm_adj_ebitda: Optional[float]


def valuation(
    fund: Fundamentals,
    price: float,
    price_date: str,
    shares_m: Optional[float] = None,
    net_cash: Optional[float] = None,
) -> Valuation:
    """Market cap, EV and revenue / EBITDA multiples at a given share price.

    Uses the latest balance sheet on or before `price_date` unless shares or
    net cash are given explicitly (e.g. a more recent 10-Q cover share count).
    """
    bs_date = latest_balance_sheet(fund, price_date)
    bs = fund.balance_sheet.get(bs_date, {}) if bs_date else {}
    if shares_m is None:
        shares_m = _value(bs.get("shares_outstanding_m"))
    if net_cash is None and bs:
        net_cash = (
            _value(bs.get("cash")) + (_value(bs.get("marketable_securities")) or 0)
            - _value(bs.get("debt_current")) - _value(bs.get("debt_noncurrent"))
        )
    if shares_m is None or net_cash is None:
        raise ValueError(f"No share count or balance sheet on or before {price_date}")

    # Latest quarter that had been reported by the price date
    quarters = [q for q in fund.quarters() if _reported_by(fund, q, price_date)]
    ttm_end = quarters[-1]

    market_cap = price * shares_m
    ev = market_cap - net_cash
    ttm_rev = trailing(fund, ttm_end, "revenue")
    ttm_ebitda = trailing(fund, ttm_end, "adj_ebitda")
    latest_rev = _value(fund.get(ttm_end, "revenue"))
    run_rate = latest_rev * 4 if latest_rev is not None else None

    def ratio(a, b):
        return a / b if a is not None and b else None

    return Valuation(
        price=price,
        price_date=price_date,
        balance_sheet_date=bs_date,
        shares_m=shares_m,
        net_cash=net_cash,
        market_cap=market_cap,
        enterprise_value=ev,
        ttm_end=ttm_end,
        ttm_revenue=ttm_rev,
        ttm_adj_ebitda=ttm_ebitda,
        run_rate_revenue=run_rate,
        mcap_to_ttm_revenue=ratio(market_cap, ttm_rev),
        ev_to_ttm_revenue=ratio(ev, ttm_rev),
        ev_to_run_rate_revenue=ratio(ev, run_rate),
        ev_to_ttm_adj_ebitda=ratio(ev, ttm_ebitda) if ttm_ebitda and ttm_ebitda > 0 else None,
    )


def _reported_by(fund: Fundamentals, quarter: str, date: str) -> bool:
    """Whether every document behind a quarter's revenue was public by `date`"""
    fact = fund.get(quarter, "revenue")
    published = [str(fund.sources[s].get("published", "")) for s in fact.sources]
    dated = [p for p in published if p]
    return not dated or max(dated) <= date


@dataclass
class Surprise:
    item: str
    actual: float
    estimate: float

    @property
    def pct(self) -> float:
        return (self.actual / self.estimate - 1) * 100


def surprises(fund: Fundamentals, period: str, metric: str = "revenue") -> List[Surprise]:
    """Actual vs third-party estimate for each item that has both"""
    result = []
    for item in fund.segments + ["total"]:
        est = fund.estimates.get((period, metric, item))
        actual = fund.get(period, metric, item)
        if est is not None and actual is not None and est.value:
            result.append(Surprise(item, actual.value, est.value))
    return result
