"""
Weekly scorecard: is the app drifting from Pei, from its data sources, from
what prices actually did, or from last week?

Inputs (all files in the repo, no API calls):
  data/factpacks/<TICKER>.json  figures from this week's fact pack build
  data/pei/<TICKER>.yaml        figures Pei stated in his posts, recorded by
                                the Friday method review
  data/metrics/history.csv      one row per ticker per week (this module appends)
  Saturday gate records         <!-- gate: {...} --> lines in the weekly issues

Outputs: data/metrics/history.csv, data/metrics/reports.csv and
data/metrics/SCORECARD.md (latest week, flags, track record).
"""

import csv
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import yaml

SOURCE_GAP_PCT = 5.0       # stockanalysis.com vs Yahoo, same fiscal year
PEI_GAP_PCT = 2.0          # our estimate vs the one in Pei's latest post
PEI_MAX_AGE_DAYS = 45      # older Pei figures aren't compared
SHARES_CHANGE_PCT = 2.0    # week-to-week share count change
ESTIMATE_CHANGE_PCT = 5.0  # week-to-week consensus change
QUIET_PRICE_PCT = 3.0      # a zone change with a smaller price move came from the estimates
HORIZONS_WEEKS = (4, 12)

HISTORY_FIELDS = ["week_ending", "ticker", "close", "benchmark", "benchmark_close", "band_period",
                  "band_low", "band_high", "band_position", "band_zone", "estimate_avg", "estimate_source",
                  "yahoo_avg", "source_gap_pct", "shares_m", "pei_date", "pei_estimate", "pei_gap_pct",
                  "pei_zone", "gate_status", "gate_fixes", "gate_warnings"]
REPORT_FIELDS = ["date", "ticker", "status", "fixes", "holds", "warnings", "issue"]

GATE_COMMENT_RE = re.compile(r"<!-- gate: (\{.*?\}) -->", re.S)
EXPECT_UP = {"below the band", "near the low end"}
EXPECT_DOWN = {"above the band", "near the high end"}


def _f(value) -> Optional[float]:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def _gap(a, b) -> Optional[float]:
    a, b = _f(a), _f(b)
    return None if a is None or not b else (a / b - 1) * 100


def _r(value, digits=2):
    return "" if value is None else round(value, digits)


def latest_pei(pei: Optional[dict], period: str, week_ending: str) -> Optional[dict]:
    """Pei's most recent recorded figure for this period, if recent enough"""
    end = date.fromisoformat(week_ending)
    entries = [e for e in (pei or {}).get("entries") or []
               if str(e.get("period", "0y")) == period and str(e.get("date", "")) <= week_ending]
    entries = [e for e in entries if (end - date.fromisoformat(str(e["date"]))).days <= PEI_MAX_AGE_DAYS]
    return sorted(entries, key=lambda e: str(e["date"]))[-1] if entries else None


def history_row(ticker: str, stats: dict, pei: Optional[dict] = None) -> dict:
    bands = stats.get("bands") or {}
    period = next(iter(bands), "")
    band = bands.get(period) or {}
    gate = stats.get("gate") or {}
    findings = gate.get("findings") or []
    bench = stats.get("benchmark") or {}
    row = {
        "week_ending": stats["week_ending"], "ticker": ticker, "close": round(stats["close"], 2),
        "benchmark": bench.get("symbol", ""), "benchmark_close": round(bench["close"], 2) if bench.get("close") else "",
        "band_period": period,
        "band_low": round(band["low"], 2) if band.get("low") is not None else "",
        "band_high": round(band["high"], 2) if band.get("high") is not None else "",
        "band_position": band.get("position", ""), "band_zone": band.get("zone", ""),
        "estimate_avg": band.get("estimate_avg", ""), "estimate_source": band.get("source", ""),
        "yahoo_avg": band.get("yahoo_avg") if band.get("yahoo_avg") is not None else "",
        "source_gap_pct": "", "shares_m": round(stats["shares_m"], 1) if stats.get("shares_m") else "",
        "pei_date": "", "pei_estimate": "", "pei_gap_pct": "", "pei_zone": "",
        "gate_status": gate.get("status", ""),
        "gate_fixes": sum(1 for f in findings if f.get("fixed")),
        "gate_warnings": "; ".join(f["detail"] for f in findings if f.get("severity") == "warn"),
    }
    if not band.get("source", "").startswith("Yahoo") and band.get("yahoo_avg") is not None:
        row["source_gap_pct"] = _r(_gap(band.get("estimate_avg"), band.get("yahoo_avg")))
    p = latest_pei(pei, period, stats["week_ending"]) if period else None
    if p:
        row.update(pei_date=str(p["date"]), pei_estimate=p.get("estimate_avg", ""),
                   pei_gap_pct=_r(_gap(band.get("estimate_avg"), p.get("estimate_avg"))),
                   pei_zone=p.get("zone", ""))
    return row


def merge_history(history: List[dict], rows: List[dict]) -> List[dict]:
    """Add this week's rows, replacing any earlier row for the same ticker and week"""
    keys = {(r["ticker"], r["week_ending"]) for r in rows}
    kept = [h for h in history if (h["ticker"], h["week_ending"]) not in keys]
    return sorted(kept + rows, key=lambda r: (r["week_ending"], r["ticker"]))


def _previous(history: List[dict], row: dict) -> Optional[dict]:
    earlier = [h for h in history if h["ticker"] == row["ticker"] and h["week_ending"] < row["week_ending"]]
    return earlier[-1] if earlier else None


def flags(history: List[dict], row: dict) -> List[str]:
    """Divergences worth a look this week, in plain words"""
    t, out = row["ticker"], []
    gap = _f(row.get("source_gap_pct"))
    if gap is not None and abs(gap) > SOURCE_GAP_PCT:
        out.append(f"{t}: {row['estimate_source']} and Yahoo differ by {gap:+.1f}% on the {row['band_period']} "
                   "estimate")
    pei_gap = _f(row.get("pei_gap_pct"))
    if pei_gap is not None and abs(pei_gap) > PEI_GAP_PCT:
        out.append(f"{t}: our estimate is {pei_gap:+.1f}% from Pei's ({row['pei_estimate']} on {row['pei_date']})")
    if row.get("pei_zone") and row.get("band_zone") and row["pei_zone"] != row["band_zone"]:
        out.append(f"{t}: band zone is \"{row['band_zone']}\" but Pei's latest post says \"{row['pei_zone']}\"")
    if row.get("gate_status") == "hold":
        out.append(f"{t}: the fact pack still failed a check after the automatic fixes")
    elif _f(row.get("gate_fixes")):
        out.append(f"{t}: {row['gate_fixes']} fact pack line(s) removed by the data check")

    prev = _previous(history, row)
    if prev:
        shares = _gap(row.get("shares_m"), prev.get("shares_m"))
        if shares is not None and abs(shares) > SHARES_CHANGE_PCT:
            out.append(f"{t}: share count moved {shares:+.1f}% week to week; check a new filing explains it")
        est = _gap(row.get("estimate_avg"), prev.get("estimate_avg"))
        if est is not None and abs(est) > ESTIMATE_CHANGE_PCT:
            out.append(f"{t}: consensus estimate moved {est:+.1f}% week to week")
        price = _gap(row.get("close"), prev.get("close"))
        if (row.get("band_zone") and prev.get("band_zone") and row["band_zone"] != prev["band_zone"]
                and price is not None and abs(price) < QUIET_PRICE_PCT):
            out.append(f"{t}: band zone changed ({prev['band_zone']} → {row['band_zone']}) on a {price:+.1f}% "
                       "price move, so the estimates moved it")
    return out


def track_record(history: List[dict], weeks: int) -> Dict[str, dict]:
    """Per ticker: band calls `weeks` later, relative to the benchmark.

    A call "works" when a stock below / near the low end of the band beats the
    benchmark, or one above / near the high end lags it. Mid band isn't scored.
    """
    by_ticker: Dict[str, List[dict]] = {}
    for h in history:
        by_ticker.setdefault(h["ticker"], []).append(h)
    out = {}
    for ticker, rows in by_ticker.items():
        rows = sorted(rows, key=lambda r: r["week_ending"])
        scored = hits = 0
        rel_sum = 0.0
        for i, r in enumerate(rows):
            if r.get("band_zone") not in EXPECT_UP | EXPECT_DOWN:
                continue
            target = (date.fromisoformat(r["week_ending"]) + timedelta(weeks=weeks)).isoformat()
            later = next((x for x in rows[i + 1:] if x["week_ending"] >= target), None)
            if not later or not _f(r.get("benchmark_close")) or not _f(later.get("benchmark_close")):
                continue
            rel = (_f(later["close"]) / _f(r["close"]) - _f(later["benchmark_close"]) / _f(r["benchmark_close"])) * 100
            scored += 1
            rel_sum += rel if r["band_zone"] in EXPECT_UP else -rel
            hits += (rel > 0) if r["band_zone"] in EXPECT_UP else (rel < 0)
        out[ticker] = {"scored": scored, "hits": hits, "avg_edge_pts": round(rel_sum / scored, 1) if scored else None}
    return out


def report_rows(issues: List[dict]) -> List[dict]:
    """Gate records from the weekly GitHub issues (gh issue list --json title,body,createdAt,url)"""
    rows = []
    for issue in issues:
        for m in GATE_COMMENT_RE.finditer(issue.get("body") or ""):
            try:
                g = json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
            findings = g.get("findings") or []
            rows.append({
                "date": (issue.get("createdAt") or "")[:10], "ticker": g.get("ticker", ""),
                "status": g.get("status", ""),
                "fixes": sum(1 for f in findings if f.get("fixed")),
                "holds": sum(1 for f in findings if f.get("severity") == "hold" and not f.get("fixed")),
                "warnings": sum(1 for f in findings if f.get("severity") == "warn"),
                "issue": issue.get("url", ""),
            })
    return rows


def merge_reports(existing: List[dict], new: List[dict]) -> List[dict]:
    keys = {(r["date"], r["ticker"]) for r in new}
    kept = [r for r in existing if (r["date"], r["ticker"]) not in keys]
    return sorted(kept + new, key=lambda r: (r["date"], r["ticker"]))


def render(history: List[dict], week_rows: List[dict], reports: List[dict]) -> str:
    week = max((r["week_ending"] for r in week_rows), default="")
    lines = [f"# Analyst scorecard: week ending {week}", "",
             "Written by the Friday fact pack run (scripts/scorecard.py). Thresholds are in "
             "src/analysis/scorecard.py.", "",
             "## This week", "",
             "| Ticker | Close | Band zone | Position | Estimate (source) | vs Yahoo | vs Pei | Data check |",
             "|---|---|---|---|---|---|---|---|"]
    for r in week_rows:
        est = f"{r['estimate_avg']} ({r['estimate_source']})" if r.get("estimate_avg") != "" else "–"
        src = f"{_f(r['source_gap_pct']):+.1f}%" if _f(r.get("source_gap_pct")) is not None else "–"
        pei = f"{_f(r['pei_gap_pct']):+.1f}% ({r['pei_date']})" if _f(r.get("pei_gap_pct")) is not None else "–"
        pos = f"{r['band_position']}%" if r.get("band_position") != "" else "–"
        lines.append(f"| {r['ticker']} | ${r['close']} | {r.get('band_zone') or '–'} | {pos} | {est} | {src} | "
                     f"{pei} | {r.get('gate_status') or '–'} |")
    all_flags = [f for r in week_rows for f in flags(history, r)]
    warnings = [f"{r['ticker']}: {w}" for r in week_rows for w in str(r.get("gate_warnings") or "").split("; ") if w]
    lines += ["", "## Flags", ""] + ([f"- {f}" for f in all_flags + warnings] or ["- None this week."])

    lines += ["", "## Track record of band calls", "",
              "A call works when a stock below or near the low end of the band beats the S&P 500 over the "
              "horizon, or one above or near the high end lags it. Mid band isn't scored.", "",
              "| Ticker | " + " | ".join(f"{w}-week calls (worked)" for w in HORIZONS_WEEKS) + " | "
              + " | ".join(f"{w}-week avg edge" for w in HORIZONS_WEEKS) + " |",
              "|---|" + "---|" * (2 * len(HORIZONS_WEEKS))]
    records = {w: track_record(history, w) for w in HORIZONS_WEEKS}
    for t in sorted({r["ticker"] for r in history}):
        cells = []
        for w in HORIZONS_WEEKS:
            rec = records[w].get(t) or {"scored": 0}
            cells.append(f"{rec['scored']} ({rec['hits']})" if rec["scored"] else "not enough history")
        for w in HORIZONS_WEEKS:
            rec = records[w].get(t) or {}
            cells.append(f"{rec['avg_edge_pts']:+.1f} pts" if rec.get("avg_edge_pts") is not None else "–")
        lines.append(f"| {t} | " + " | ".join(cells) + " |")

    recent = [r for r in reports if r["date"] >= (date.fromisoformat(week) - timedelta(weeks=8)).isoformat()] \
        if week else reports
    lines += ["", "## Saturday posts, last 8 weeks", ""]
    if recent:
        lines += ["| Date | Ticker | Gate | Fixes | Holds | Issue |", "|---|---|---|---|---|---|"]
        lines += [f"| {r['date']} | {r['ticker']} | {r['status']} | {r['fixes']} | {r['holds']} | {r['issue']} |"
                  for r in sorted(recent, key=lambda r: (r["date"], r["ticker"]), reverse=True)]
    else:
        lines.append("No gate records yet.")
    return "\n".join(lines) + "\n"


def read_csv(path: Path) -> List[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: List[dict], fields: List[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def update(root: Path, issues: Optional[List[dict]] = None) -> str:
    """Run the whole scorecard for every fact pack JSON under root/data/factpacks"""
    data = root / "data"
    rows = []
    for stats_path in sorted((data / "factpacks").glob("*.json")):
        ticker = stats_path.stem
        stats = json.loads(stats_path.read_text())
        pei_path = data / "pei" / f"{ticker}.yaml"
        pei = yaml.safe_load(pei_path.read_text()) if pei_path.exists() else None
        rows.append(history_row(ticker, stats, pei))
    metrics_dir = data / "metrics"
    history = merge_history(read_csv(metrics_dir / "history.csv"), rows)
    # rows read back from CSV are strings; use the merged copies for this week too
    week_rows = [h for h in history if (h["ticker"], h["week_ending"]) in {(r["ticker"], r["week_ending"]) for r in rows}]
    write_csv(metrics_dir / "history.csv", history, HISTORY_FIELDS)
    reports = read_csv(metrics_dir / "reports.csv")
    if issues:
        reports = merge_reports(reports, report_rows(issues))
        write_csv(metrics_dir / "reports.csv", reports, REPORT_FIELDS)
    text = render(history, week_rows, reports)
    (metrics_dir / "SCORECARD.md").write_text(text, encoding="utf-8")
    return text
