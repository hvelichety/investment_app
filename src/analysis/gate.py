"""
Pre-post gate: checks that run before anything is posted to Slack, and fixes
what can be fixed without a person.

Reports post to the #stock channels with no approval step (the user's
decision on 2026-11-14), so this is the safety net. Three layers:

1. Fact pack checks (run when the pack is built, in GitHub Actions):
   - freshness: the pack is from the latest trading day; if not, the
     workflow rebuilds it (retries Friday night and again Saturday morning).
   - sanity: market cap = close × shares, P/E and band position in a sane
     range, weekly move not absurd. A line that fails is removed from the
     pack with a note, so no report can quote it (auto-fix).
   - estimate age: the estimates page's own update date, not the day we
     recorded it.
2. Draft checks (run by the Saturday report before posting):
   - every figure is in the fact pack (or an allowed source such as a news
     excerpt or last week's pack); the app's own buy/sell call is never allowed.
   - auto-fix: lines with figures that can't be traced are dropped.
3. A post is held only when a fix still leaves a problem, e.g. the pack is
   still stale after the retries, or the draft has nothing left after fixing.

Everything here is plain code: no model calls, no paid API.
"""

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Iterable, List, Optional, Tuple

from .numbers import unsupported_numbers

HOLD, WARN = "hold", "warn"

MAX_WEEKLY_MOVE_PCT = 25.0      # bigger moves happen (earnings), so this warns, never drops data
MARKET_CAP_TOLERANCE = 0.02     # close × shares vs the printed market cap
PE_RANGE = (0.0, 200.0)         # P/E on the average estimate outside this = broken input
BAND_POSITION_RANGE = (-150.0, 250.0)
MAX_ESTIMATE_AGE_DAYS = 21      # by the estimates page's own "last updated" date

WEEK_RE = re.compile(r"<!-- week ending (\d{4}-\d{2}-\d{2}) -->")
CLOSE_RE = re.compile(r"^- (?P<t>[A-Z.^]+) close: \$(?P<close>[\d,]+\.\d+)", re.M)
MOVE_RE = re.compile(r"^- 1-week change: (?P<pct>[-+]\d+(?:\.\d+)?)%", re.M)
OWN_CAP_RE = re.compile(r"^- (?P<t>[A-Z.]+) market cap: (?P<cap>-?\$[\d,.]+[TBM]) \((?P<shares>[\d,.]+)M shares\)$", re.M)
PEER_CAP_RE = re.compile(r"^- (?P<t>[A-Z.]+) close: \$(?P<close>[\d,]+\.\d+); market cap (?P<cap>-?\$[\d,.]+[TBM]) "
                         r"\((?P<shares>[\d,.]+)M shares\)$", re.M)
VS_CAP_RE = re.compile(r"^- (?P<a>[A-Z.]+) market cap vs (?P<b>[A-Z.]+): .*$", re.M)
PE_RE = re.compile(r"^  - Current P/E on the average estimate: (?P<pe>-?[\d,.]+)x$", re.M)
POSITION_RE = re.compile(r"^  - Price \$[\d,.]+ sits at (?P<pos>-?\d+)% of the band: (?P<zone>.+)$", re.M)
UPDATED_RE = re.compile(r"updated (\d{4}-\d{2}-\d{2})")

# The app reports where the price sits in Pei's band and what the channel's
# method does there; it never makes its own call (docs/METHODOLOGY.md).
OWN_CALL_RE = re.compile(
    r"\b(we|I)\s+(recommend|suggest|advise)\b.{0,40}\b(buy|sell|short|trim|add)\w*"
    r"|\b(strong\s+buy|strong\s+sell)\b"
    r"|\b(you\s+should|everyone\s+should)\s+(buy|sell|short|trim)\b",
    re.I)


@dataclass
class Finding:
    check: str
    severity: str          # hold | warn
    detail: str
    fixed: bool = False    # an automatic fix was applied
    fix: str = ""


@dataclass
class GateResult:
    ticker: str
    findings: List[Finding] = field(default_factory=list)
    text: str = ""          # the (possibly fixed) fact pack or draft

    @property
    def open_holds(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == HOLD and not f.fixed]

    @property
    def fixes(self) -> List[Finding]:
        return [f for f in self.findings if f.fixed]

    @property
    def warnings(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == WARN]

    @property
    def status(self) -> str:
        if self.open_holds:
            return "hold"
        return "fixed" if self.fixes else "pass"

    def as_dict(self) -> dict:
        return {"ticker": self.ticker, "status": self.status,
                "findings": [asdict(f) for f in self.findings]}


# --- helpers -------------------------------------------------------------

def money_m(text: str) -> float:
    """"$1.54T" -> 1_540_000 ($M)"""
    sign = -1 if text.startswith("-") else 1
    value = float(text.lstrip("-$").rstrip("TBM").replace(",", ""))
    return sign * value * {"T": 1_000_000, "B": 1000, "M": 1}[text[-1]]


def _num(text: str) -> float:
    return float(text.replace(",", ""))


def factpack_week(text: str) -> Optional[date]:
    m = WEEK_RE.search(text)
    return date.fromisoformat(m.group(1)) if m else None


def last_trading_day(today: date) -> date:
    """Latest weekday on or before today (market holidays are allowed for in is_fresh)"""
    day = today
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def is_fresh(week_ending: Optional[date], today: date, after_close: bool = True) -> bool:
    """The pack is from the latest close, allowing one weekday for a market holiday.

    after_close=False (a weekday run before the close): the previous trading day counts too.
    """
    if week_ending is None:
        return False
    expected = last_trading_day(today)
    if not after_close and today.weekday() < 5:
        expected = last_trading_day(today - timedelta(days=1))
    allowed = last_trading_day(expected - timedelta(days=1))
    return week_ending >= allowed


def _drop_lines(text: str, spans: Iterable[Tuple[int, int]], note: str) -> str:
    """Replace whole lines covering each (start, end) span with one note line"""
    lines = text.split("\n")
    offsets, pos = [], 0
    for line in lines:
        offsets.append((pos, pos + len(line)))
        pos += len(line) + 1
    drop = set()
    for start, end in spans:
        for i, (a, b) in enumerate(offsets):
            if a <= end and b >= start:
                drop.add(i)
    if not drop:
        return text
    out, noted = [], False
    for i, line in enumerate(lines):
        if i in drop:
            if not noted:
                indent = line[:len(line) - len(line.lstrip())]
                out.append(f"{indent}- _{note}_")
                noted = True
            continue
        out.append(line)
    return "\n".join(out)


def _band_block(text: str, line_start: int) -> Tuple[int, int]:
    """Span of the band period that contains the sub-line at line_start (its "- period:" line + sub-lines)"""
    head = text.rfind("\n- ", 0, line_start) + 1
    nxt = re.compile(r"^(?!  - )", re.M)
    m = nxt.search(text, text.index("\n", head) + 1)
    end = m.start() - 1 if m else len(text)
    return head, end


# --- fact pack -----------------------------------------------------------

def check_factpack(ticker: str, text: str, today: date, after_close: bool = True) -> GateResult:
    """Check a fact pack and remove any line that fails a sanity check"""
    result = GateResult(ticker)
    week = factpack_week(text)
    if not is_fresh(week, today, after_close):
        result.findings.append(Finding("fresh", HOLD, f"fact pack is for week ending {week or 'unknown'}, "
                                       f"expected {last_trading_day(today)}"))

    m = MOVE_RE.search(text)
    if m and abs(float(m.group("pct"))) > MAX_WEEKLY_MOVE_PCT:
        result.findings.append(Finding("weekly_move", WARN, f"1-week change {m.group('pct')}%: "
                                       "confirm it with a news item before writing about it"))

    closes = {c.group("t"): _num(c.group("close")) for c in CLOSE_RE.finditer(text)}
    bad_spans = []
    for m in OWN_CAP_RE.finditer(text):
        close = closes.get(m.group("t"))
        if close and _cap_mismatch(close, m.group("shares"), m.group("cap")):
            bad_spans.append((m.start(), m.end(), f"{m.group('t')} market cap does not equal close × shares"))
    for m in PEER_CAP_RE.finditer(text):
        if _cap_mismatch(_num(m.group("close")), m.group("shares"), m.group("cap")):
            bad_spans.append((m.start(), m.end(), f"{m.group('t')} market cap does not equal close × shares"))
    bad_caps = {why.split(" ")[0] for _, _, why in bad_spans}
    for m in VS_CAP_RE.finditer(text):
        if bad_caps & {m.group("a"), m.group("b")}:
            bad_spans.append((m.start(), m.end(), f"{m.group('a')} vs {m.group('b')} uses a market cap that failed"))
    for m in PE_RE.finditer(text):
        pe = _num(m.group("pe"))
        if not PE_RANGE[0] < pe <= PE_RANGE[1]:
            start, end = _band_block(text, m.start())
            bad_spans.append((start, end, f"P/E {pe:g}x is outside {PE_RANGE[0]:g}–{PE_RANGE[1]:g}x"))
    for m in POSITION_RE.finditer(text):
        pos = float(m.group("pos"))
        if not BAND_POSITION_RANGE[0] <= pos <= BAND_POSITION_RANGE[1]:
            start, end = _band_block(text, m.start())
            bad_spans.append((start, end, f"band position {pos:g}% is outside "
                              f"{BAND_POSITION_RANGE[0]:g}% to {BAND_POSITION_RANGE[1]:g}%"))

    # Apply fixes from the bottom up so earlier offsets stay valid
    fixed_text = text
    seen = set()
    for start, end, why in sorted(bad_spans, key=lambda s: -s[0]):
        if (start, end) in seen:
            continue
        seen.add((start, end))
        fixed_text = _drop_lines(fixed_text, [(start, end)],
                                 "Omitted by the data check: the source data failed a consistency check this week")
        result.findings.append(Finding("sanity", HOLD, why, fixed=True, fix="line removed from the fact pack"))

    for m in UPDATED_RE.finditer(text):
        age = (today - date.fromisoformat(m.group(1))).days
        if age > MAX_ESTIMATE_AGE_DAYS:
            result.findings.append(Finding("estimate_age", WARN, f"analyst estimates last updated {m.group(1)} "
                                           f"({age} days ago); say so if the band is quoted"))
            break
    result.text = fixed_text
    return result


def _cap_mismatch(close: float, shares: str, cap: str) -> bool:
    computed = close * _num(shares)
    printed = money_m(cap)
    # The printed cap is rounded to 2 decimals of T/B; allow that plus the tolerance
    return abs(computed - printed) > max(abs(printed) * MARKET_CAP_TOLERANCE, 1.0)


# --- draft ---------------------------------------------------------------

def check_draft(ticker: str, draft: str, factpack: str, allowed: str = "", today: Optional[date] = None,
                fix: bool = True) -> GateResult:
    """Check a Slack draft against its fact pack; with fix=True, drop lines whose figures can't be traced.

    allowed: extra text whose figures may be quoted (news excerpts, Pei's posts, last week's pack).
    """
    result = GateResult(ticker, text=draft)
    if today is not None and not is_fresh(factpack_week(factpack), today):
        result.findings.append(Finding("fresh", HOLD, f"fact pack is for week ending {factpack_week(factpack)}"))

    sources = factpack + "\n" + allowed
    for m in OWN_CALL_RE.finditer(draft):
        result.findings.append(Finding("own_call", HOLD, f"“{m.group(0)}” reads as the app's own buy/sell call"))
    missing = unsupported_numbers(draft, sources)
    if missing:
        result.findings.append(Finding("figures", HOLD, "not in the fact pack or an allowed source: "
                                       + ", ".join(missing)))
    if not fix or not result.open_holds:
        return result

    # Auto-fix: drop the bullets that carry an untraceable figure or an own call
    kept, dropped = [], []
    for line in draft.split("\n"):
        if line.strip() and (unsupported_numbers(line, sources) or OWN_CALL_RE.search(line)):
            dropped.append(line.strip())
        else:
            kept.append(line)
    fixed = "\n".join(kept)
    still = unsupported_numbers(fixed, sources) or OWN_CALL_RE.search(fixed)
    bullets_left = sum(1 for line in kept if line.lstrip().startswith(("-", "•", "*")))
    for f in result.findings:
        if f.check in ("figures", "own_call"):
            f.fixed = not still and bullets_left >= 2
            f.fix = f"dropped {len(dropped)} line(s): " + " | ".join(dropped)
    if bullets_left < 2:
        result.findings.append(Finding("too_short", HOLD, "fewer than 2 bullets left after the fix"))
    result.text = fixed
    return result


GATE_CHECKS = ("fresh", "sanity", "figures", "own_call")


def footer(factpack: str, findings: List[Finding]) -> str:
    """One line for the end of each Slack post: what was checked and how old the data is"""
    failed = {f.check for f in findings if f.severity == HOLD and not f.fixed} & set(GATE_CHECKS)
    fixed = sum(1 for f in findings if f.fixed)
    parts = [f"Data checks: {len(GATE_CHECKS) - len(failed)}/{len(GATE_CHECKS)} passed"
             + (f" ({fixed} auto-fixed)" if fixed else "")]
    week = factpack_week(factpack)
    if week:
        parts.append(f"prices as of {week:%b} {week.day} close")
    updated = sorted(UPDATED_RE.findall(factpack))
    if updated:
        oldest = date.fromisoformat(updated[0])
        parts.append(f"estimates updated {oldest:%b} {oldest.day}")
    return "_" + " · ".join(parts) + "_"


def gate_comment(result: GateResult) -> str:
    """Machine-readable record for the weekly GitHub issue, collected into data/metrics/"""
    return "<!-- gate: " + json.dumps(result.as_dict(), ensure_ascii=False) + " -->"
