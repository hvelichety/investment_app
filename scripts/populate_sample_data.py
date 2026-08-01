"""
Populate Database with Sample Financial Data
Demonstrates the database structure with realistic example data
"""

import os
import sys
import random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database_manager import MetricsDatabase  # noqa: E402
from src.query_interface import MetricsQuery  # noqa: E402


def generate_sample_metrics(ticker: str, year: int, base_revenue: float):
    """Generate realistic sample metrics for a company"""
    revenue_growth = random.uniform(10, 30)
    gross_margin = random.uniform(50, 75)
    operating_margin = random.uniform(15, 35)
    net_margin = random.uniform(10, 25)
    
    metrics = {
        'total_revenue': base_revenue * (1 + year * 0.15),
        'revenue_growth': revenue_growth,
        'gross_profit': base_revenue * (1 + year * 0.15) * (gross_margin / 100),
        'operating_income': base_revenue * (1 + year * 0.15) * (operating_margin / 100),
        'net_income': base_revenue * (1 + year * 0.15) * (net_margin / 100),
        'ebitda': base_revenue * (1 + year * 0.15) * (operating_margin / 100) * 1.2,
        'gross_margin': gross_margin,
        'operating_margin': operating_margin,
        'net_margin': net_margin,
        'total_assets': base_revenue * 3.5,
        'total_liabilities': base_revenue * 1.8,
        'stockholders_equity': base_revenue * 1.7,
        'cash_and_equivalents': base_revenue * 0.4,
        'total_debt': base_revenue * 0.9,
        'operating_cash_flow': base_revenue * (1 + year * 0.15) * (net_margin / 100) * 1.3,
        'free_cash_flow': base_revenue * (1 + year * 0.15) * (net_margin / 100) * 1.1,
        'capex': base_revenue * (1 + year * 0.15) * 0.08,
        'eps': (base_revenue * (1 + year * 0.15) * (net_margin / 100)) / 1000000,
        'book_value_per_share': (base_revenue * 1.7) / 1000000,
        'research_and_development': base_revenue * (1 + year * 0.15) * 0.18,
        'sales_and_marketing': base_revenue * (1 + year * 0.15) * 0.15,
        'employee_count': int(base_revenue / 50 * (1 + year * 0.1)),
        'market_cap': base_revenue * 8
    }
    
    return metrics


def populate_sample_data():
    """Populate database with sample data for all companies"""
    
    companies_config = {
        'AMD': {
            'cik': '0000002488',
            'name': 'Advanced Micro Devices, Inc.',
            'base_revenue': 5600000
        },
        'CRM': {
            'cik': '0001108524',
            'name': 'Salesforce, Inc.',
            'base_revenue': 31000000
        },
        'GOOG': {
            'cik': '0001652044',
            'name': 'Alphabet Inc.',
            'base_revenue': 280000000
        },
        'NVDA': {
            'cik': '0001045810',
            'name': 'NVIDIA Corporation',
            'base_revenue': 60000000
        },
        'RH': {
            'cik': '0001528849',
            'name': 'RH',
            'base_revenue': 3000000
        },
        'SPCX': {
            'cik': '0001841991',
            'name': 'SPACx',
            'base_revenue': 500000
        },
        'TSLA': {
            'cik': '0001318605',
            'name': 'Tesla, Inc.',
            'base_revenue': 81000000
        }
    }
    
    db = MetricsDatabase()
    db.connect()
    db.create_schema()
    
    print("=" * 70)
    print("POPULATING DATABASE WITH SAMPLE FINANCIAL DATA")
    print("=" * 70)
    print("\nNote: This is sample data demonstrating the database structure.")
    print("Real SEC data requires proper API credentials and rate limiting.\n")
    
    current_year = 2024
    
    for ticker, config in companies_config.items():
        print(f"\nInserting data for {ticker} ({config['name']})...")
        
        company_id = db.insert_company(
            ticker=ticker,
            cik=config['cik'],
            company_name=config['name']
        )
        
        for year_offset in range(3):
            filing_year = current_year - year_offset
            filing_date = f"{filing_year}-12-31"
            
            for filing_type in ['10-K', 'S-1']:
                if filing_type == 'S-1' and year_offset > 0:
                    continue
                
                filing_id = db.insert_filing(
                    company_id=company_id,
                    filing_type=filing_type,
                    filing_date=filing_date,
                    document_url=f"https://sec.gov/example/{ticker}/{filing_type}/{filing_year}"
                )
                
                metrics = generate_sample_metrics(ticker, year_offset, config['base_revenue'])
                db.insert_metrics(filing_id, metrics)
                
                print(f"  ✓ {filing_type} - {filing_date}: {len(metrics)} metrics")
    
    print("\n" + "=" * 70)
    print("EXPORTING DATA")
    print("=" * 70)
    
    db.export_to_excel('financial_metrics.xlsx')
    db.close()
    
    print("\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)
    
    query = MetricsQuery()
    
    companies = query.get_all_companies()
    print(f"\n✓ Total companies: {len(companies)}")
    print(f"  Tickers: {', '.join(companies['ticker'].tolist())}")
    
    metrics = query.get_all_metric_names()
    print(f"\n✓ Total unique metrics: {len(metrics)}")
    print(f"  Sample metrics: {', '.join(metrics[:10])}...")
    
    print("\n" + "=" * 70)
    print("COMPANY SUMMARIES")
    print("=" * 70)
    
    for ticker in companies['ticker']:
        df = query.db.get_company_metrics(ticker)
        if not df.empty:
            latest = df.iloc[0]
            print(f"\n{ticker} - Latest Filing ({latest['filing_date']}):")
            print(f"  Revenue: ${latest['total_revenue']:,.0f}")
            print(f"  Net Income: ${latest['net_income']:,.0f}")
            print(f"  Net Margin: {latest['net_margin']:.1f}%")
            print(f"  Total Assets: ${latest['total_assets']:,.0f}")
            print(f"  Employees: {int(latest['employee_count']):,}")
    
    print("\n" + "=" * 70)
    print("SAMPLE QUERIES")
    print("=" * 70)
    
    print("\n1. Revenue Comparison:")
    revenue_df = query.get_revenue_comparison()
    print(revenue_df.head(10).to_string(index=False))
    
    print("\n2. Profitability Comparison:")
    prof_df = query.get_profitability_comparison()
    print(prof_df.head(10).to_string(index=False))
    
    print("\n" + "=" * 70)
    print("DATABASE READY")
    print("=" * 70)
    print("\nFiles created:")
    print("  - financial_metrics.db    (SQLite database with sample data)")
    print("  - financial_metrics.xlsx  (Excel export)")
    print("\nYou can now:")
    print("  - Query data using query_interface.py")
    print("  - Import real SEC data when API access is configured")
    print("  - Analyze metrics using pandas/SQL")
    
    query.close()


if __name__ == "__main__":
    populate_sample_data()
