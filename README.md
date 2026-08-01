# Financial Metrics Database

> **Live deployment**: This app is deployed on Vercel. See `vercel.json` and `api/index.py` for the serverless configuration.

A comprehensive database system for collecting, parsing, and analyzing **real financial metrics** from the Yahoo Finance API for publicly traded companies, with an AI chatbot web interface.

## Project Structure

```
.
├── app.py                    # Local dev entrypoint (python3 app.py)
├── api/
│   └── index.py              # Vercel serverless entrypoint
├── src/                      # Application package
│   ├── web.py                # Flask app: chat UI + database browser
│   ├── chatbot.py            # Natural-language chatbot
│   ├── query_interface.py    # High-level analysis queries
│   ├── database_manager.py   # Schema + data access layer
│   └── db_backend.py         # Local SQLite / Turso cloud selector
├── templates/
│   └── index.html            # Web UI (chat + database tabs)
├── data/
│   ├── financial_metrics.db          # SQLite database (real data)
│   └── financial_metrics_real.xlsx   # Excel export
├── scripts/                  # Data pipelines & utilities
│   ├── populate_real_data.py     # Rebuild DB from Yahoo Finance
│   ├── yahoo_finance_fetcher.py  # Yahoo Finance data collection
│   ├── migrate_to_cloud.py       # Sync local DB -> Turso cloud
│   ├── demo.py                   # Interactive data demo
│   ├── populate_sample_data.py   # (legacy) sample data generator
│   ├── sec_data_fetcher.py       # (legacy) SEC EDGAR fetcher
│   ├── metrics_parser.py         # (legacy) SEC filing parser
│   ├── main_pipeline.py          # (legacy) SEC pipeline
│   └── run_pipeline.py           # (legacy) SEC pipeline runner
├── tests/
│   └── test_suite.py         # Database & query tests
├── docs/                     # Extended documentation
│   ├── QUICKSTART.md
│   ├── CHATBOT.md
│   ├── REAL_DATA.md
│   ├── USAGE.md
│   └── SUMMARY.md
├── .github/workflows/
│   └── update-data.yml       # Weekly automated data refresh
├── requirements.txt          # Runtime deps (web app / Vercel)
├── requirements-data.txt     # Data collection & dev deps
└── vercel.json               # Vercel deployment config
```

## ✅ Real Data Included

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
- **🗄️ Database Browser**: Browse every table/view and run read-only SQL from the web UI
- **Real Financial Data**: Fetched from the Yahoo Finance API
- **Comprehensive Metrics**: 22+ financial metrics tracked over 5 years
- **Structured Database**: SQLite with normalized schema + convenience views
- **Cloud Database Support**: Optional Turso (libSQL) backend for deployments
- **Excel Export**: Export all data to Excel with multiple sheets
- **Automated Updates**: Weekly GitHub Actions refresh (`.github/workflows/update-data.yml`)

## Quick Start

### Option 1: Interactive Chatbot (Recommended)

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

### Option 2: Rebuild the Database with Fresh Data

```bash
pip install -r requirements.txt -r requirements-data.txt
python3 scripts/populate_real_data.py
```

This fetches real financial data from Yahoo Finance for all companies, populates `data/financial_metrics.db`, and exports `data/financial_metrics_real.xlsx`.

### View Results

```bash
# Run interactive demo
python3 scripts/demo.py

# Query the database from the CLI
python3 -m src.query_interface

# View in Excel
open data/financial_metrics_real.xlsx
```

## Querying from Python

```python
from src.query_interface import MetricsQuery

query = MetricsQuery()

# Get all companies
companies = query.get_all_companies()

# Get latest metrics for a company
latest = query.get_latest_metrics('NVDA')

# Compare revenue across companies
revenue = query.get_revenue_comparison()

# Compare a specific metric across companies
comparison = query.compare_companies(['NVDA', 'AMD'], 'total_revenue')

# Get metric trends over time
trends = query.get_metric_trends('GOOG', 'net_income')

# Generate comprehensive report
report = query.generate_company_report('TSLA', output_file='tesla_report.txt')

query.close()
```

## Database Schema

Core tables:

- `companies`: Company information (ticker, CIK, name)
- `filings`: Filing metadata (type, date, document URL)
- `revenue_metrics`, `profitability_metrics`, `margin_metrics`,
  `balance_sheet_metrics`, `cash_flow_metrics`, `per_share_metrics`,
  `operational_metrics`, `valuation_metrics`
- `all_metrics`: Flat table with all metrics for flexible querying

Convenience views (`v_company_overview`, `v_revenue_metrics`, `v_per_share_metrics`, ...) join company and filing info into each metric table for easier browsing.

## Cloud Database (Turso)

The app uses the local SQLite file by default. To use a Turso cloud database instead, set:

```bash
export TURSO_DATABASE_URL="libsql://your-db-your-org.turso.io"
export TURSO_AUTH_TOKEN="your-token"
python3 scripts/migrate_to_cloud.py   # one-time (or repeat) sync
```

The weekly GitHub Actions workflow syncs to Turso automatically when the `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` repository secrets are configured.

## Automated Updates

`.github/workflows/update-data.yml` runs every Monday at 06:00 UTC (or manually via *Run workflow*): it rebuilds the database from Yahoo Finance, syncs the cloud database, and commits the updated files in `data/`.

## Testing

```bash
python3 tests/test_suite.py
```

## Documentation

See the `docs/` folder for extended guides: [QUICKSTART](docs/QUICKSTART.md), [CHATBOT](docs/CHATBOT.md), [REAL_DATA](docs/REAL_DATA.md), [USAGE](docs/USAGE.md), and [SUMMARY](docs/SUMMARY.md).

## Requirements

- Python 3.8+
- Runtime: `flask`, `pandas`, `libsql` (see `requirements.txt`)
- Data collection: `yfinance`, `openpyxl`, etc. (see `requirements-data.txt`)

## License

MIT License
