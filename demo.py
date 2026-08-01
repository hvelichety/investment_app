"""
Quick Demo - Shows database functionality
"""

from query_interface import MetricsQuery
import pandas as pd

print("=" * 70)
print("FINANCIAL METRICS DATABASE - QUICK DEMO")
print("=" * 70)

query = MetricsQuery()

print("\n1. Companies in Database:")
print("-" * 70)
companies = query.get_all_companies()
for _, row in companies.iterrows():
    print(f"  {row['ticker']:6s} - {row['company_name']:40s} (CIK: {row['cik']})")

print(f"\n  Total: {len(companies)} companies")

print("\n2. Available Metrics:")
print("-" * 70)
metrics = query.get_all_metric_names()
print(f"  {', '.join(metrics[:15])}...")
print(f"\n  Total: {len(metrics)} unique metrics")

print("\n3. Latest Metrics Comparison:")
print("-" * 70)
revenue_df = query.get_revenue_comparison()
latest_by_company = revenue_df.groupby('ticker').first().sort_values('total_revenue', ascending=False)
for ticker, row in latest_by_company.head(7).iterrows():
    if pd.notna(row['total_revenue']):
        print(f"  {ticker:6s}: ${row['total_revenue']:>12,.0f} revenue")

print("\n4. Company Overview - NVDA:")
print("-" * 70)
overview = query.get_company_overview('NVDA')
print(f"  Ticker: {overview['ticker']}")
print(f"  Filings: {overview['filings_count']}")
print(f"  Date Range: {overview['date_range']['earliest']} to {overview['date_range']['latest']}")

latest_nvda = query.get_latest_metrics('NVDA')
if not latest_nvda.empty:
    print(f"\n  Latest Metrics ({latest_nvda.iloc[0]['filing_date']}):")
    for _, row in latest_nvda.head(10).iterrows():
        print(f"    {row['metric_name']:30s}: {row['metric_value']:>12,.2f}")

print("\n5. Profitability Analysis:")
print("-" * 70)
prof_df = query.get_profitability_comparison()
latest_prof = prof_df.groupby('ticker').first().sort_values('net_margin', ascending=False)
for ticker, row in latest_prof.head(7).iterrows():
    if pd.notna(row['net_margin']):
        print(f"  {ticker:6s}: {row['net_margin']:>6.2f}% net margin, ${row['net_income']:>12,.0f} net income")

print("\n" + "=" * 70)
print("DATABASE SUMMARY")
print("=" * 70)
print(f"  Companies:      {len(companies)}")
print(f"  Unique Metrics: {len(metrics)}")
print(f"  Database File:  financial_metrics.db (84 KB)")
print(f"  Excel Export:   financial_metrics.xlsx (39 KB)")

print("\n" + "=" * 70)
print("DEMO COMPLETE")
print("=" * 70)
print("\nNext Steps:")
print("  - Explore data in Excel: financial_metrics.xlsx")
print("  - Run custom queries using query_interface.py")
print("  - Read USAGE.md for detailed examples")
print("  - Check SUMMARY.md for project overview")

query.close()
