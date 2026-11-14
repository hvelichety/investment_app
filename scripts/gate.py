"""
Pre-post gate (src/analysis/gate.py) from the command line.

Fact packs, before the Saturday report (and in the workflow, to decide on a rebuild):
    python3 scripts/gate.py packs                 # every ticker with a playbook
    python3 scripts/gate.py packs --stale-only    # print only tickers whose pack is stale or missing
  Exit code 2 if any pack is stale or missing.

A Slack draft, before it is posted:
    python3 scripts/gate.py draft RH draft.md [--allow news.md ...] [--out fixed.md]
  Checks every figure against data/factpacks/RH.md plus the --allow files
  (news excerpts, Pei's posts, last week's pack), and the app's own buy/sell
  calls. Lines that fail are dropped automatically and the fixed draft is
  written to --out (default: draft path with .gated.md). Prints the footer line
  for the post and the <!-- gate: ... --> record for the weekly issue.
  Exit code 0 = post (pass or fixed), 1 = hold (the fix wasn't enough).
"""

import argparse
import os
import sys
from datetime import date, datetime, timezone

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from src.analysis.gate import check_draft, check_factpack, footer, gate_comment  # noqa: E402

FACTPACK_DIR = os.path.join(ROOT_DIR, "data", "factpacks")


def _tickers(args):
    if args:
        return [t.upper() for t in args]
    return sorted(f[:-5] for f in os.listdir(os.path.join(ROOT_DIR, "playbooks")) if f.endswith(".yaml"))


def _after_close(now: datetime) -> bool:
    return now.weekday() >= 5 or now.hour >= 21  # US close is 20:00/21:00 UTC


def packs(tickers, stale_only=False):
    now = datetime.now(timezone.utc)
    stale = []
    for t in tickers:
        path = os.path.join(FACTPACK_DIR, f"{t}.md")
        if not os.path.exists(path):
            stale.append(t)
            if not stale_only:
                print(f"{t}: hold: no fact pack")
            continue
        with open(path, encoding="utf-8") as f:
            result = check_factpack(t, f.read(), now.date(), _after_close(now))
        if any(f.check == "fresh" for f in result.open_holds):
            stale.append(t)
        if not stale_only:
            print(f"{t}: {result.status}")
            for f in result.findings:
                print(f"  {'fixed' if f.fixed else f.severity}: {f.check}: {f.detail}")
    if stale_only:
        print(" ".join(stale))
    return 2 if stale else 0


def draft(ticker, draft_path, allow, out):
    with open(os.path.join(FACTPACK_DIR, f"{ticker}.md"), encoding="utf-8") as f:
        factpack = f.read()
    with open(draft_path, encoding="utf-8") as f:
        text = f.read()
    allowed = ""
    for path in allow or []:
        with open(path, encoding="utf-8") as f:
            allowed += "\n" + f.read()
    now = datetime.now(timezone.utc)
    pack = check_factpack(ticker, factpack, now.date(), _after_close(now))
    result = check_draft(ticker, text, factpack, allowed)
    result.findings = [f for f in pack.findings if f.check in ("fresh", "estimate_age", "weekly_move")] + result.findings
    out = out or os.path.splitext(draft_path)[0] + ".gated.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write(result.text)
    print(f"{ticker}: {result.status.upper()}")
    for f in result.findings:
        state = "fixed" if f.fixed else f.severity
        print(f"  {state}: {f.check}: {f.detail}" + (f" ({f.fix})" if f.fix else ""))
    print(f"fixed draft: {out}")
    print("footer: " + footer(factpack, result.findings))
    print(gate_comment(result))
    return 1 if result.status == "hold" else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("packs")
    p.add_argument("tickers", nargs="*")
    p.add_argument("--stale-only", action="store_true")
    d = sub.add_parser("draft")
    d.add_argument("ticker")
    d.add_argument("draft")
    d.add_argument("--allow", action="append")
    d.add_argument("--out")
    a = parser.parse_args()
    if a.cmd == "packs":
        sys.exit(packs(_tickers(a.tickers), a.stale_only))
    sys.exit(draft(a.ticker.upper(), a.draft, a.allow, a.out))


if __name__ == "__main__":
    main()
