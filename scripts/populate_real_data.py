"""
Populate Database with Real Yahoo Finance Data
Fetches actual financial data from Yahoo Finance for all companies
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.yahoo_finance_fetcher import YahooFinanceDataFetcher  # noqa: E402
from scripts.load_segment_data import load_segment_data  # noqa: E402
from src.database_manager import MetricsDatabase  # noqa: E402
from src.query_interface import MetricsQuery  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def populate_real_data():
    """Populate database with real Yahoo Finance data"""
    
    companies = ["AMD", "CRM", "GOOG", "NVDA", "RH", "SPCX", "TSLA"]
    
    print("=" * 70)
    print("FETCHING REAL FINANCIAL DATA FROM YAHOO FINANCE")
    print("=" * 70)
    print(f"\nCompanies: {', '.join(companies)}")
    print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Initialize fetcher and database
    fetcher = YahooFinanceDataFetcher()
    db = MetricsDatabase()
    db.connect()
    
    # Recreate database schema
    print("\nInitializing database...")
    db.create_schema()
    
    successful = []
    failed = []
    total_metrics = 0
    
    # Fetch data for each company
    for ticker in companies:
        print("\n" + "=" * 70)
        print(f"PROCESSING: {ticker}")
        print("=" * 70)
        
        try:
            # Fetch data from Yahoo Finance
            data = fetcher.extract_metrics_from_financials(ticker)
            
            if 'error' in data:
                print(f"✗ Failed: {data['error']}")
                failed.append(ticker)
                continue
            
            # Insert company
            company_id = db.insert_company(
                ticker=ticker,
                cik=data.get('cik'),
                company_name=data.get('company_name', ticker)
            )
            
            print(f"\n✓ Company: {data.get('company_name', ticker)}")
            
            # Insert filings and metrics
            filings_count = 0
            metrics_count = 0
            
            for filing in data.get('filings', []):
                filing_id = db.insert_filing(
                    company_id=company_id,
                    filing_type=filing['filing_type'],
                    filing_date=filing['filing_date'],
                    document_url=f"https://finance.yahoo.com/quote/{ticker}/financials"
                )
                
                metrics = filing.get('metrics', {})
                if metrics:
                    db.insert_metrics(filing_id, metrics)
                    filings_count += 1
                    metrics_count += len(metrics)
                    print(f"  ✓ {filing['filing_type']} ({filing['filing_date']}): {len(metrics)} metrics")
            
            print(f"\n✓ {ticker} completed: {filings_count} filings, {metrics_count} metrics")
            successful.append(ticker)
            total_metrics += metrics_count
            
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            print(f"\n✗ Error processing {ticker}: {e}")
            import traceback
            traceback.print_exc()
            failed.append(ticker)
    
    db.close()

    # Overlay operating-segment breakdowns (not available from Yahoo Finance)
    print("\n" + "=" * 70)
    print("LOADING SEGMENT REVENUE OVERLAYS")
    print("=" * 70)
    try:
        load_segment_data()
    except Exception as e:
        print(f"✗ Segment load error: {e}")

    # Export to Excel (re-open so segment rows are included)
    print("\n" + "=" * 70)
    print("EXPORTING RESULTS")
    print("=" * 70)

    db = MetricsDatabase()
    db.connect()
    try:
        excel_path = os.path.join(DATA_DIR, 'financial_metrics_real.xlsx')
        db.export_to_excel(excel_path)
        print(f"✓ Excel exported to: {excel_path}")
    except Exception as e:
        print(f"✗ Excel export error: {e}")
    
    db.close()
    
    # Generate summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\n✓ Successful: {len(successful)} companies")
    if successful:
        print(f"   {', '.join(successful)}")
    
    if failed:
        print(f"\n✗ Failed: {len(failed)} companies")
        print(f"   {', '.join(failed)}")
    
    print(f"\n📊 Total metrics collected: {total_metrics}")
    
    # Verify database contents
    print("\n" + "=" * 70)
    print("DATABASE CONTENTS")
    print("=" * 70)
    
    query = MetricsQuery()
    
    companies_df = query.get_all_companies()
    print(f"\n✓ Companies in database: {len(companies_df)}")
    
    for _, row in companies_df.iterrows():
        df = query.db.get_company_metrics(row['ticker'])
        if not df.empty:
            latest = df.iloc[0]
            print(f"\n{row['ticker']:6s} - {row['company_name'][:40]}")
            print(f"         Filings: {len(df)}")
            if 'total_revenue' in latest and pd.notna(latest['total_revenue']):
                print(f"         Latest Revenue: ${latest['total_revenue']:,.0f}")
            if 'net_income' in latest and pd.notna(latest['net_income']):
                print(f"         Latest Net Income: ${latest['net_income']:,.0f}")
    
    metrics = query.get_all_metric_names()
    print(f"\n✓ Unique metrics: {len(metrics)}")
    
    query.close()
    
    print("\n" + "=" * 70)
    print("REAL DATA COLLECTION COMPLETE")
    print("=" * 70)
    print("\n📁 Output files:")
    print("   - data/financial_metrics.db         (SQLite database with REAL data)")
    print("   - data/financial_metrics_real.xlsx  (Excel export)")
    print("\n💡 Next steps:")
    print("   - Run: python3 scripts/demo.py")
    print("   - Explore: data/financial_metrics_real.xlsx")
    print("   - Launch the web app: python3 app.py")


if __name__ == "__main__":
    import pandas as pd
    populate_real_data()
