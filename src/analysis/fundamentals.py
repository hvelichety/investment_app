"""
Sourced quarterly fundamentals.

Loads data/fundamentals/<TICKER>.yaml, keeps every figure tied to the
document it came from, and derives quarters a company never printed on
their own (e.g. Q4 = FY - 9M). Derived figures carry the formula used.
Overlapping totals (segments vs total, H1 + Q3 vs 9M, ...) are cross-checked
so a typo in the data file fails loudly instead of flowing into analysis.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import yaml

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FUNDAMENTALS_DIR = os.path.join(ROOT_DIR, "data", "fundamentals")

# Statement lines broken down by segment (plus "total")
SEGMENTED_METRICS = ["revenue", "operating_income", "adj_ebitda", "capex"]
# KPIs that add up across quarters; the rest (subscribers, ARPU, compute)
# are point-in-time and never derived
FLOW_KPIS = {"launches_total", "launches_customer", "launches_internal", "mass_to_orbit_t"}

# Figures are printed rounded to $1M, so sums can drift by a unit per term
ROUNDING_TOLERANCE = 1.0


@dataclass
class Fact:
    value: float
    sources: List[str]
    derived_from: Optional[str] = None  # formula when not printed by the company

    @property
    def derived(self) -> bool:
        return self.derived_from is not None


@dataclass
class Fundamentals:
    ticker: str
    company: str
    segments: List[str]
    sources: Dict[str, dict]
    facts: Dict[Tuple[str, str, str], Fact] = field(default_factory=dict)
    balance_sheet: Dict[str, Dict[str, Fact]] = field(default_factory=dict)
    estimates: Dict[Tuple[str, str, str], Fact] = field(default_factory=dict)

    def get(self, period: str, metric: str, item: str = "total") -> Optional[Fact]:
        return self.facts.get((period, metric, item))

    def quarters(self) -> List[str]:
        """Quarters with total revenue, oldest first"""
        qs = {p for (p, m, i) in self.facts if m == "revenue" and i == "total" and "Q" in p}
        return sorted(qs, key=_quarter_key)


def _quarter_key(period: str) -> Tuple[int, int]:
    year, q = period.split("Q")
    return int(year), int(q)


def previous_quarter(period: str, back: int = 1) -> str:
    year, q = _quarter_key(period)
    index = year * 4 + (q - 1) - back
    return f"{index // 4}Q{index % 4 + 1}"


def _relations(year: int) -> List[Tuple[str, List[str]]]:
    q = [f"{year}Q{i}" for i in range(1, 5)]
    h1, nine, fy = f"{year}H1", f"{year}-9M", f"{year}FY"
    # Two-term relations first so a quarter is derived from printed
    # aggregates (Q4 = FY - 9M) rather than from other derived quarters
    return [
        (h1, q[:2]),
        (nine, [h1, q[2]]),
        (fy, [nine, q[3]]),
        (nine, q[:3]),
        (fy, q),
    ]


def load_fundamentals(ticker: str, path: str = None) -> Fundamentals:
    path = path or os.path.join(FUNDAMENTALS_DIR, f"{ticker}.yaml")
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    fund = Fundamentals(
        ticker=raw["ticker"],
        company=raw.get("company", raw["ticker"]),
        segments=raw.get("segments", []),
        sources=raw.get("sources", {}),
    )

    for period, block in (raw.get("reported") or {}).items():
        _load_block(fund.facts, fund, str(period), block)

    for period, block in (raw.get("estimates") or {}).items():
        _load_block(fund.estimates, fund, str(period), block)

    for date, block in (raw.get("balance_sheet") or {}).items():
        source = block["source"]
        _check_source(fund, source)
        items = {
            key: Fact(float(value), [source])
            for key, value in block.items()
            if key not in ("source", "shares_m")
        }
        shares = block.get("shares_m") or {}
        if shares:
            items["shares_outstanding_m"] = Fact(
                float(sum(shares.values())), [source],
                derived_from="sum of share classes" if len(shares) > 1 else None,
            )
        fund.balance_sheet[str(date)] = items

    errors = []
    _fill_segment_totals(fund.facts, fund.segments, errors)
    _derive_periods(fund.facts, errors)
    _fill_segment_totals(fund.facts, fund.segments, errors)
    if errors:
        raise ValueError(f"{ticker} fundamentals are inconsistent:\n  " + "\n  ".join(errors))
    return fund


def _check_source(fund: Fundamentals, source: str):
    if source not in fund.sources:
        raise ValueError(f"{fund.ticker}: unknown source '{source}'")


def _load_block(target: dict, fund: Fundamentals, period: str, block: dict):
    source = block["source"]
    _check_source(fund, source)
    for metric in SEGMENTED_METRICS:
        for item, value in (block.get(metric) or {}).items():
            target[(period, metric, item)] = Fact(float(value), [source])
    if "net_income" in block:
        target[(period, "net_income", "total")] = Fact(float(block["net_income"]), [source])
    for kpi, value in (block.get("kpis") or {}).items():
        target[(period, "kpi", kpi)] = Fact(float(value), [source])


def _fill_segment_totals(facts: dict, segments: List[str], errors: List[str]):
    """Total = sum of segments when only segments are printed; check otherwise."""
    periods = {(p, m) for (p, m, _) in facts if m in SEGMENTED_METRICS}
    for period, metric in sorted(periods):
        parts = [facts.get((period, metric, s)) for s in segments]
        if any(p is None for p in parts):
            continue
        part_sum = sum(p.value for p in parts)
        total = facts.get((period, metric, "total"))
        if total is None:
            facts[(period, metric, "total")] = Fact(
                part_sum, _merge_sources(parts), derived_from="sum of segments"
            )
        elif abs(total.value - part_sum) > ROUNDING_TOLERANCE * len(parts):
            errors.append(
                f"{period} {metric}: segments sum to {part_sum:,.0f} but total is {total.value:,.0f}"
            )


def _derive_periods(facts: dict, errors: List[str]):
    """Solve aggregate relations (H1 = Q1 + Q2, ...) for single unknowns, then cross-check."""
    keys = {(m, i) for (_, m, i) in facts if m != "kpi" or i in FLOW_KPIS}
    years = {int(p[:4]) for (p, _, _) in facts}

    changed = True
    while changed:
        changed = False
        for year in sorted(years):
            for metric, item in sorted(keys):
                for aggregate, parts in _relations(year):
                    terms = [aggregate] + parts
                    known = {t: facts.get((t, metric, item)) for t in terms}
                    missing = [t for t, f in known.items() if f is None]
                    if len(missing) != 1:
                        continue
                    target = missing[0]
                    if target == aggregate:
                        value = sum(known[p].value for p in parts)
                        formula = " + ".join(parts)
                    else:
                        others = [p for p in parts if p != target]
                        value = known[aggregate].value - sum(known[p].value for p in others)
                        formula = f"{aggregate} − " + " − ".join(others)
                    present = [f for f in known.values() if f is not None]
                    facts[(target, metric, item)] = Fact(value, _merge_sources(present), derived_from=formula)
                    changed = True

    for year in sorted(years):
        for metric, item in sorted(keys):
            for aggregate, parts in _relations(year):
                terms = [facts.get((t, metric, item)) for t in [aggregate] + parts]
                if any(t is None for t in terms):
                    continue
                agg, rest = terms[0], terms[1:]
                part_sum = sum(t.value for t in rest)
                if abs(agg.value - part_sum) > ROUNDING_TOLERANCE * len(rest):
                    errors.append(
                        f"{aggregate} {metric}/{item}: {' + '.join(parts)} = {part_sum:,.0f} "
                        f"but {aggregate} = {agg.value:,.0f}"
                    )


def _merge_sources(facts: List[Fact]) -> List[str]:
    merged = []
    for f in facts:
        for s in f.sources:
            if s not in merged:
                merged.append(s)
    return merged
