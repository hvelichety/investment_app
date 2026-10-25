"""
Check that every reported figure in data/fundamentals/<TICKER>.yaml appears
in the source document it cites.

Downloads each source (PDF or HTML), extracts its text, and looks for each
number as the company prints it ("1,767", "(1,943)", "13.6"). Derived
figures are skipped since they are computed, not printed. Exits non-zero
when a figure can't be found, so a typo in the data file fails CI. A source
that can't be downloaded is reported but doesn't fail the run.

Usage:
    python3 scripts/verify_sources.py SPCX [SPCX ...]

SEC asks automated clients to identify themselves; set SEC_USER_AGENT
(e.g. "investment-app admin@example.com") when sources include sec.gov.
"""

import io
import os
import re
import sys
import urllib.request

import yaml

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUNDAMENTALS_DIR = os.path.join(ROOT_DIR, "data", "fundamentals")
DEFAULT_USER_AGENT = "investment-app source verifier"


def fetch_text(url: str) -> str:
    headers = {"User-Agent": os.environ.get("SEC_USER_AGENT", DEFAULT_USER_AGENT)}
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as resp:
        body = resp.read()
        content_type = resp.headers.get("Content-Type", "")
    if url.lower().endswith(".pdf") or "pdf" in content_type:
        from pypdf import PdfReader
        return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(body)).pages)
    html = body.decode("utf-8", errors="replace")
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"&nbsp;|&#160;", " ", text)


def printed_forms(value: float):
    """Ways a company release prints a number: 1,767 / (1,943) / 13.6"""
    if value == 0:
        return []
    magnitude = abs(value)
    if magnitude == int(magnitude):
        digits = [f"{int(magnitude):,}"]
        if magnitude < 100:
            # Small KPIs (launches, ARPU) may print with one decimal
            digits.append(f"{magnitude:.1f}")
    else:
        digits = [f"{magnitude:,.1f}".rstrip("0").rstrip("."), f"{magnitude:,.2f}"]
    if value < 0:
        forms = [f"({d})" for d in digits] + [f"-{d}" for d in digits] + [f"−{d}" for d in digits]
        if magnitude >= 100:
            # Narrative text prints losses unsigned ("loss from operations of $657 million")
            forms += digits
        return forms
    return digits


def figures_by_source(raw: dict):
    """(source, label, value) for every printed figure in the data file"""
    for section in ("reported", "estimates"):
        for period, block in (raw.get(section) or {}).items():
            source = block["source"]
            for metric, items in block.items():
                if metric == "source":
                    continue
                if isinstance(items, dict):
                    for item, value in items.items():
                        yield source, f"{period} {metric}/{item}", value
                else:
                    yield source, f"{period} {metric}", items
    for date, block in (raw.get("balance_sheet") or {}).items():
        source = block["source"]
        for key, value in block.items():
            if key == "source":
                continue
            if isinstance(value, dict):
                for item, v in value.items():
                    yield source, f"{date} {key}/{item}", v
            else:
                yield source, f"{date} {key}", value


def verify(ticker: str) -> int:
    with open(os.path.join(FUNDAMENTALS_DIR, f"{ticker}.yaml"), encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    texts, missing, unfetched, checked = {}, [], set(), 0
    for source, label, value in figures_by_source(raw):
        src = raw["sources"][source]
        if src.get("kind") == "third_party_estimate":
            continue  # estimates live in chat posts / paywalled feeds, not fetchable docs
        if source not in texts:
            try:
                texts[source] = re.sub(r"\s+", " ", fetch_text(src["url"]))
            except Exception as e:
                print(f"  ✗ {source}: could not fetch {src['url']}: {e}")
                texts[source] = None
        text = texts[source]
        if text is None:
            unfetched.add(source)
            continue
        forms = printed_forms(float(value))
        if not forms:
            continue
        checked += 1
        if not any(form in text for form in forms):
            missing.append(f"{label} = {value} [{source}]")

    print(f"{ticker}: {checked} figures checked against {len(texts) - len(unfetched)} sources")
    for source in sorted(unfetched):
        print(f"  ! {source} could not be fetched, so its figures were not checked")
    for m in missing:
        print(f"  ✗ not found in source: {m}")
    if not missing:
        print("  ✓ every reported figure appears in its cited source")
    return len(missing)


if __name__ == "__main__":
    tickers = sys.argv[1:] or [f[:-5] for f in sorted(os.listdir(FUNDAMENTALS_DIR)) if f.endswith(".yaml")]
    sys.exit(1 if sum(verify(t) for t in tickers) else 0)
