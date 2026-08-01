# Financial Metrics Database

> **Live deployment**: This app is deployed on Vercel. See `vercel.json` and `api/index.py` for the serverless configuration.

A comprehensive database system for collecting, parsing, and analyzing **real financial metrics** from Yahoo Finance API for publicly traded companies.

## Overview

This system automatically fetches real financial data from Yahoo Finance, extracts comprehensive metrics, and stores them in a structured SQLite database with powerful querying capabilities.

## ✅ **Real Data Included**

The database contains **real financial metrics from Yahoo Finance** for:

- AMD (Advanced Micro Devices)
- CRM (Salesforce)
- GOOG (Alphabet/Google)
- NVDA (NVIDIA)
- RH (RH/Restoration Hardware)
- SPCX (SPACx)
- TSLA (Tesla)

## Features

- **🤖 AI Chatbot**: Natural language interface with interactive visualizations
  - Ask questions in plain English
  - Get instant responses with charts and graphs
  - Bar charts, line charts, pie charts, and more
  - Modern web interface with real-time updates
- **Real Financial Data**: Fetches actual data from Yahoo Finance API
- **Comprehensive Metrics**: 22+ financial metrics tracked over 5 years
- **7 Companies**: AMD, CRM, GOOG, NVDA, RH, SPCX, TSLA
- **560 Total Metrics**: Real financial data points
- **37 Filings**: Historical data from 2021-2026
- **Structured Database**: SQLite with normalized schema
- **Query Interface**: Python API and SQL access
- **Excel Export**: Export all data to Excel with multiple sheets
- **Automated Updates**: Re-run script to get latest data
## Real Data Examples

### Latest Revenue (as of 2025-2026)
- **GOOG**: $402.8B (32.8% net margin)
- **NVDA**: $215.9B (55.6% net margin)
- **TSLA**: $94.8B (4.0% net margin)
- **CRM**: $41.5B (18.0% net margin)
- **AMD**: $34.6B (12.5% net margin)
- **SPCX**: $18.7B (-26.4% net margin)
- **RH**: $3.4B (3.6% net margin)

### Key Insights from Real Data
- NVIDIA has the highest profitability with 55.6% net margin
- Google generates the most revenue at $402.8B
- Space Exploration (SpaceX) shows losses but strong revenue growth
- All companies have 3-5 years of historical data

## Metrics Tracked

### Revenue Metrics (2)
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

### Option 1: Interactive Chatbot (Recommended) 🆕

```bash
pip install -r requirements.txt
python3 app.py
```

Open your browser to **http://localhost:5000** and chat with your financial data!

**Ask questions like:**
- "Show me an overview of all companies"
- "Compare profitability across companies"
- "Show NVDA revenue trend over time"
- "What are the latest metrics for TSLA?"

The chatbot will respond with **interactive charts and graphs**!

### Option 2: Populate Database with Real Data

Run the complete pipeline to fetch real data from Yahoo Finance:

```bash
pip install -r requirements.txt
python3 populate_real_data.py
```

This will:
1. Fetch real financial data from Yahoo Finance for all companies
2. Parse comprehensive financial metrics
3. Populate the SQLite database
4. Export results to Excel

### View Results

```bash
# Run interactive demo
python3 demo.py

# Query the database
python3 query_interface.py

# View in Excel
open financial_metrics_real.xlsx
```

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
