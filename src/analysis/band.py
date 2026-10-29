"""
Valuation band and relative performance, the channel's core price tools.

Band: analyst projection range × the multiple range set in the ticker's
playbook (docs/METHODOLOGY.md §2). Where the price sits in the band is
reported as a position (0% = low end, 100% = high end) and a zone. The
estimates are third-party (‡); everything else is computed here.

Relative performance: the stock vs benchmark indices since a decision date
(§4), in the channel's "+16.2 pts (RH +14.9%, S&P -1.3%)" form.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .factpack import _money, _pct

PERIOD_LABELS = {"0q": "current quarter", "+1q": "next quarter",
                 "0y": "current fiscal year", "+1y": "next fiscal year"}
BENCHMARK_LABELS = {"^GSPC": "S&P 500", "^IXIC": "Nasdaq", "^DJI": "Dow"}


@dataclass
class Band:
    period: str
    basis: str                 # "eps" (price = EPS × P/E) or "revenue" (EV / revenue)
    estimate_low: float
    estimate_avg: float
    estimate_high: float
    analysts: Optional[int]
    multiple_low: float
    multiple_high: float
    low: float                 # share price at low estimate × low multiple
    mid: float                 # average estimate × midpoint multiple
    high: float                # high estimate × high multiple
    consensus_low: float       # average estimate × low multiple
    consensus_high: float      # average estimate × high multiple

    def position(self, price: float) -> float:
        """0 at the low end, 100 at the high end; can fall outside 0..100"""
        return (price - self.low) / (self.high - self.low) * 100


def _to_price(value: float, basis: str, net_cash_m: Optional[float], shares_m: Optional[float]) -> float:
    if basis == "eps":
        return value
    # Revenue basis: value is an enterprise value in $M; convert to a share price
    return (value + net_cash_m) / shares_m


def valuation_band(estimate: Dict[str, float], period: str, basis: str, multiple_low: float, multiple_high: float,
                   net_cash_m: Optional[float] = None, shares_m: Optional[float] = None) -> Band:
    """estimate: {"low", "avg", "high", optional "analysts"}; revenue in $M for the revenue basis"""
    if basis == "revenue" and (net_cash_m is None or not shares_m):
        raise ValueError("Revenue-based band needs net cash and share count")
    mid_multiple = (multiple_low + multiple_high) / 2

    def price(est, mult):
        return _to_price(est * mult, basis, net_cash_m, shares_m)
    return Band(
        period=period, basis=basis,
        estimate_low=estimate["low"], estimate_avg=estimate["avg"], estimate_high=estimate["high"],
        analysts=estimate.get("analysts"),
        multiple_low=multiple_low, multiple_high=multiple_high,
        low=price(estimate["low"], multiple_low),
        mid=price(estimate["avg"], mid_multiple),
        high=price(estimate["high"], multiple_high),
        consensus_low=price(estimate["avg"], multiple_low),
        consensus_high=price(estimate["avg"], multiple_high),
    )


def zone(position: float, low_zone: float = 25, high_zone: float = 75) -> str:
    if position < 0:
        return "below the band"
    if position > 100:
        return "above the band"
    if position <= low_zone:
        return "near the low end"
    if position >= high_zone:
        return "near the high end"
    return "mid band"


def band_lines(bands: List[Band], price: float, source_key: str, zones: Tuple[float, float] = (25, 75)) -> List[str]:
    lines = [f"## Valuation band [{source_key}]", "",
             "Analyst estimates are third-party (‡); multiples come from the playbook. "
             "Position: 0% = low end of the band, 100% = high end.", ""]
    for b in bands:
        if b.basis == "eps":
            est = f"EPS ${b.estimate_low:,.2f} – ${b.estimate_high:,.2f}‡ (avg ${b.estimate_avg:,.2f}‡"
            mult = f"{b.multiple_low:g}x – {b.multiple_high:g}x P/E"
        else:
            est = (f"revenue {_money(b.estimate_low)} – {_money(b.estimate_high)}‡ "
                   f"(avg {_money(b.estimate_avg)}‡")
            mult = f"{b.multiple_low:g}x – {b.multiple_high:g}x EV / revenue"
        est += f", {b.analysts} analysts)" if b.analysts else ")"
        pos = b.position(price)
        lines += [
            f"- {PERIOD_LABELS.get(b.period, b.period)}: {est} × {mult}",
            f"  - Band: ${b.low:,.2f} – ${b.high:,.2f} (mid ${b.mid:,.2f}); "
            f"on the average estimate: ${b.consensus_low:,.2f} – ${b.consensus_high:,.2f}",
            f"  - Price ${price:,.2f} sits at {pos:.0f}% of the band: {zone(pos, *zones)}",
        ]
    lines.append("")
    return lines


def _close_on_or_before(prices: Sequence[Tuple[str, float]], day: str):
    earlier = [p for p in prices if p[0] <= day]
    return earlier[-1] if earlier else None


def relative_lines(ticker: str, prices: Sequence[Tuple[str, float]],
                   benchmarks: Dict[str, Sequence[Tuple[str, float]]], since: str) -> List[str]:
    """Return since `since` close vs each benchmark, in percentage points"""
    start = _close_on_or_before(sorted(prices), since)
    if start is None:
        return []
    end = sorted(prices)[-1]
    own = (end[1] / start[1] - 1) * 100
    lines = [f"- Since {start[0]} close ({ticker} ${start[1]:,.2f} → ${end[1]:,.2f} on {end[0]}):"]
    for symbol, series in benchmarks.items():
        series = sorted(series)
        b_start, b_end = _close_on_or_before(series, start[0]), _close_on_or_before(series, end[0])
        if not b_start or not b_end:
            continue
        theirs = (b_end[1] / b_start[1] - 1) * 100
        name = BENCHMARK_LABELS.get(symbol, symbol)
        lines.append(f"  - vs {name}: {own - theirs:+.1f} pts ({ticker} {_pct(own)}, {name} {_pct(theirs)})")
    return lines
