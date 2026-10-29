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
    source: str = ""           # where the estimates came from, e.g. "stockanalysis.com, updated 2026-10-20"

    def position(self, price: float, on: str = "avg") -> float:
        """0 at the low end, 100 at the high end; can fall outside 0..100.

        on="avg": the band on the average estimate (the channel's charts);
        on="range": low estimate × low multiple to high estimate × high multiple.
        """
        low, high = (self.consensus_low, self.consensus_high) if on == "avg" else (self.low, self.high)
        return (price - low) / (high - low) * 100


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
        source=estimate.get("source", ""),
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


def band_lines(bands: List[Band], price: float, source_key: str, zones: Tuple[float, float] = (25, 75),
               on: str = "avg") -> List[str]:
    basis_note = ("the average analyst estimate × the multiple range" if on == "avg"
                  else "low estimate × low multiple to high estimate × high multiple")
    lines = [f"## Valuation band [{source_key}]", "",
             f"Band = {basis_note}. Analyst estimates are third-party (‡); multiples come from the playbook. "
             "Position: 0% = low end of the band, 100% = high end.", ""]
    for b in bands:
        analysts = f", {b.analysts} analysts" if b.analysts else ""
        analysts += f"; {b.source}" if b.source else ""
        if b.basis == "eps":
            est = (f"EPS avg ${b.estimate_avg:,.2f}‡ (range ${b.estimate_low:,.2f} – "
                   f"${b.estimate_high:,.2f}‡{analysts})")
            mult = f"{b.multiple_low:g}x – {b.multiple_high:g}x P/E"
        else:
            est = (f"revenue avg {_money(b.estimate_avg)}‡ (range {_money(b.estimate_low)} – "
                   f"{_money(b.estimate_high)}‡{analysts})")
            mult = f"{b.multiple_low:g}x – {b.multiple_high:g}x EV / revenue"
        main, alt = ((b.consensus_low, b.consensus_high), (b.low, b.high)) if on == "avg" \
            else ((b.low, b.high), (b.consensus_low, b.consensus_high))
        alt_label = "full estimate range" if on == "avg" else "on the average estimate"
        pos = b.position(price, on)
        lines += [
            f"- {PERIOD_LABELS.get(b.period, b.period)}: {est} × {mult}",
            f"  - Band: ${main[0]:,.2f} – ${main[1]:,.2f} ({alt_label}: ${alt[0]:,.2f} – ${alt[1]:,.2f})",
        ]
        if b.basis == "eps" and b.estimate_avg > 0:
            lines.append(f"  - Current P/E on the average estimate: {price / b.estimate_avg:.1f}x")
        lines.append(f"  - Price ${price:,.2f} sits at {pos:.0f}% of the band: {zone(pos, *zones)}")
    lines.append("")
    return lines


def acquisition_lines(target: str, target_close: float, target_diluted_shares_m: float,
                      acquirer: str, acquirer_cap_m: float, fractions=(0.25, 0.5),
                      cap_note: str = "") -> List[str]:
    """Reference prices if the acquirer pays the target's price plus a share of the valuation gap.

    gap = acquirer market value − target market cap, spread over the target's
    diluted shares; each line = target close + fraction × gap per share.
    """
    target_cap = target_close * target_diluted_shares_m
    gap = acquirer_cap_m - target_cap
    per_share = gap / target_diluted_shares_m
    lines = [
        f"- Acquisition reference ({acquirer} acquiring {target}): {acquirer} market value {_money(acquirer_cap_m)}"
        + (f" ({cap_note})" if cap_note else "")
        + f" vs {target} {_money(target_cap)} ({target_diluted_shares_m:,.0f}M diluted shares); "
        f"gap {_money(gap)}, ${per_share:,.2f} per {target} share",
    ]
    for f in fractions:
        lines.append(f"  - {f:.0%} line: ${target_close + f * per_share:,.2f} "
                     f"({target} close + {f:.0%} of the gap per share)")
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
