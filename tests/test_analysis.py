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
    ]
    print("\n" + "=" * 60)
    for name, passed in results:
        print(f"{name:30s}: {'✓ PASSED' if passed else '✗ FAILED'}")
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{len(results)} tests passed")
    sys.exit(0 if passed == len(results) else 1)
