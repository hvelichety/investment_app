"""
Weekly market section of the fact pack.

Fundamentals change once a quarter; what moves week to week is the share
price, the multiples it implies, and the gap to peers (SPCX vs TSLA for the
merger thesis). This renders those as fact-pack lines so the commentary
agent can quote them verbatim, all computed here from daily closes.
"""

from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from . import metrics
from .factpack import _money, _pct
from .fundamentals import Fundamentals

MARKET_SOURCE = "market_data"


def _close_on_or_before(prices: Sequence[Tuple[str, float]], day: str) -> Optional[Tuple[str, float]]:
    earlier = [p for p in prices if p[0] <= day]
    return earlier[-1] if earlier else None


def _change(now: float, then: Optional[Tuple[str, float]]) -> Optional[float]:
    return None if then is None or not then[1] else (now / then[1] - 1) * 100


def _shares(m: float) -> str:
    return f"{m:,.1f}M" if m < 100 else f"{m:,.0f}M"


def _x(r: Optional[float]) -> str:
    return "n/a" if r is None else f"{r:.1f}x"


def weekly_section(fund: Optional[Fundamentals], prices: List[Tuple[str, float]],
                   peers: Optional[Dict[str, Tuple[float, float]]] = None,
                   source_note: str = "Yahoo Finance daily closes",
                   ticker: Optional[str] = None, extra_lines: Optional[List[str]] = None,
                   shares_m: Optional[float] = None) -> str:
    """Price moves and valuation vs a week earlier.

    prices: (YYYY-MM-DD, close) oldest first. peers: ticker -> (close on the
    same day, shares outstanding in millions). Without sourced fundamentals
    (fund=None) there are no multiples, and the peer comparison uses
    shares_m (market data) for this ticker's market cap. extra_lines (e.g.
    relative performance) are added after the price lines.
    """
    ticker = ticker or fund.ticker
    prices = sorted(prices)
    last_day, close = prices[-1]
    today = date.fromisoformat(last_day)
    week = _close_on_or_before(prices, (today - timedelta(days=7)).isoformat())
    month = _close_on_or_before(prices, (today - timedelta(days=28)).isoformat())
    year = [c for d, c in prices if d > (today - timedelta(days=365)).isoformat()]

    lines = [
        f"## Week ending {last_day} [{MARKET_SOURCE}]",
        "",
        f"Market data: {source_note}."
        + (" Fundamentals above are unchanged unless a release came out this week." if fund else ""),
        "",
        f"- {ticker} close: ${close:,.2f}",
        f"- 1-week change: {_pct(_change(close, week))}" + (f" (from ${week[1]:,.2f} on {week[0]})" if week else ""),
        f"- 4-week change: {_pct(_change(close, month))}" + (f" (from ${month[1]:,.2f} on {month[0]})" if month else ""),
        f"- 52-week range: ${min(year):,.2f} – ${max(year):,.2f} ({len(year)} trading days in data)",
    ]

    lines += extra_lines or []

    own_cap = close * shares_m if shares_m else None
    if fund is not None:
        # The week-earlier multiple uses today's fundamentals, so the change is
        # the price move alone and not mixed with a release during the week
        now = metrics.valuation(fund, close, last_day)
        then = metrics.valuation(fund, week[1], last_day) if week else None
        note = " at the same fundamentals" if then else ""
        lines += [
            f"- EV / TTM revenue: {_x(now.ev_to_ttm_revenue)}"
            + (f" (a week earlier{note}: {_x(then.ev_to_ttm_revenue)})" if then else ""),
            f"- EV / annualized run-rate revenue: {_x(now.ev_to_run_rate_revenue)}"
            + (f" (a week earlier{note}: {_x(then.ev_to_run_rate_revenue)})" if then else ""),
        ]
        own_cap = now.market_cap
    elif own_cap:
        lines.append(f"- {ticker} market cap: {_money(own_cap)} ({_shares(shares_m)} shares)")

    for peer, (peer_close, peer_shares_m) in (peers or {}).items():
        peer_cap = peer_close * peer_shares_m
        lines.append(f"- {peer} close: ${peer_close:,.2f}; market cap {_money(peer_cap)} ({_shares(peer_shares_m)} shares)")
        if own_cap:
            ratio = own_cap / peer_cap
            lines.append(f"- {ticker} market cap vs {peer}: {_money(own_cap)} vs {_money(peer_cap)}, "
                         f"{ratio:.2f}x ({abs(ratio - 1) * 100:.1f}% {'premium' if ratio >= 1 else 'discount'})")

    lines.append("")
    return "\n".join(lines)
