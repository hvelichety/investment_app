# Financial Metrics Database - Usage Guide

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Populate database with sample data
python3 populate_sample_data.py

# 3. Query the database
python3 query_interface.py
```

## Database Overview

The database contains **comprehensive financial metrics** for 7 companies:
- **AMD** (Advanced Micro Devices)
- **CRM** (Salesforce)
- **GOOG** (Alphabet/Google)
- **NVDA** (NVIDIA)
- **RH** (RH/Restoration Hardware)
- **SPCX** (SPACx)
- **TSLA** (Tesla)

## Current Status

✅ **Database Created**: `financial_metrics.db` (SQLite)
✅ **Excel Export**: `financial_metrics.xlsx`
✅ **Total Metrics**: 644 individual data points
✅ **Filings**: 28 filings (10-K and S-1) across 7 companies
✅ **Metric Types**: 23 different financial metrics

## Available Metrics

### Revenue Metrics
- `total_revenue` - Total company revenue
- `revenue_growth` - Year-over-year revenue growth percentage

### Profitability Metrics
- `gross_profit` - Gross profit
- `operating_income` - Operating income
- `net_income` - Net income/profit
- `ebitda` - Earnings before interest, taxes, depreciation, and amortization

### Margin Metrics
- `gross_margin` - Gross profit margin percentage
- `operating_margin` - Operating margin percentage
- `net_margin` - Net profit margin percentage

### Balance Sheet Metrics
- `total_assets` - Total company assets
- `total_liabilities` - Total liabilities
- `stockholders_equity` - Stockholders' equity
- `cash_and_equivalents` - Cash and cash equivalents
- `total_debt` - Total debt

### Cash Flow Metrics
- `operating_cash_flow` - Cash from operating activities
- `free_cash_flow` - Free cash flow
- `capex` - Capital expenditures

### Per Share Metrics
- `eps` - Earnings per share
- `book_value_per_share` - Book value per share

### Operational Metrics
- `research_and_development` - R&D expenses
- `sales_and_marketing` - Sales and marketing expenses
- `employee_count` - Number of employees

### Valuation Metrics
- `market_cap` - Market capitalization

## Database Schema

```
companies
├── company_id (PK)
├── ticker
├── cik
├── company_name
└── created_at

filings
├── filing_id (PK)
├── company_id (FK)
├── filing_type (10-K, S-1)
├── filing_date
├── document_url
└── extraction_date

[11 metrics tables]
├── revenue_metrics
├── profitability_metrics
├── margin_metrics
├── balance_sheet_metrics
├── cash_flow_metrics
├── per_share_metrics
├── operational_metrics
├── valuation_metrics
└── all_metrics (flat table for flexible queries)
```

## Example Queries

### Python API

```python
from query_interface import MetricsQuery

query = MetricsQuery()

# Get all companies
companies = query.get_all_companies()
print(companies)

# Get latest metrics for a company
latest = query.get_latest_metrics('NVDA')
print(latest)

# Compare revenue across companies
revenue = query.get_revenue_comparison()
print(revenue)

# Get profitability comparison
profitability = query.get_profitability_comparison()
print(profitability)

# Search for specific metrics
results = query.search_metrics('revenue')
print(results)

# Get metric trends over time
trends = query.get_metric_trends('TSLA', 'net_income')
print(trends)

# Generate comprehensive report
report = query.generate_company_report('AMD', 'amd_report.txt')
print(report)

query.close()
```

### SQL Queries

```bash
sqlite3 financial_metrics.db
```

```sql
-- Get all companies
SELECT * FROM companies;

-- Get latest filing for each company
SELECT c.ticker, f.filing_type, f.filing_date, r.total_revenue
FROM companies c
JOIN filings f ON c.company_id = f.company_id
JOIN revenue_metrics r ON f.filing_id = r.filing_id
ORDER BY f.filing_date DESC;

-- Compare net income across companies
SELECT c.ticker, c.company_name, p.net_income, m.net_margin, f.filing_date
FROM companies c
JOIN filings f ON c.company_id = f.company_id
JOIN profitability_metrics p ON f.filing_id = p.filing_id
JOIN margin_metrics m ON f.filing_id = m.filing_id
WHERE f.filing_date = '2024-12-31'
ORDER BY p.net_income DESC;

-- Get all metrics for a specific company
SELECT am.metric_name, am.metric_value, f.filing_date
FROM companies c
JOIN filings f ON c.company_id = f.company_id
JOIN all_metrics am ON f.filing_id = am.filing_id
WHERE c.ticker = 'NVDA'
ORDER BY f.filing_date DESC, am.metric_name;

-- Find companies with highest revenue growth
SELECT c.ticker, r.revenue_growth, f.filing_date
FROM companies c
JOIN filings f ON c.company_id = f.company_id
JOIN revenue_metrics r ON f.filing_id = r.filing_id
WHERE r.revenue_growth IS NOT NULL
ORDER BY r.revenue_growth DESC
LIMIT 10;
```

## Excel Analysis

Open `financial_metrics.xlsx` to explore:
- **Companies** sheet - Company information
- **Filings** sheet - All filings metadata
- **All_Metrics** sheet - Complete metrics dataset
- Individual company sheets (e.g., **NVDA_Metrics**)

## Real SEC Data Collection

The system includes tools to fetch real SEC filing data:

```python
# Configure SEC API access (requires proper User-Agent)
from sec_data_fetcher import SECDataFetcher

fetcher = SECDataFetcher(user_agent="Your Name your@email.com")
data = fetcher.get_company_data("NVDA")
```

**Note**: SEC EDGAR requires a proper User-Agent header with contact information. 
The current implementation uses sample data due to API access restrictions.

## Project Structure

```
.
├── requirements.txt              # Python dependencies
├── README.md                     # Project overview
├── USAGE.md                      # This file
│
├── database_manager.py           # Database schema and operations
├── sec_data_fetcher.py          # SEC EDGAR data fetcher
├── metrics_parser.py            # Financial metrics extraction
├── query_interface.py           # Query API
│
├── main_pipeline.py             # Complete data pipeline
├── run_pipeline.py              # Robust pipeline with retry logic
├── populate_sample_data.py      # Sample data generator
├── test_suite.py                # Test suite
│
├── financial_metrics.db         # SQLite database (generated)
└── financial_metrics.xlsx       # Excel export (generated)
```

## Performance

- Database size: ~84 KB (with sample data)
- Total records: 644 metrics across 28 filings
- Query performance: < 100ms for most queries
- Excel export: Complete in < 1 second

## Extending the System

### Add More Companies

```python
from database_manager import MetricsDatabase

db = MetricsDatabase()
db.connect()
company_id = db.insert_company("AAPL", "0000320193", "Apple Inc.")
# ... insert filings and metrics
db.close()
```

### Add Custom Metrics

Edit `metrics_parser.py` to add new metric patterns:

```python
self.metric_patterns = {
    # ... existing patterns ...
    'custom_metric': [
        r'custom pattern regex here'
    ]
}
```

### Export to Other Formats

```python
import pandas as pd
from query_interface import MetricsQuery

query = MetricsQuery()
df = query.get_all_companies_metrics()

# CSV export
df.to_csv('metrics.csv', index=False)

# JSON export
df.to_json('metrics.json', orient='records')

# Parquet export
df.to_parquet('metrics.parquet')

query.close()
```

## Troubleshooting

### SEC API 403 Errors
- SEC requires a proper User-Agent header with contact information
- Use sample data or configure proper credentials

### Missing Dependencies
```bash
pip install -r requirements.txt
```

### Database Locked
- Close all connections before modifying schema
- Only one write operation at a time

### Memory Issues
- Process companies one at a time
- Use `run_pipeline.py` which includes progress tracking

## Next Steps

1. **Configure SEC API access** for real data collection
2. **Add more companies** to the database
3. **Create visualizations** using matplotlib/plotly
4. **Build a web interface** using Flask/Django
5. **Add financial ratios** (P/E, ROE, ROA, etc.)
6. **Implement trend analysis** and predictions
7. **Export to data warehouse** (BigQuery, Redshift, etc.)

## Support

For issues or questions:
1. Check the README.md for project overview
2. Review test_suite.py for examples
3. Examine query_interface.py for available methods
4. Inspect database_manager.py for schema details
