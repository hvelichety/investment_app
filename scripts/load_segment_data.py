"""
Load operating-segment revenue overlays into the database.

Segment detail (e.g. SPCX Connectivity / Space / AI) is maintained in
data/segment_metrics.json and applied after Yahoo Finance populate, since
Yahoo does not provide this breakdown.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database_manager import MetricsDatabase  # noqa: E402

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEGMENT_FILE = os.path.join(ROOT_DIR, "data", "segment_metrics.json")


def _find_filing_id(db: MetricsDatabase, ticker: str, filing_date: str):
    db.cursor.execute(
        """
        SELECT f.filing_id
        FROM filings f
        JOIN companies c ON f.company_id = c.company_id
        WHERE c.ticker = ? AND f.filing_date = ?
        ORDER BY f.filing_id DESC
        LIMIT 1
        """,
        (ticker, filing_date),
    )
    row = db.cursor.fetchone()
    return row[0] if row else None


def load_segment_data(db_path: str = None, segment_file: str = SEGMENT_FILE) -> int:
    """Ensure schema exists and upsert segment rows. Returns rows written."""
    if not os.path.exists(segment_file):
        print(f"Segment file not found: {segment_file}")
        return 0

    with open(segment_file, "r", encoding="utf-8") as f:
        payload = json.load(f)

    db = MetricsDatabase(db_path)
    db.connect()
    db.create_schema()

    written = 0
    companies = payload.get("companies", {})

    for ticker, company in companies.items():
        for year, year_data in company.get("years", {}).items():
            filing_date = year_data.get("filing_date") or f"{year}-12-31"
            segments = year_data.get("segments") or []
            if not segments:
                continue

            filing_id = _find_filing_id(db, ticker, filing_date)
            if filing_id is None:
                # Create a lightweight filing shell so segment data can still live
                # in the DB even if Yahoo populate missed this ticker/year.
                company_id = db.insert_company(
                    ticker=ticker,
                    company_name=company.get("company_name", ticker),
                )
                filing_id = db.insert_filing(
                    company_id=company_id,
                    filing_type="SEGMENT",
                    filing_date=filing_date,
                    document_url=None,
                )
                print(f"  + Created filing shell for {ticker} {filing_date}")

            db.insert_segment_metrics(filing_id, segments)
            written += len(segments)
            print(f"  ✓ {ticker} {filing_date}: {len(segments)} segments")

    db.close()
    print(f"✓ Loaded {written} segment rows from {os.path.basename(segment_file)}")
    return written


if __name__ == "__main__":
    load_segment_data()
