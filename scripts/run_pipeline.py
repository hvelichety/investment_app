"""
Robust Data Collection Pipeline with Progress Tracking
"""

import json
import time
import sys
import os
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.sec_data_fetcher import SECDataFetcher  # noqa: E402
from scripts.metrics_parser import MetricsParser  # noqa: E402
from src.database_manager import MetricsDatabase  # noqa: E402


class RobustPipeline:
    def __init__(self):
        self.fetcher = SECDataFetcher()
        self.parser = MetricsParser()
        self.db = MetricsDatabase()
        self.progress_file = "pipeline_progress.json"
        
    def load_progress(self) -> Dict:
        """Load progress from previous run"""
        if os.path.exists(self.progress_file):
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {"completed_tickers": [], "failed_tickers": []}
    
    def save_progress(self, progress: Dict):
        """Save current progress"""
        with open(self.progress_file, 'w') as f:
            json.dump(progress, f, indent=2)
    
    def fetch_company_data(self, ticker: str) -> Dict:
        """Fetch data for a single company with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"\nAttempt {attempt + 1}/{max_retries} for {ticker}...")
                data = self.fetcher.get_company_data(ticker)
                
                if 'error' not in data:
                    return data
                else:
                    print(f"  Error in data: {data['error']}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
            except Exception as e:
                print(f"  Exception: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
        
        return {"ticker": ticker, "error": "Max retries exceeded"}
    
    def run_pipeline(self, tickers: List[str], skip_completed: bool = True):
        """Run the complete pipeline with progress tracking"""
        print("=" * 70)
        print("ROBUST FINANCIAL METRICS PIPELINE")
        print("=" * 70)
        print(f"Companies: {', '.join(tickers)}")
        print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        progress = self.load_progress()
        
        if skip_completed:
            tickers = [t for t in tickers if t not in progress['completed_tickers']]
            print(f"Skipping already completed: {progress['completed_tickers']}")
            print(f"Processing: {tickers}\n")
        
        self.db.connect()
        self.db.create_schema()
        
        all_data = {}
        
        for ticker in tickers:
            print("\n" + "=" * 70)
            print(f"PROCESSING: {ticker}")
            print("=" * 70)
            
            try:
                raw_data = self.fetch_company_data(ticker)
                all_data[ticker] = raw_data
                
                if 'error' in raw_data:
                    print(f"✗ Failed to fetch data for {ticker}")
                    progress['failed_tickers'].append(ticker)
                    self.save_progress(progress)
                    continue
                
                with open(f'data_{ticker}.json', 'w') as f:
                    json.dump(raw_data, f, indent=2)
                print(f"✓ Raw data saved to data_{ticker}.json")
                
                print(f"\nParsing metrics for {ticker}...")
                parsed_data = self.parser.parse_company_filings(raw_data)
                
                with open(f'metrics_{ticker}.json', 'w') as f:
                    json.dump(parsed_data, f, indent=2)
                print(f"✓ Parsed metrics saved to metrics_{ticker}.json")
                
                print(f"\nInserting {ticker} into database...")
                company_id = self.db.insert_company(
                    ticker=ticker,
                    cik=parsed_data.get('cik')
                )
                
                metrics_inserted = 0
                filings_parsed = parsed_data.get('filings_parsed', [])
                
                for filing_data in filings_parsed:
                    filing_id = self.db.insert_filing(
                        company_id=company_id,
                        filing_type=filing_data['filing_type'],
                        filing_date=filing_data['filing_date']
                    )
                    
                    metrics = filing_data.get('metrics', {})
                    if metrics:
                        self.db.insert_metrics(filing_id, metrics)
                        metrics_inserted += len(metrics)
                        print(f"  ✓ {len(metrics)} metrics from {filing_data['filing_type']} ({filing_data['filing_date']})")
                
                print(f"\n✓ {ticker} completed - {metrics_inserted} total metrics inserted")
                
                progress['completed_tickers'].append(ticker)
                self.save_progress(progress)
                
                time.sleep(1)
                
            except Exception as e:
                print(f"\n✗ Error processing {ticker}: {e}")
                import traceback
                traceback.print_exc()
                progress['failed_tickers'].append(ticker)
                self.save_progress(progress)
                continue
        
        print("\n" + "=" * 70)
        print("EXPORTING RESULTS")
        print("=" * 70)
        
        try:
            self.db.export_to_excel('financial_metrics.xlsx')
            print("✓ Results exported to financial_metrics.xlsx")
        except Exception as e:
            print(f"✗ Excel export error: {e}")
        
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Completed: {len(progress['completed_tickers'])} companies")
        print(f"  {', '.join(progress['completed_tickers'])}")
        
        if progress['failed_tickers']:
            print(f"\nFailed: {len(progress['failed_tickers'])} companies")
            print(f"  {', '.join(progress['failed_tickers'])}")
        
        print("\n" + "=" * 70)
        print("DATABASE CONTENTS")
        print("=" * 70)
        
        for ticker in progress['completed_tickers']:
            try:
                df = self.db.get_company_metrics(ticker)
                if not df.empty:
                    non_null = df.count()
                    metrics_count = sum(1 for col in df.columns if df[col].notna().any() and col not in ['ticker', 'filing_type', 'filing_date'])
                    print(f"{ticker:6s}: {len(df)} filings, {metrics_count} metrics with data")
            except Exception as e:
                print(f"{ticker:6s}: Error - {e}")
        
        self.db.close()
        
        print("\n" + "=" * 70)
        print("OUTPUT FILES")
        print("=" * 70)
        print("  - financial_metrics.db    (SQLite database)")
        print("  - financial_metrics.xlsx  (Excel export)")
        print("  - data_*.json             (Raw SEC data per company)")
        print("  - metrics_*.json          (Parsed metrics per company)")
        print("  - pipeline_progress.json  (Progress tracking)")


if __name__ == "__main__":
    companies = ["AMD", "CRM", "GOOG", "NVDA", "RH", "SPCX", "TSLA"]
    
    pipeline = RobustPipeline()
    pipeline.run_pipeline(companies)
