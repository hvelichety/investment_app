"""
Fact pack: the only numbers the analyst agent is allowed to use.

Renders sourced fundamentals and the deterministic metrics computed from
them as Markdown. Every figure is tagged with its source key; derived
figures are marked † and third-party estimates ‡ so the memo (and the
reviewer) can tell reported numbers from computed or outside ones.
"""

from typing import List, Optional

from . import metrics
from .fundamentals import Fact, Fundamentals

SEGMENT_LABELS = {"space": "Space", "connectivity": "Connectivity (Starlink)", "ai": "AI / Super Intelligence"}
METRIC_LABELS = {
    "revenue": "Revenue",
    "operating_income": "Operating income",
    "adj_ebitda": "Adjusted EBITDA",
    "capex": "Capex",
}
KPI_LABELS = {
    "starlink_subscribers_m": "Starlink subscribers (M, period end)",
    "starlink_arpu_usd": "Starlink consumer ARPU ($/month)",
    "launches_total": "Launches, total",
    "launches_customer": "Launches, customer",
    "launches_internal": "Launches, internal",
    "mass_to_orbit_t": "Mass to orbit (t)",
    "compute_gw": "Nameplate compute (GW)",
}


def _plain(value: float) -> str:
    return f"{value:,.1f}".rstrip("0").rstrip(".")


# Units written into the figure so a memo can quote it verbatim ("13.6M")
KPI_FORMATS = {
    "starlink_subscribers_m": lambda v: f"{v:.1f}M",
    "starlink_arpu_usd": lambda v: f"${_plain(v)}",
    "compute_gw": lambda v: f"{v:.1f} GW",
}


def _money(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    sign = "-" if value < 0 else ""
    v = abs(value)
    if v >= 1_000_000:
        return f"{sign}${v / 1_000_000:,.2f}T"
    return f"{sign}${v / 1000:,.2f}B" if v >= 1000 else f"{sign}${v:,.0f}M"


def _pct(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:+.1f}%"


def _ratio(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:.1f}%"


def _cell(fact: Optional[Fact], fmt=_money) -> str:
    if fact is None:
        return "n/a"
    return fmt(fact.value) + ("†" if fact.derived else "")


def _segment_label(item: str) -> str:
    return "Total" if item == "total" else SEGMENT_LABELS.get(item, item)


def build_factpack(fund: Fundamentals, price: Optional[float] = None, price_date: Optional[str] = None,
                   quarters: int = 5, market_section: Optional[str] = None) -> str:
    qs = fund.quarters()[-quarters:]
    latest = qs[-1]
    lines: List[str] = [
        f"# {fund.company} ({fund.ticker}) fact pack",
        "",
        f"Latest reported quarter: **{latest}**. Units: USD. "
        "† = derived from company totals (formula in the appendix); ‡ = third-party estimate, not company data.",
        "",
    ]

    for metric, label in METRIC_LABELS.items():
        lines += [f"## {label} by segment", "", "| Segment | " + " | ".join(qs) + " |",
                  "|---|" + "---|" * len(qs)]
        for item in fund.segments + ["total"]:
            row = [_cell(fund.get(q, metric, item)) for q in qs]
            lines.append(f"| {_segment_label(item)} | " + " | ".join(row) + " |")
        lines.append("")

    lines += [f"## Growth, margins and mix ({latest})", "",
              "| Segment | Revenue YoY | Revenue QoQ | Mix | Op. margin | Adj. EBITDA margin | Capex / revenue |",
              "|---|---|---|---|---|---|---|"]
    shares = metrics.mix(fund, latest)
    for item in fund.segments + ["total"]:
        lines.append(
            f"| {_segment_label(item)} "
            f"| {_pct(metrics.growth(fund, latest, 'revenue', item, 4))} "
            f"| {_pct(metrics.growth(fund, latest, 'revenue', item, 1))} "
            f"| {'100%' if item == 'total' else (f'{shares[item]:.0f}%' if item in shares else 'n/a')} "
            f"| {_ratio(metrics.margin(fund, latest, 'operating_income', item))} "
            f"| {_ratio(metrics.margin(fund, latest, 'adj_ebitda', item))} "
            f"| {_ratio(metrics.margin(fund, latest, 'capex', item))} |"
        )
    lines.append("")

    lines += ["## Operating KPIs", "", "| KPI | " + " | ".join(qs) + " |", "|---|" + "---|" * len(qs)]
    for kpi, label in KPI_LABELS.items():
        fmt = KPI_FORMATS.get(kpi, _plain)
        row = [_cell(fund.get(q, "kpi", kpi), fmt) for q in qs]
        if any(c != "n/a" for c in row):
            lines.append(f"| {label} | " + " | ".join(row) + " |")
    lines.append("")

    ttm_rev = metrics.trailing(fund, latest, "revenue")
    ttm_ebitda = metrics.trailing(fund, latest, "adj_ebitda")
    ttm_capex = metrics.trailing(fund, latest, "capex")
    lines += ["## Trailing twelve months", "",
              f"- TTM revenue (through {latest}): {_money(ttm_rev)}",
              f"- TTM adjusted EBITDA: {_money(ttm_ebitda)}",
              f"- TTM capex: {_money(ttm_capex)}",
              f"- Annualized run-rate revenue ({latest} × 4): {_money(fund.get(latest, 'revenue').value * 4)}",
              ""]

    bs_date = max(fund.balance_sheet) if fund.balance_sheet else None
    if bs_date:
        bs = fund.balance_sheet[bs_date]
        cash = bs["cash"].value + (bs["marketable_securities"].value if "marketable_securities" in bs else 0)
        debt = bs["debt_current"].value + bs["debt_noncurrent"].value
        lines += [f"## Balance sheet ({bs_date}) [{bs['cash'].sources[0]}]", "",
                  f"- Cash + marketable securities: {_money(cash)}",
                  f"- Debt and finance leases: {_money(debt)}",
                  f"- Net cash: {_money(cash - debt)}",
                  f"- Shares outstanding: {bs['shares_outstanding_m'].value:,.0f}M", ""]

    if price is not None and price_date:
        v = metrics.valuation(fund, price, price_date)
        def x(r):
            return "n/a" if r is None else f"{r:.1f}x"
        lines += [f"## Valuation at ${price:,.2f} ({price_date} close)", "",
                  f"- Market cap: {_money(v.market_cap)} ({v.shares_m:,.0f}M shares, balance sheet {v.balance_sheet_date})",
                  f"- Enterprise value: {_money(v.enterprise_value)} (net cash {_money(v.net_cash)})",
                  f"- Market cap / TTM revenue: {x(v.mcap_to_ttm_revenue)}",
                  f"- EV / TTM revenue: {x(v.ev_to_ttm_revenue)}",
                  f"- EV / annualized run-rate revenue: {x(v.ev_to_run_rate_revenue)}",
                  f"- EV / TTM adjusted EBITDA: {x(v.ev_to_ttm_adj_ebitda)}", ""]

    surprise = metrics.surprises(fund, latest)
    if surprise:
        est_source = next(iter(f for (p, _, _), f in fund.estimates.items() if p == latest)).sources[0]
        lines += [f"## {latest} actual vs estimate‡ [{est_source}]", "",
                  "| Segment | Actual | Estimate‡ | Surprise |", "|---|---|---|---|"]
        for s in surprise:
            lines.append(f"| {_segment_label(s.item)} | {_money(s.actual)} | {_money(s.estimate)} | {_pct(s.pct)} |")
        lines.append("")

    if market_section:
        lines.append(market_section)

    lines += ["## Sources", ""]
    for key, src in fund.sources.items():
        published = f", published {src['published']}" if src.get("published") else ""
        lines.append(f"- `{key}`: {src['title']} ({src.get('kind', 'source')}{published}) {src['url']}")
    if market_section:
        lines.append("- `market_data`: daily closing prices and share counts (market data, not company filings)")
    lines.append("")

    derived = sorted(
        ((p, m, i, f) for (p, m, i), f in fund.facts.items() if f.derived and p in qs),
        key=lambda t: (t[0], t[1], t[2]),
    )
    if derived:
        lines += ["## Appendix: derived figures†", ""]
        for period, metric, item, fact in derived:
            lines.append(f"- {period} {metric}/{item} = {fact.derived_from} [{', '.join(fact.sources)}]")
        lines.append("")

    return "\n".join(lines)
