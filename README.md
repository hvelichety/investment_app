# Financial Metrics Database

A comprehensive database system for collecting, parsing, and analyzing financial metrics from SEC filings (S-1 and 10-K) for publicly traded companies.

## Overview

This system automatically fetches SEC filings, extracts financial metrics, and stores them in a structured SQLite database with comprehensive querying capabilities.

## Target Companies

- AMD (Advanced Micro Devices)
- CRM (Salesforce)
- GOOG (Alphabet/Google)
- NVDA (NVIDIA)
- RH (RH/Restoration Hardware)
- SPCX (SPACx)
- TSLA (Tesla)

## Features

- **Automated SEC Filing Retrieval**: Fetches S-1 and 10-K filings from SEC EDGAR
- **Comprehensive Metrics Extraction**: Parses 20+ financial metrics including:
  - Revenue metrics (total revenue, growth rate)
  - Profitability metrics (gross profit, operating income, net income, EBITDA)
  - Margin metrics (gross, operating, net margins)
  - Balance sheet metrics (assets, liabilities, equity, cash, debt)
  - Cash flow metrics (operating cash flow, free cash flow, capex)
  - Per-share metrics (EPS, book value per share)
  - Operational metrics (R&D, sales & marketing, employee count)
  - Valuation metrics (market cap)
- **Structured Database**: SQLite database with normalized schema
- **Query Interface**: Easy-to-use Python API for data analysis
- **Excel Export**: Export all data to Excel with multiple sheets

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Quick Start

Run the complete pipeline to fetch, parse, and store all metrics:

```bash
python main_pipeline.py
```

This will:
1. Fetch SEC filings for all companies
2. Parse financial metrics from the filings
3. Populate the SQLite database
4. Export results to Excel

### Individual Components

#### Fetch SEC Data Only

```bash
python sec_data_fetcher.py
```

#### Parse Metrics Only

```bash
python metrics_parser.py
```

#### Create Database Schema Only

```bash
python database_manager.py
```

#### Query the Database

```python
from query_interface import MetricsQuery

query = MetricsQuery()

# Get all companies
companies = query.get_all_companies()

# Get latest metrics for a company
latest = query.get_latest_metrics('NVDA')

# Compare revenue across companies
revenue = query.get_revenue_comparison()

# Generate comprehensive report
report = query.generate_company_report('TSLA', output_file='tesla_report.txt')

query.close()
```

## Database Schema

The database contains 11 tables:

- `companies`: Company information (ticker, CIK, name)
- `filings`: Filing metadata (type, date, document URL)
- `revenue_metrics`: Revenue and growth metrics
- `profitability_metrics`: Profit-related metrics
- `margin_metrics`: Margin percentages
- `balance_sheet_metrics`: Balance sheet items
- `cash_flow_metrics`: Cash flow data
- `per_share_metrics`: Per-share calculations
- `operational_metrics`: Operational data
- `valuation_metrics`: Valuation data
- `all_metrics`: Flat table with all metrics for flexible querying

## Output Files

- `sec_data_raw.json`: Raw SEC filing data
- `parsed_metrics.json`: Parsed metrics in JSON format
- `financial_metrics.db`: SQLite database
- `financial_metrics.xlsx`: Excel export with multiple sheets

## Query Examples

### Get all available metrics

```python
query = MetricsQuery()
metrics = query.get_all_metric_names()
print(metrics)
```

### Compare specific metric across companies

```python
query = MetricsQuery()
comparison = query.compare_companies(['NVDA', 'AMD'], 'total_revenue')
print(comparison)
```

### Get metric trends over time

```python
query = MetricsQuery()
trends = query.get_metric_trends('GOOG', 'net_income')
print(trends)
```

### Search for metrics

```python
query = MetricsQuery()
results = query.search_metrics('revenue')
print(results)
```

## Architecture

```
main_pipeline.py
├── sec_data_fetcher.py    # Fetches filings from SEC EDGAR
├── metrics_parser.py      # Extracts metrics from HTML/text
└── database_manager.py    # Manages SQLite database

query_interface.py         # Provides query and analysis tools
```

## Notes

- The SEC API has rate limits; the system includes delays to respect these limits
- Some metrics may not be available for all companies or all filings
- The parser uses pattern matching and may require adjustments for specific filing formats
- All monetary values are stored as-is from the filings (typically in millions or billions)

## Requirements

- Python 3.8+
- requests
- beautifulsoup4
- lxml
- pandas
- openpyxl
- sqlite3 (included with Python)

## License

MIT License
