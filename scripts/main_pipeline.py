"""
Main Data Collection Pipeline
Orchestrates the complete data collection, parsing, and database population process
"""

import json
import os
import time
import sys
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.sec_data_fetcher import SECDataFetcher  # noqa: E402
from scripts.metrics_parser import MetricsParser  # noqa: E402
from src.database_manager import MetricsDatabase  # noqa: E402


class DataPipeline:
    def __init__(self):
        self.fetcher = SECDataFetcher()
        self.parser = MetricsParser()
        self.db = MetricsDatabase()
        
    def fetch_sec_data(self, tickers: List[str]) -> Dict:
        """Fetch SEC filing data for all companies"""
        print("=" * 60)
        print("STEP 1: Fetching SEC Filing Data")
        print("=" * 60)
        
        all_data = {}
        for ticker in tickers:
            try:
                data = self.fetcher.get_company_data(ticker)
                all_data[ticker] = data
                time.sleep(0.5)
            except Exception as e:
                print(f"Error fetching data for {ticker}: {e}")
                all_data[ticker] = {"ticker": ticker, "error": str(e)}
        
        with open('sec_data_raw.json', 'w') as f:
            json.dump(all_data, f, indent=2)
        
        print("\n✓ SEC data saved to sec_data_raw.json")
        return all_data
    
    def parse_metrics(self, raw_data: Dict) -> Dict:
        """Parse metrics from raw filing data"""
        print("\n" + "=" * 60)
        print("STEP 2: Parsing Financial Metrics")
        print("=" * 60)
        
        parsed_results = {}
        for ticker, company_data in raw_data.items():
            if 'error' in company_data:
                print(f"\nSkipping {ticker} (error in data fetch)")
                continue
                
            print(f"\nParsing {ticker}...")
            try:
                parsed_results[ticker] = self.parser.parse_company_filings(company_data)
            except Exception as e:
                print(f"  Error parsing {ticker}: {e}")
        
        with open('parsed_metrics.json', 'w') as f:
            json.dump(parsed_results, f, indent=2)
        
        print("\n✓ Parsed metrics saved to parsed_metrics.json")
        return parsed_results
    
    def populate_database(self, parsed_data: Dict):
        """Populate database with parsed metrics"""
        print("\n" + "=" * 60)
        print("STEP 3: Populating Database")
        print("=" * 60)
        
        self.db.connect()
        self.db.create_schema()
        
        for ticker, company_data in parsed_data.items():
            print(f"\nInserting {ticker} data...")
            
            try:
                company_id = self.db.insert_company(
                    ticker=ticker,
                    cik=company_data.get('cik')
                )
                
                filings_parsed = company_data.get('filings_parsed', [])
                
                for filing_data in filings_parsed:
                    filing_id = self.db.insert_filing(
                        company_id=company_id,
                        filing_type=filing_data['filing_type'],
                        filing_date=filing_data['filing_date']
                    )
                    
                    metrics = filing_data.get('metrics', {})
                    if metrics:
                        self.db.insert_metrics(filing_id, metrics)
                        print(f"  ✓ Inserted {len(metrics)} metrics from {filing_data['filing_type']} ({filing_data['filing_date']})")
            
            except Exception as e:
                print(f"  Error inserting {ticker} data: {e}")
        
        print("\n✓ Database populated successfully")
    
    def export_results(self):
        """Export database to Excel"""
        print("\n" + "=" * 60)
        print("STEP 4: Exporting Results")
        print("=" * 60)
        
        try:
            self.db.export_to_excel('financial_metrics.xlsx')
            print("\n✓ Results exported to financial_metrics.xlsx")
        except Exception as e:
            print(f"Error exporting to Excel: {e}")
    
    def generate_summary(self, tickers: List[str]):
        """Generate summary statistics"""
        print("\n" + "=" * 60)
        print("DATABASE SUMMARY")
        print("=" * 60)
        
        for ticker in tickers:
            try:
                df = self.db.get_company_metrics(ticker)
                if not df.empty:
                    print(f"\n{ticker}:")
                    print(f"  Filings: {len(df)}")
                    
                    non_null_counts = df.count()
                    metrics_with_data = non_null_counts[non_null_counts > 0]
                    print(f"  Metrics with data: {len(metrics_with_data) - 3}")
            except Exception as e:
                print(f"\n{ticker}: Error generating summary - {e}")
    
    def run(self, tickers: List[str]):
        """Run the complete pipeline"""
        print("\n" + "=" * 60)
        print("FINANCIAL METRICS DATABASE PIPELINE")
        print("=" * 60)
        print(f"\nCompanies: {', '.join(tickers)}")
        print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        try:
            raw_data = self.fetch_sec_data(tickers)
            
            parsed_data = self.parse_metrics(raw_data)
            
            self.populate_database(parsed_data)
            
            self.export_results()
            
            self.generate_summary(tickers)
            
            print("\n" + "=" * 60)
            print("PIPELINE COMPLETED SUCCESSFULLY")
            print("=" * 60)
            print("\nOutput files:")
            print("  - sec_data_raw.json       (Raw SEC filing data)")
            print("  - parsed_metrics.json     (Parsed metrics)")
            print("  - financial_metrics.db    (SQLite database)")
            print("  - financial_metrics.xlsx  (Excel export)")
            
        except Exception as e:
            print(f"\n✗ Pipeline error: {e}")
            raise
        
        finally:
            if self.db.conn:
                self.db.close()


if __name__ == "__main__":
    companies = ["AMD", "CRM", "GOOG", "NVDA", "RH", "SPCX", "TSLA"]
    
    pipeline = DataPipeline()
    pipeline.run(companies)
