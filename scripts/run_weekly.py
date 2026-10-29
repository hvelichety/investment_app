"""
Weekly report: analyst memo, commentary, and fact check for each ticker.

Usage:
    ANTHROPIC_API_KEY=... python3 scripts/run_weekly.py            # every ticker with a playbook
    ANTHROPIC_API_KEY=... python3 scripts/run_weekly.py SPCX TSLA

For each ticker (method: docs/METHODOLOGY.md, per-ticker settings in playbooks/):
  1. Fact pack: sourced fundamentals when data/fundamentals/<TICKER>.yaml
     exists, plus this week's market section: price moves, multiples vs a
     week earlier, valuation band on analyst estimates, performance vs the
     S&P 500 / Nasdaq since the playbook's decision date, market cap vs peers.
  2. Analyst memo + CFO review (only with sourced fundamentals).
  3. Commentary agent: this week's news, thesis scorecard, Slack draft.
  4. Verifier agent checks the commentary; if anything is contradicted or
     unconfirmed, the commentary is rewritten once and checked again.
     The memo is checked too.
  5. Method review (when SLACK_BOT_TOKEN is set): the methodology author's
     posts from the past week are compared with the playbook; a revised
     playbook is written to playbooks/ for the workflow to open as a PR,
     and the figures in the posts are fact-checked.
Writes reports/<TICKER>_weekly.md (the review issue body),
reports/<TICKER>_weekly.json, and reports/method_changes.md when a playbook
changed. Nothing is posted to Slack.
"""

import json
import os
import sys
from dataclasses import asdict

import yaml

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from src.analysis import metrics  # noqa: E402
from src.analysis.agent import run_analyst, unsupported_numbers  # noqa: E402
from src.analysis.band import acquisition_lines, band_lines, relative_lines, valuation_band  # noqa: E402
from src.analysis.commentary import write_commentary  # noqa: E402
from src.analysis.factpack import build_factpack, build_market_factpack  # noqa: E402
from src.analysis.fundamentals import load_fundamentals  # noqa: E402
from src.analysis.verifier import Verification, verify_report  # noqa: E402
from src.analysis.weekly import MARKET_SOURCE, weekly_section  # noqa: E402

METHODOLOGY_PATH = os.path.join(ROOT_DIR, "docs", "METHODOLOGY.md")

MAX_ISSUE_CHARS = 60000
DIRECTION_LABELS = {"strengthens": "▲ strengthens", "weakens": "▼ weakens",
                    "no_change": "– no change", "no_new_data": "· no new data"}


def tickers_with_playbooks():
    return sorted(f[:-5] for f in os.listdir(os.path.join(ROOT_DIR, "playbooks")) if f.endswith(".yaml"))


def has_fundamentals(ticker: str) -> bool:
    return os.path.exists(os.path.join(ROOT_DIR, "data", "fundamentals", f"{ticker}.yaml"))


def price_history(ticker: str, period: str = "2y"):
    """(date, close) from Yahoo Finance, oldest first"""
    import yfinance as yf
    history = yf.Ticker(ticker).history(period=period)
    prices = [(d.strftime("%Y-%m-%d"), float(c)) for d, c in history["Close"].dropna().items()]
    if not prices:
        raise RuntimeError(f"No price history for {ticker}")
    return prices


def shares_outstanding_m(ticker: str):
    import yfinance as yf
    t = yf.Ticker(ticker)
    shares = t.info.get("sharesOutstanding") or t.fast_info.get("shares")
    return shares / 1e6 if shares else None


def peer_quote(ticker: str, day: str):
    """(close on or before `day`, shares outstanding in millions)"""
    closes = [(d, c) for d, c in price_history(ticker, "1y") if d <= day]
    shares = shares_outstanding_m(ticker)
    if not closes or not shares:
        raise RuntimeError(f"No quote or share count for {ticker}")
    return closes[-1][1], shares


def analyst_estimates(ticker: str, basis: str):
    """period ("0y", "+1y", ...) -> {"low", "avg", "high", "analysts"}; revenue in $M"""
    import yfinance as yf
    t = yf.Ticker(ticker)
    table = t.earnings_estimate if basis == "eps" else t.revenue_estimate
    scale = 1 if basis == "eps" else 1e6
    estimates = {}
    for period, row in table.iterrows():
        if any(row.get(k) is None or row.get(k) != row.get(k) for k in ("low", "avg", "high")):
            continue  # missing or NaN
        estimates[str(period)] = {
            "low": float(row["low"]) / scale, "avg": float(row["avg"]) / scale,
            "high": float(row["high"]) / scale,
            "analysts": int(row["numberOfAnalysts"]) if row.get("numberOfAnalysts") == row.get("numberOfAnalysts") else None,
        }
    return estimates


def market_lines(ticker, playbook, prices, fund):
    """Band and relative-performance lines for the market section, per the playbook's method"""
    method = playbook.get("method") or {}
    close = prices[-1][1]
    extra, band_section = [], []

    rel = method.get("relative_performance")
    if rel:
        benchmarks = {}
        for symbol in rel.get("benchmarks", []):
            try:
                benchmarks[symbol] = price_history(symbol)
            except Exception as e:
                print(f"  ! {symbol} history unavailable: {e}", file=sys.stderr)
        extra += relative_lines(ticker, prices, benchmarks, str(rel["since"]))

    cfg = method.get("valuation_band")
    if cfg:
        try:
            estimates = analyst_estimates(ticker, cfg["basis"])
            net_cash = shares = None
            if cfg["basis"] == "revenue":
                v = metrics.valuation(fund, close, prices[-1][0])
                net_cash, shares = v.net_cash, v.shares_m
            bands = [valuation_band(estimates[p], p, cfg["basis"], cfg["multiple"]["low"], cfg["multiple"]["high"],
                                    net_cash_m=net_cash, shares_m=shares)
                     for p in cfg.get("periods", ["0y"]) if p in estimates]
            zones = cfg.get("zones") or {}
            if bands:
                band_section = band_lines(bands, close, MARKET_SOURCE, (zones.get("low", 25), zones.get("high", 75)),
                                          on=cfg.get("estimate", "avg"))
        except Exception as e:
            print(f"  ! valuation band unavailable for {ticker}: {e}", file=sys.stderr)
    acq = method.get("acquisition_reference")
    if acq:
        try:
            extra += acquisition_reference(ticker, close, prices[-1][0], acq)
        except Exception as e:
            print(f"  ! acquisition reference unavailable for {ticker}: {e}", file=sys.stderr)
    return extra, band_section


def acquisition_reference(ticker, close, day, cfg):
    """Reference prices for the target if the playbook's acquirer buys it (METHODOLOGY.md §5)"""
    acquirer = cfg["acquirer"]
    acq_close, acq_shares = peer_quote(acquirer, day)
    note = f"{acq_shares:,.0f}M shares, market data"
    if has_fundamentals(acquirer):
        # Prefer the share count from the acquirer's latest sourced balance sheet
        v = metrics.valuation(load_fundamentals(acquirer), acq_close, day)
        acq_shares = v.shares_m
        note = f"{acq_shares:,.0f}M shares per balance sheet {v.balance_sheet_date}"
    return acquisition_lines(ticker, close, float(cfg["target_diluted_shares_m"]), acquirer,
                             acq_close * acq_shares, tuple(cfg.get("gap_shares", (0.25, 0.5))),
                             cap_note=f"${acq_close:,.2f} × {note}")


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


def _cells(cells):
    return "| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in cells) + " |"


def render(ticker, day, memo_result, commentary, check, memo_check, revised, method=None, channel_check=None):
    memo_check = memo_check or Verification()
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
        lines.append(_cells([s["question"], DIRECTION_LABELS[s["direction"]], s["evidence"]]))
    lines += ["", "## Watch next week", ""] + [f"- {w}" for w in commentary.watch_next]
    lines += ["", "## News used", ""]
    lines += [f"- [{n['headline']}]({n['url']}): {n['outlet']}, {n['date']}" for n in commentary.news] or ["- none"]
    if commentary.dropped_news:
        lines += ["", "Dropped (URL not returned by any search, so the item couldn't be confirmed):"]
        lines += [f"- {n['headline']} ({n['outlet']})" for n in commentary.dropped_news]

    counts = (f"Commentary: {len(check.by_status('verified'))} verified, "
              f"{len(check.by_status('contradicted'))} contradicted, {len(check.by_status('unverified'))} unconfirmed.")
    if memo_result:
        counts += (f" Memo: {len(memo_check.by_status('verified'))} verified, "
                   f"{len(memo_check.by_status('contradicted'))} contradicted, "
                   f"{len(memo_check.by_status('unverified'))} unconfirmed.")
    lines += ["", "## Verification", "", counts, ""]
    if problems:
        lines += ["**Needs a look:**", ""] + _findings_table(problems) + [""]
    verified = check.by_status("verified") + memo_check.by_status("verified")
    lines += ["<details><summary>All verified claims</summary>", ""] + _findings_table(verified) + ["", "</details>", ""]

    if method is not None:
        lines += ["## Channel this week", "", method.summary, ""]
        if method.changed:
            lines += ["**Method changes proposed** (opened as a pull request on the playbook):", ""]
            lines += [f"- {c['what']}: {c['why']} (post {c['post_date']}: “{c['quote']}”)" for c in method.changes]
        elif method.rejected:
            lines.append(f"A playbook change was proposed but not accepted: {method.rejected}.")
        else:
            lines.append("No change to the method.")
        lines.append("")
        if channel_check and channel_check.findings:
            lines += ["**Fact check of the posts:**", ""] + _findings_table(channel_check.findings) + [""]

    if memo_result:
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


def method_review(ticker, playbook, playbook_path, methodology, factpack, client):
    """Learn from the author's posts; returns (review, fact check of the posts) or (None, None)"""
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token or not playbook.get("slack_channel") or not playbook.get("methodology_author"):
        return None, None
    from src.analysis.method import review_method
    from src.analysis.slack import author_posts

    posts = author_posts(playbook["slack_channel"], playbook["methodology_author"], token)
    if not posts:
        return None, None
    with open(playbook_path, encoding="utf-8") as f:
        playbook_text = f.read()
    review = review_method(posts, playbook_text, methodology, client)
    if review.changed and review.playbook_yaml.strip() != playbook_text.strip():
        with open(playbook_path, "w", encoding="utf-8") as f:
            f.write(review.playbook_yaml.rstrip() + "\n")
    else:
        review.changed = False
    channel_check = verify_report("\n".join(f"- {c}" for c in review.claims), factpack, client) if review.claims else None
    return review, channel_check


def run(ticker: str, client, methodology: str):
    playbook_path = os.path.join(ROOT_DIR, "playbooks", f"{ticker}.yaml")
    with open(playbook_path, encoding="utf-8") as f:
        playbook = yaml.safe_load(f)
    fund = load_fundamentals(ticker) if has_fundamentals(ticker) else None

    prices = price_history(ticker)
    day, close = prices[-1]
    peers = {}
    for peer in playbook.get("relative", []):
        try:
            peers[peer["ticker"]] = peer_quote(peer["ticker"], day)
        except Exception as e:
            print(f"  ! {peer['ticker']} quote unavailable: {e}", file=sys.stderr)
    extra, band_section = market_lines(ticker, playbook, prices, fund)
    own_shares = None if fund else shares_outstanding_m(ticker)
    market = weekly_section(fund, prices, peers, ticker=ticker, extra_lines=extra, shares_m=own_shares)
    if band_section:
        market += "\n" + "\n".join(band_section)
    if fund:
        factpack = build_factpack(fund, price=close, price_date=day, market_section=market)
        known_urls = {s["url"] for s in fund.sources.values()}
    else:
        factpack = build_market_factpack(ticker, market, playbook.get("company"))
        known_urls = set()

    memo_result = None
    if fund:
        print(f"{ticker}: memo")
        memo_result = run_analyst(factpack, playbook, client=client)
    memo = memo_result.memo if memo_result else ""

    print(f"{ticker}: commentary")
    commentary = write_commentary(factpack, memo, playbook, day, client, methodology=methodology)
    print(f"{ticker}: fact check")
    check = verify_report(commentary.text(), factpack, client, known_urls,
                          unsupported_numbers(commentary.text(), factpack))
    revised = False
    if check.problems:
        print(f"{ticker}: rewriting commentary ({len(check.problems)} problems)")
        commentary = write_commentary(factpack, memo, playbook, day, client,
                                      feedback=_feedback(check.problems), previous=commentary,
                                      methodology=methodology)
        check = verify_report(commentary.text(), factpack, client,
                              known_urls | {n["url"] for n in commentary.news},
                              unsupported_numbers(commentary.text(), factpack))
        revised = True

    memo_check = None
    if memo_result:
        print(f"{ticker}: memo fact check")
        memo_check = verify_report(memo_result.memo, factpack, client, known_urls, memo_result.unsupported_numbers)

    method, channel_check = None, None
    try:
        method, channel_check = method_review(ticker, playbook, playbook_path, methodology, factpack, client)
    except Exception as e:
        print(f"  ! method review failed for {ticker}: {e}", file=sys.stderr)

    out_dir = os.path.join(ROOT_DIR, "reports")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"{ticker}_factpack.md"), "w", encoding="utf-8") as f:
        f.write(factpack)
    with open(os.path.join(out_dir, f"{ticker}_weekly.md"), "w", encoding="utf-8") as f:
        f.write(render(ticker, day, memo_result, commentary, check, memo_check, revised, method, channel_check))
    with open(os.path.join(out_dir, f"{ticker}_weekly.json"), "w", encoding="utf-8") as f:
        json.dump({
            "ticker": ticker,
            "week_ending": day,
            "slack_channel": playbook.get("slack_channel"),
            "commentary": asdict(commentary),
            "commentary_findings": check.findings,
            "memo": memo,
            "memo_findings": memo_check.findings if memo_check else [],
            "method": asdict(method) if method else None,
            "clean": not (check.problems or (memo_check and memo_check.problems)),
        }, f, indent=2, ensure_ascii=False)
    if method and method.changed:
        with open(os.path.join(out_dir, "method_changes.md"), "a", encoding="utf-8") as f:
            f.write(f"## {ticker}\n\n{method.summary}\n\n")
            f.write("\n".join(f"- {c['what']}: {c['why']} (post {c['post_date']}: “{c['quote']}”)"
                              for c in method.changes) + "\n\n")
    print(f"{ticker}: wrote reports/{ticker}_weekly.md")


def main():
    import anthropic
    client = anthropic.Anthropic()
    tickers = [t.upper() for t in sys.argv[1:]] or tickers_with_playbooks()
    with open(METHODOLOGY_PATH, encoding="utf-8") as f:
        methodology = f.read()
    failed = []
    for ticker in tickers:
        try:
            run(ticker, client, methodology)
        except Exception as e:
            print(f"{ticker}: failed: {e}", file=sys.stderr)
            failed.append(ticker)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
