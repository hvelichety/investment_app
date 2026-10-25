"""
Run the analyst agent for a ticker and write a memo draft for review.

Usage:
    ANTHROPIC_API_KEY=... python3 scripts/run_analyst.py SPCX

Builds the fact pack (valued at the latest close: local price table first,
then Yahoo Finance), runs the analyst + CFO reviewer, and writes
reports/<TICKER>_memo.md with the review notes appended. Nothing is posted
anywhere; the memo is a draft for a person to approve.
"""

import os
import sys

import yaml

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from scripts.build_factpack import latest_close  # noqa: E402
from src.analysis.agent import run_analyst  # noqa: E402
from src.analysis.factpack import build_factpack  # noqa: E402
from src.analysis.fundamentals import load_fundamentals  # noqa: E402


def current_price(ticker: str):
    price, date = latest_close(ticker)
    if price is not None:
        return price, date
    try:
        import yfinance as yf
        history = yf.Ticker(ticker).history(period="5d")
        if not history.empty:
            return float(history["Close"].iloc[-1]), history.index[-1].strftime("%Y-%m-%d")
    except Exception as e:
        print(f"Price lookup failed: {e}", file=sys.stderr)
    return None, None


def render(ticker: str, result, price, price_date) -> str:
    status = "✅ passed review" if result.clean else "⚠️ open issues below — check before sharing"
    lines = [
        f"<!-- Draft for review. Valued at ${price:,.2f} on {price_date}. -->" if price is not None
        else "<!-- Draft for review. No share price available, so no valuation. -->",
        result.memo,
        "",
        "---",
        f"**Review status:** {status}" + (f" (revised {len(result.history) - 1}x)" if result.revised else ""),
        "",
    ]
    if result.unsupported_numbers:
        lines.append("**Figures not found in the fact pack:** " + ", ".join(result.unsupported_numbers))
        lines.append("")
    if result.review.get("issues"):
        lines.append("**CFO reviewer notes:**")
        for issue in result.review["issues"]:
            lines.append(f"- “{issue['quote']}” — {issue['problem']} (Fix: {issue['fix']})")
    return "\n".join(lines) + "\n"


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: run_analyst.py TICKER")
    ticker = sys.argv[1].upper()

    with open(os.path.join(ROOT_DIR, "playbooks", f"{ticker}.yaml"), encoding="utf-8") as f:
        playbook = yaml.safe_load(f)

    price, price_date = current_price(ticker)
    factpack = build_factpack(load_fundamentals(ticker), price=price, price_date=price_date)
    result = run_analyst(factpack, playbook)

    out_dir = os.path.join(ROOT_DIR, "reports")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"{ticker}_factpack.md"), "w", encoding="utf-8") as f:
        f.write(factpack)
    out_path = os.path.join(out_dir, f"{ticker}_memo.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(render(ticker, result, price, price_date))
    print(f"Wrote {out_path} ({'clean' if result.clean else 'needs attention'})")


if __name__ == "__main__":
    main()
