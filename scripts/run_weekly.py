"""
Weekly report: analyst memo, commentary, and fact check for each ticker.

Usage:
    ANTHROPIC_API_KEY=... python3 scripts/run_weekly.py            # every ticker with a playbook
    ANTHROPIC_API_KEY=... python3 scripts/run_weekly.py SPCX TSLA

For each ticker:
  1. Fact pack with this week's market section (price moves, multiples vs a
     week earlier, market cap vs the playbook's peers).
  2. Analyst memo + CFO review (src/analysis/agent.py).
  3. Commentary agent: this week's news, thesis scorecard, Slack draft.
  4. Verifier agent checks the commentary; if anything is contradicted or
     unconfirmed, the commentary is rewritten once and checked again.
  5. Verifier checks the memo too.
Writes reports/<TICKER>_weekly.md (the review issue body) and
reports/<TICKER>_weekly.json. Nothing is posted to Slack.
"""

import json
import os
import sys
from dataclasses import asdict

import yaml

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from src.analysis.agent import run_analyst, unsupported_numbers  # noqa: E402
from src.analysis.commentary import write_commentary  # noqa: E402
from src.analysis.factpack import build_factpack  # noqa: E402
from src.analysis.fundamentals import load_fundamentals  # noqa: E402
from src.analysis.verifier import verify_report  # noqa: E402
from src.analysis.weekly import weekly_section  # noqa: E402

MAX_ISSUE_CHARS = 60000
DIRECTION_LABELS = {"strengthens": "▲ strengthens", "weakens": "▼ weakens",
                    "no_change": "– no change", "no_new_data": "· no new data"}


def tickers_with_playbooks():
    playbooks = {f[:-5] for f in os.listdir(os.path.join(ROOT_DIR, "playbooks")) if f.endswith(".yaml")}
    data = {f[:-5] for f in os.listdir(os.path.join(ROOT_DIR, "data", "fundamentals")) if f.endswith(".yaml")}
    return sorted(playbooks & data)


def price_history(ticker: str):
    """(date, close) for the past year from Yahoo Finance"""
    import yfinance as yf
    history = yf.Ticker(ticker).history(period="1y")
    prices = [(d.strftime("%Y-%m-%d"), float(c)) for d, c in history["Close"].dropna().items()]
    if not prices:
        raise RuntimeError(f"No price history for {ticker}")
    return prices


def peer_quote(ticker: str, day: str):
    """(close on or before `day`, shares outstanding in millions)"""
    import yfinance as yf
    t = yf.Ticker(ticker)
    closes = [(d, c) for d, c in price_history(ticker) if d <= day]
    shares = t.info.get("sharesOutstanding") or t.fast_info.get("shares")
    if not closes or not shares:
        raise RuntimeError(f"No quote or share count for {ticker}")
    return closes[-1][1], shares / 1e6


def _feedback(problems):
    return [f"“{p['claim']}” ({p['status']}): {p['note'] or p['evidence']}"
            + (f" [source: {p['source_url']}]" if p["source_url"] else "") for p in problems]


def _findings_table(findings):
    rows = ["| Status | Claim | Basis | Evidence / note |", "|---|---|---|---|"]
    icon = {"verified": "✅", "contradicted": "❌", "unverified": "❓"}
    for f in findings:
        detail = f["note"] if f["status"] != "verified" else f["evidence"]
        if f["source_url"]:
            detail += f" ([source]({f['source_url']}))"
        cells = [f"{icon[f['status']]} {f['status']}", f["claim"], f["basis"], detail]
        rows.append("| " + " | ".join(c.replace("|", "\\|").replace("\n", " ") for c in cells) + " |")
    return rows


def render(ticker, day, memo_result, commentary, check, memo_check, revised):
    problems = check.problems + memo_check.problems
    status = ("✅ every checked claim verified" if not problems
              else f"⚠️ {len(problems)} claim(s) need a look before sharing (see Verification)")
    lines = [
        f"# {ticker} weekly report: week ending {day}",
        "",
        f"**Status:** {status}. Draft for review; nothing has been posted to Slack.",
        "",
        "## Slack draft" + (" (rewritten once after fact check)" if revised else ""),
        "",
        "```text",
        commentary.slack_post,
        "```",
        "",
        "## Thesis scorecard",
        "",
        "| Thesis question | This week | Evidence |",
        "|---|---|---|",
    ]
    for s in commentary.scorecard:
        cells = [s["question"], DIRECTION_LABELS[s["direction"]], s["evidence"]]
        lines.append("| " + " | ".join(c.replace("|", "\\|").replace("\n", " ") for c in cells) + " |")
    lines += ["", "## Watch next week", ""] + [f"- {w}" for w in commentary.watch_next]
    lines += ["", "## News used", ""]
    lines += [f"- [{n['headline']}]({n['url']}): {n['outlet']}, {n['date']}" for n in commentary.news] or ["- none"]
    if commentary.dropped_news:
        lines += ["", "Dropped (URL not returned by any search, so the item couldn't be confirmed):"]
        lines += [f"- {n['headline']} ({n['outlet']})" for n in commentary.dropped_news]

    lines += ["", "## Verification", "",
              f"Commentary: {len(check.by_status('verified'))} verified, "
              f"{len(check.by_status('contradicted'))} contradicted, {len(check.by_status('unverified'))} unconfirmed. "
              f"Memo: {len(memo_check.by_status('verified'))} verified, "
              f"{len(memo_check.by_status('contradicted'))} contradicted, "
              f"{len(memo_check.by_status('unverified'))} unconfirmed.", ""]
    if problems:
        lines += ["**Needs a look:**", ""] + _findings_table(problems) + [""]
    verified = check.by_status("verified") + memo_check.by_status("verified")
    lines += ["<details><summary>All verified claims</summary>", ""] + _findings_table(verified) + ["", "</details>", ""]

    review = "passed" if memo_result.clean else "open issues"
    lines += ["## Analyst memo", "", f"<details><summary>Quarterly memo (CFO review: {review})</summary>", "",
              memo_result.memo, ""]
    if memo_result.review.get("issues"):
        lines.append("**CFO reviewer notes:**")
        lines += [f"- “{i['quote']}”: {i['problem']} (Fix: {i['fix']})" for i in memo_result.review["issues"]]
    lines += ["", "</details>", ""]

    body = "\n".join(lines)
    if len(body) > MAX_ISSUE_CHARS:
        body = body[:MAX_ISSUE_CHARS] + "\n\n…cut to fit the issue; the full report is in the run artifact.\n"
    return body


def run(ticker: str, client):
    with open(os.path.join(ROOT_DIR, "playbooks", f"{ticker}.yaml"), encoding="utf-8") as f:
        playbook = yaml.safe_load(f)
    fund = load_fundamentals(ticker)

    prices = price_history(ticker)
    day, close = prices[-1]
    peers = {}
    for peer in playbook.get("relative", []):
        try:
            peers[peer["ticker"]] = peer_quote(peer["ticker"], day)
        except Exception as e:
            print(f"  ! {peer['ticker']} quote unavailable: {e}", file=sys.stderr)
    market = weekly_section(fund, prices, peers)
    factpack = build_factpack(fund, price=close, price_date=day, market_section=market)
    known_urls = {s["url"] for s in fund.sources.values()}

    print(f"{ticker}: memo")
    memo_result = run_analyst(factpack, playbook, client=client)

    print(f"{ticker}: commentary")
    commentary = write_commentary(factpack, memo_result.memo, playbook, day, client)
    print(f"{ticker}: fact check")
    check = verify_report(commentary.text(), factpack, client, known_urls,
                          unsupported_numbers(commentary.text(), factpack))
    revised = False
    if check.problems:
        print(f"{ticker}: rewriting commentary ({len(check.problems)} problems)")
        commentary = write_commentary(factpack, memo_result.memo, playbook, day, client,
                                      feedback=_feedback(check.problems), previous=commentary)
        check = verify_report(commentary.text(), factpack, client,
                              known_urls | {n["url"] for n in commentary.news},
                              unsupported_numbers(commentary.text(), factpack))
        revised = True

    print(f"{ticker}: memo fact check")
    memo_check = verify_report(memo_result.memo, factpack, client, known_urls, memo_result.unsupported_numbers)

    out_dir = os.path.join(ROOT_DIR, "reports")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"{ticker}_factpack.md"), "w", encoding="utf-8") as f:
        f.write(factpack)
    with open(os.path.join(out_dir, f"{ticker}_weekly.md"), "w", encoding="utf-8") as f:
        f.write(render(ticker, day, memo_result, commentary, check, memo_check, revised))
    with open(os.path.join(out_dir, f"{ticker}_weekly.json"), "w", encoding="utf-8") as f:
        json.dump({
            "ticker": ticker,
            "week_ending": day,
            "slack_channel": playbook.get("slack_channel"),
            "commentary": asdict(commentary),
            "commentary_findings": check.findings,
            "memo": memo_result.memo,
            "memo_findings": memo_check.findings,
            "clean": not (check.problems or memo_check.problems),
        }, f, indent=2, ensure_ascii=False)
    print(f"{ticker}: wrote reports/{ticker}_weekly.md")


def main():
    import anthropic
    client = anthropic.Anthropic()
    tickers = [t.upper() for t in sys.argv[1:]] or tickers_with_playbooks()
    failed = []
    for ticker in tickers:
        try:
            run(ticker, client)
        except Exception as e:
            print(f"{ticker}: failed: {e}", file=sys.stderr)
            failed.append(ticker)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
