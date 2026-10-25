"""
Build the analyst fact pack for a ticker.

Usage:
    python3 scripts/build_factpack.py SPCX
    python3 scripts/build_factpack.py SPCX --price 148 --date 2026-10-20

Without --price, the latest close in the daily_prices table is used (if any).
Writes reports/<TICKER>_factpack.md and prints it.
"""

import argparse
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from src.analysis.factpack import build_factpack  # noqa: E402
from src.analysis.fundamentals import load_fundamentals  # noqa: E402


def latest_close(ticker: str):
    """(close, date) from the local price table, or (None, None)"""
    from src.database_manager import MetricsDatabase
    db = MetricsDatabase()
    try:
        db.connect()
        prices = db.get_price_history(ticker)
    except Exception:
        return None, None
    finally:
        db.close()
    if prices.empty:
        return None, None
    last = prices.iloc[-1]
    return float(last['close']), str(last['price_date'])


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("ticker")
    parser.add_argument("--price", type=float, help="share price for valuation multiples")
    parser.add_argument("--date", help="date of --price (YYYY-MM-DD)")
    args = parser.parse_args()

    price, price_date = args.price, args.date
    if price is None:
        price, price_date = latest_close(args.ticker)
    elif price_date is None:
        parser.error("--date is required with --price")

    fund = load_fundamentals(args.ticker)
    text = build_factpack(fund, price=price, price_date=price_date)

    out_dir = os.path.join(ROOT_DIR, "reports")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{args.ticker}_factpack.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    print(f"\nWrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
