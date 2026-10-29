"""
Tests for sourced fundamentals and the analyst metrics.

Pins SpaceX figures to the company releases and checks the valuation math
against the multiples posted in #stock-spcx (Oct 20, 2026).
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.analysis import metrics  # noqa: E402
from src.analysis.factpack import build_factpack  # noqa: E402
from src.analysis.fundamentals import load_fundamentals  # noqa: E402


def close(a, b, tol=0.05):
    return a is not None and abs(a - b) <= tol


def test_load_and_derive():
    """Data file is internally consistent; unprinted quarters derive correctly"""
    print("Testing SPCX fundamentals load and derivation...")
    fund = load_fundamentals("SPCX")

    q4 = fund.get("2025Q4", "revenue")
    q1 = fund.get("2025Q1", "revenue")
    checks = [
        (q4.value == 4960 and q4.derived_from == "2025FY − 2025-9M", "Q4 2025 revenue = FY - 9M"),
        (q1.value == 4067 and q1.derived, "Q1 2025 revenue = H1 - Q2"),
        (fund.get("2025Q4", "revenue", "ai").value == 923, "Q4 2025 AI revenue"),
        (not fund.get("2026Q3", "revenue").derived, "Q3 2026 revenue is reported"),
        (fund.quarters() == ["2025Q1", "2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q2", "2026Q3"],
         "seven quarters available"),
    ]
    for ok, label in checks:
        print(f"  {'✓' if ok else '✗'} {label}")
    return all(ok for ok, _ in checks)


def test_inconsistent_data_fails():
    """A typo that breaks segment or period sums is rejected"""
    print("\nTesting that inconsistent data is rejected...")
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "fundamentals", "SPCX.yaml")
    with open(path, encoding="utf-8") as f:
        text = f.read().replace("connectivity: 5248, ai: 7560", "connectivity: 5284, ai: 7560", 1)
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tmp:
        tmp.write(text)
    try:
        load_fundamentals("SPCX", path=tmp.name)
        print("  ✗ typo was not caught")
        return False
    except ValueError as e:
        print(f"  ✓ rejected: {str(e).splitlines()[1].strip()}")
        return True
    finally:
        os.remove(tmp.name)


def test_valuation_matches_channel():
    """Reproduce the multiples posted in #stock-spcx with the same inputs"""
    print("\nTesting valuation against #stock-spcx multiples...")
    fund = load_fundamentals("SPCX")

    # Inputs from the chart footnote: 13,181.8M shares, $60.6B net cash, $148 close
    v = metrics.valuation(fund, 148, "2026-10-20", shares_m=13181.8, net_cash=60645)
    checks = [
        (v.ttm_revenue == 32043, f"TTM revenue $32,043M (got {v.ttm_revenue})"),
        (close(v.mcap_to_ttm_revenue, 60.9), f"mcap / TTM ≈ 61x (got {v.mcap_to_ttm_revenue:.1f})"),
        (close(v.ev_to_ttm_revenue, 59.0), f"EV / TTM ≈ 59x (got {v.ev_to_ttm_revenue:.1f})"),
        (close(v.ev_to_run_rate_revenue, 32.4), f"EV / run-rate ≈ 32x (got {v.ev_to_run_rate_revenue:.1f})"),
    ]

    # Default inputs use the Sep 30 balance sheet instead
    latest = metrics.valuation(fund, 148, "2026-10-20")
    checks += [
        (latest.balance_sheet_date == "2026-09-30", "uses Sep 30 balance sheet"),
        (latest.shares_m == 13579 and latest.net_cash == 51011, "Sep 30 shares and net cash"),
    ]

    # Before the Q3 release only quarters through Q2 are known
    early = metrics.valuation(fund, 120, "2026-09-15")
    checks.append((early.ttm_end == "2026Q2" and early.balance_sheet_date == "2026-06-30",
                   "valuation date ignores later releases"))

    for ok, label in checks:
        print(f"  {'✓' if ok else '✗'} {label}")
    return all(ok for ok, _ in checks)


def test_surprises_and_growth():
    print("\nTesting estimate surprises and growth...")
    fund = load_fundamentals("SPCX")
    s = {x.item: x.pct for x in metrics.surprises(fund, "2026Q3")}
    checks = [
        (close(s.get("ai"), 16.8, 0.1), "AI beat ≈ +17%"),
        (close(s.get("space"), 21.0, 0.1), "Space beat ≈ +21%"),
        (close(s.get("total"), 14.6, 0.1), "Total beat ≈ +15%"),
        (close(metrics.growth(fund, "2026Q3", "revenue"), 161.4, 0.1), "revenue +161% YoY"),
        (close(metrics.margin(fund, "2026Q3", "operating_income", "connectivity"), 45.1, 0.1),
         "Connectivity operating margin 45%"),
    ]
    for ok, label in checks:
        print(f"  {'✓' if ok else '✗'} {label}")
    return all(ok for ok, _ in checks)


def test_factpack():
    print("\nTesting fact pack rendering...")
    text = build_factpack(load_fundamentals("SPCX"), price=148, price_date="2026-10-20")
    checks = [
        ("$14.57B" in text, "Q3 total revenue shown"),
        ("$923M†" in text, "derived figures marked †"),
        ("Estimate‡" in text, "estimates marked ‡"),
        ("EV / TTM revenue: 61.1x" in text, "valuation section"),
        ("q3_2026_release" in text, "sources listed"),
    ]
    for ok, label in checks:
        print(f"  {'✓' if ok else '✗'} {label}")
    return all(ok for ok, _ in checks)


class _Block:
    def __init__(self, text):
        self.type, self.text = "text", text


class _Message:
    def __init__(self, text):
        self.stop_reason, self.stop_details, self.content = "end_turn", None, [_Block(text)]


class _FakeMessages:
    """Stands in for client.beta.messages: scripted memos and reviews"""

    def __init__(self, memos, reviews):
        self.memos, self.reviews, self.prompts = list(memos), list(reviews), []

    def stream(self, **kwargs):
        self.prompts.append(kwargs["messages"][0]["content"])
        message = _Message(self.memos.pop(0))

        class _Stream:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def get_final_message(self):
                return message
        return _Stream()

    def create(self, **kwargs):
        import json
        return _Message(json.dumps(self.reviews.pop(0)))


def test_agent_pipeline():
    """Unsupported numbers and reviewer issues trigger one revision"""
    print("\nTesting analyst / reviewer pipeline (stubbed model)...")
    from types import SimpleNamespace
    from src.analysis.agent import run_analyst, unsupported_numbers

    factpack = build_factpack(load_fundamentals("SPCX"), price=148, price_date="2026-10-20")
    first = "Revenue reached $14.6B [q3_2026_release], up 3x. ARPU was $69, then $66."
    second = "Revenue reached $14.57B [q3_2026_release], +161.4% YoY; 13.6M subscribers."
    fake = _FakeMessages(
        memos=[first, second],
        reviews=[{"verdict": "revise", "issues": [{"quote": "up 3x", "problem": "not in fact pack", "fix": "use +161.4%"}]},
                 {"verdict": "pass", "issues": []}],
    )
    result = run_analyst(factpack, {"ticker": "SPCX"}, client=SimpleNamespace(beta=SimpleNamespace(messages=fake)))

    checks = [
        (unsupported_numbers(first, factpack) == ["$14.6B", "3x"], "rounded / invented figures flagged"),
        (result.revised and result.memo == second, "memo revised once"),
        ("$14.6B" in fake.prompts[1] and "up 3x" in fake.prompts[1], "feedback passed to revision"),
        (result.clean, "final memo is clean"),
    ]
    for ok, label in checks:
        print(f"  {'✓' if ok else '✗'} {label}")
    return all(ok for ok, _ in checks)


def test_weekly_section():
    """Weekly market lines: price changes, multiples vs a week earlier, peer premium"""
    print("\nTesting weekly market section...")
    from src.analysis.weekly import weekly_section
    fund = load_fundamentals("SPCX")
    prices = [("2026-09-25", 120.0), ("2026-10-16", 140.0), ("2026-10-23", 148.0)]
    text = weekly_section(fund, prices, peers={"TSLA": (400.0, 3200.0)})
    factpack = build_factpack(fund, price=148, price_date="2026-10-23", market_section=text)
    checks = [
        ("1-week change: +5.7% (from $140.00 on 2026-10-16)" in text, "1-week change"),
        ("4-week change: +23.3% (from $120.00 on 2026-09-25)" in text, "4-week change"),
        ("EV / TTM revenue: 61.1x (a week earlier at the same fundamentals: 57.7x)" in text,
         "multiple vs a week earlier"),
        ("$1.28T (3,200M shares)" in text, "peer market cap"),
        ("1.57x (57.0% premium)" in text, "premium over peer"),
        ("## Week ending 2026-10-23 [market_data]" in factpack and "`market_data`" in factpack,
         "section and source in fact pack"),
    ]
    for ok, label in checks:
        print(f"  {'✓' if ok else '✗'} {label}")
    if not all(ok for ok, _ in checks):
        print(text)
    return all(ok for ok, _ in checks)


class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _ToolMessages:
    """Stands in for client.beta.messages in tool loops: scripted turns"""

    def __init__(self, turns):
        self.turns, self.requests = list(turns), []

    def stream(self, **kwargs):
        self.requests.append(kwargs)
        stop, content = self.turns.pop(0)
        message = _Obj(stop_reason=stop, stop_details=None, content=content)

        class _Stream:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def get_final_message(self):
                return message
        return _Stream()


def _client(turns):
    from types import SimpleNamespace
    fake = _ToolMessages(turns)
    return SimpleNamespace(beta=SimpleNamespace(messages=fake)), fake


def _search_result(url):
    return _Obj(type="web_search_tool_result", content=[_Obj(type="web_search_result", url=url, title="t")])


def test_verifier():
    """Findings come back through the tool; unreturned URLs can't verify a claim"""
    print("\nTesting verifier agent (stubbed model)...")
    from src.analysis.verifier import verify_report
    real, fake_url = "https://example.com/real", "https://example.com/made-up"

    def finding(claim, status, basis, url):
        return {"claim": claim, "status": status, "basis": basis, "source_url": url, "evidence": "e", "note": ""}
    findings = [
        finding("Revenue $14.57B", "verified", "fact_pack", ""),
        finding("Lockup ends Dec 1", "verified", "secondary_source", real),
        finding("Starship flew Oct 20", "verified", "primary_source", fake_url),
        finding("Tesla 800 robotaxis", "contradicted", "primary_source", real),
    ]
    client, fake = _client([
        ("pause_turn", [_search_result(real)]),
        ("tool_use", [_Obj(type="tool_use", id="t1", name="record_findings", input={"findings": findings})]),
        ("end_turn", [_Obj(type="text", text="Done.")]),
    ])
    check = verify_report("report", "factpack", client, extra_figures=["800"])
    statuses = [f["status"] for f in check.findings]
    tool_results = [m["content"][0] for m in fake.requests[-1]["messages"]
                    if m["role"] == "user" and isinstance(m["content"], list)]
    checks = [
        (statuses == ["verified", "verified", "unverified", "contradicted"], "made-up URL downgraded"),
        (len(fake.requests) == 3, "pause_turn resumed and tool result sent"),
        (tool_results and tool_results[0]["tool_use_id"] == "t1", "tool result answers the call"),
        ("800" in fake.requests[0]["messages"][0]["content"], "unsupported figures passed to verifier"),
        (len(check.problems) == 2 and not check.clean, "problems counted"),
    ]
    for ok, label in checks:
        print(f"  {'✓' if ok else '✗'} {label}")
    return all(ok for ok, _ in checks)


def test_commentary():
    """Commentary comes back structured; news with unreturned URLs is dropped"""
    print("\nTesting commentary agent (stubbed model)...")
    from src.analysis.commentary import write_commentary
    real = "https://example.com/news"
    submitted = {
        "slack_post": "*SpaceX week ending Oct 23*\n• Close $148.00",
        "scorecard": [{"question": "Is Starlink compounding?", "direction": "no_new_data", "evidence": "No release."}],
        "watch_next": ["Lockup expiry"],
        "news": [
            {"headline": "Real", "outlet": "Reuters", "date": "2026-10-22", "url": real},
            {"headline": "Invented", "outlet": "Blog", "date": "2026-10-22", "url": "https://example.com/nope"},
        ],
    }
    client, fake = _client([
        ("tool_use", [_search_result(real),
                      _Obj(type="tool_use", id="c1", name="submit_commentary", input=submitted)]),
        ("end_turn", []),
    ])
    c = write_commentary("factpack", "memo", {"ticker": "SPCX"}, "2026-10-23", client)
    revision_client, revision = _client([
        ("tool_use", [_Obj(type="tool_use", id="c2", name="submit_commentary", input=dict(submitted, news=c.news))]),
        ("end_turn", []),
    ])
    c2 = write_commentary("factpack", "memo", {"ticker": "SPCX"}, "2026-10-23", revision_client,
                          feedback=["“x” (unverified): not found"], previous=c)
    checks = [
        ([n["headline"] for n in c.news] == ["Real"], "news with a returned URL kept"),
        ([n["headline"] for n in c.dropped_news] == ["Invented"], "news with an unreturned URL dropped"),
        ("Close $148.00" in c.text() and "Lockup expiry" in c.text(), "text covers post and watch list"),
        ("not found" in revision.requests[0]["messages"][0]["content"], "fact-check feedback in revision"),
        ([n["headline"] for n in c2.news] == ["Real"], "revision keeps already-checked news"),
    ]
    for ok, label in checks:
        print(f"  {'✓' if ok else '✗'} {label}")
    return all(ok for ok, _ in checks)


def test_band_and_relative():
    """Valuation band (estimate range × multiple range) and relative performance"""
    print("\nTesting valuation band and relative performance...")
    from src.analysis.band import band_lines, relative_lines, valuation_band, zone
    from src.analysis.factpack import build_market_factpack
    from src.analysis.weekly import weekly_section
    # RH P/E range chart in #stock-rh (Oct 22): consensus EPS FY26E $5.36, FY27E $8.52, 20x / 30x
    band = valuation_band({"low": 4.9, "avg": 5.36, "high": 5.9, "analysts": 12}, "0y", "eps", 20, 30)
    band27 = valuation_band({"low": 7.5, "avg": 8.52, "high": 9.6}, "+1y", "eps", 20, 30)
    lines = "\n".join(band_lines([band, band27], 138.03, "market_data"))
    rel = relative_lines("RH", [("2026-10-07", 120.0), ("2026-10-22", 137.88)],
                         {"^GSPC": [("2026-10-07", 6000.0), ("2026-10-22", 5922.0)]}, "2026-10-07")
    market = weekly_section(None, [("2026-10-15", 130.0), ("2026-10-22", 138.0)], ticker="RH",
                            extra_lines=rel, shares_m=18.7, peers={"WSM": (200.0, 125.0)})
    pack = build_market_factpack("RH", market)
    from src.analysis.band import acquisition_lines
    acq = acquisition_lines("TSLA", 400.0, 3500.0, "SPCX", 2_100_000.0, cap_note="test")
    checks = [
        ("gap $700.00B, $200.00 per TSLA share" in acq[0], "acquisition gap per target share"),
        ("25% line: $450.00" in acq[1] and "50% line: $500.00" in acq[2], "acquisition reference lines"),
        (round(band.consensus_low, 2) == 107.2 and round(band.consensus_high, 2) == 160.8
         and round(band27.consensus_low, 2) == 170.4 and round(band27.consensus_high, 2) == 255.6,
         "band on the average estimate matches the channel's chart"),
        ((round(band.low, 2), round(band.high, 2)) == (98.0, 177.0), "full estimate range"),
        (abs(band.position(138.03) - (138.03 - 107.2) / 53.6 * 100) < 1e-9, "position on the average-estimate band"),
        (zone(10) == "near the low end" and zone(80) == "near the high end" and zone(120) == "above the band",
         "zones"),
        ("EPS avg $5.36‡ (range $4.90 – $5.90‡, 12 analysts) × 20x – 30x P/E" in lines, "band estimate line"),
        ("Band: $107.20 – $160.80 (full estimate range: $98.00 – $177.00)" in lines, "band line"),
        ("Current P/E on the average estimate: 25.8x" in lines
         and "Current P/E on the average estimate: 16.2x" in lines, "current P/E matches the chart"),
        ("sits at 58% of the band: mid band" in lines and "sits at -38% of the band: below the band" in lines,
         "band position lines"),
        ("vs S&P 500: +16.2 pts (RH +14.9%, S&P 500 -1.3%)" in rel[1], "relative performance in channel form"),
        ("RH market cap: $2.58B (18.7M shares)" in market and "0.10x (89.7% discount)" in market,
         "market-only peer gap"),
        ("No sourced quarterly fundamentals" in pack and "`market_data`" in pack, "market-only fact pack"),
    ]
    for ok, label in checks:
        print(f"  {'✓' if ok else '✗'} {label}")
    if not all(ok for ok, _ in checks):
        print(lines, rel, market, sep="\n")
    return all(ok for ok, _ in checks)


def test_method_review():
    """Method review accepts a valid revised playbook and rejects one that drops keys"""
    print("\nTesting method review (stubbed model)...")
    import json
    from types import SimpleNamespace
    from src.analysis.method import review_method
    from src.analysis.slack import Post
    playbook = "ticker: RH\n# band\nmethod:\n  valuation_band: {basis: eps}\nthesis_questions: [a]\n"

    def client_returning(result):
        calls = []

        def create(**kwargs):
            calls.append(kwargs)
            return _Message(json.dumps(result))
        return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create))), calls

    base = {"summary": "Trimmed half at 138.", "changes": [{"what": "x", "why": "y", "quote": "q", "post_date": "2026-10-22"}],
            "claims": ["RH rose 14.9% since Oct 7"]}
    good, calls = client_returning(dict(base, changed=True, playbook_yaml=playbook + "kpis: [margin]  # 2026-10-22\n"))
    posts = [Post("1792771200.0", "Reducing risk by 50%", images=[("image/png", b"png")])]
    accepted = review_method(posts, playbook, "method", good)
    bad, _ = client_returning(dict(base, changed=True, playbook_yaml="ticker: RH\n"))
    rejected = review_method(posts, playbook, "method", bad)
    content = calls[0]["messages"][0]["content"]
    checks = [
        (accepted.changed and "kpis" in accepted.playbook_yaml, "valid revision accepted"),
        (not rejected.changed and "drops keys" in rejected.rejected, "revision dropping keys rejected"),
        (content[0]["type"] == "image" and "Reducing risk" in content[-1]["text"], "charts and text sent"),
        (accepted.claims == ["RH rose 14.9% since Oct 7"], "claims passed through for fact check"),
    ]
    for ok, label in checks:
        print(f"  {'✓' if ok else '✗'} {label}")
    return all(ok for ok, _ in checks)


if __name__ == "__main__":
    print("=" * 60)
    print("ANALYST DATA LAYER - TEST SUITE")
    print("=" * 60)
    results = [
        ("Load and derive", test_load_and_derive()),
        ("Inconsistent data rejected", test_inconsistent_data_fails()),
        ("Valuation vs channel", test_valuation_matches_channel()),
        ("Surprises and growth", test_surprises_and_growth()),
        ("Fact pack", test_factpack()),
        ("Agent pipeline", test_agent_pipeline()),
        ("Weekly section", test_weekly_section()),
        ("Verifier agent", test_verifier()),
        ("Commentary agent", test_commentary()),
        ("Band and relative", test_band_and_relative()),
        ("Method review", test_method_review()),
    ]
    print("\n" + "=" * 60)
    for name, passed in results:
        print(f"{name:30s}: {'✓ PASSED' if passed else '✗ FAILED'}")
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{len(results)} tests passed")
    sys.exit(0 if passed == len(results) else 1)
