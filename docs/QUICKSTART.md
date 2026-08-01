# 🚀 Quick Start Guide

## Get Started in 3 Steps!

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Start the Chatbot
```bash
python3 app.py
```

### Step 3: Open Your Browser
Navigate to: **http://localhost:5000**

That's it! 🎉

## What You Can Do

### 💬 Chat with Your Data
Type questions in natural language:
- "Show me an overview"
- "Compare revenue"
- "Show NVDA trends"
- "Latest metrics for TSLA"

### 📊 Get Interactive Charts
Every response includes beautiful visualizations:
- **Bar charts** for comparisons
- **Line charts** for trends
- **Pie charts** for breakdowns
- **Multi-metric** charts for details

### 🔍 Explore Companies
Click company tags in sidebar to:
- See financial performance
- View historical trends
- Compare with competitors
- Analyze profitability

## Example Queries

### 1. Overview
**Ask:** "Show me an overview of all companies"

**Get:**
- List of all 7 companies
- Revenue rankings
- Interactive bar chart

### 2. Compare
**Ask:** "Compare profitability across companies"

**Get:**
- Net margin percentages
- Net income amounts
- Bar chart comparison

### 3. Trends
**Ask:** "Show NVDA revenue trend over time"

**Get:**
- 5 years of revenue data
- Year-over-year growth
- Line chart with trend

### 4. Company Details
**Ask:** "Tell me about GOOG"

**Get:**
- Company profile
- Latest metrics
- Multi-metric performance chart

### 5. Latest Metrics
**Ask:** "What are the latest metrics for TSLA?"

**Get:**
- All current metrics
- Formatted values
- Pie chart with margins

## Alternative: Terminal Mode

Prefer command line?
```bash
python3 -m src.chatbot
```

Ask questions and get text responses!

## Alternative: Direct Database Access

### Python API
```python
from query_interface import MetricsQuery

query = MetricsQuery()
companies = query.get_all_companies()
latest = query.get_latest_metrics('NVDA')
query.close()
```

### SQL Queries
```bash
sqlite3 data/financial_metrics.db

SELECT * FROM companies;
SELECT * FROM revenue_metrics;
```

### Excel
```bash
open data/financial_metrics_real.xlsx
```

## Update Data

Get the latest financial data:
```bash
python3 scripts/populate_real_data.py
```

This fetches fresh data from Yahoo Finance!

## Tips

1. **Be specific** with company names (use tickers: NVDA, TSLA, GOOG)
2. **Try examples** from the sidebar to learn query patterns
3. **Explore charts** - hover for details, zoom, pan
4. **Ask follow-ups** - continue the conversation naturally
5. **Use keywords** - revenue, profit, margin, trend, compare

## Troubleshooting

### Port already in use?
```bash
# Use a different port
python3 -c "from app import app; app.run(port=5001)"
```

### Database not found?
```bash
# Create database with real data
python3 scripts/populate_real_data.py
```

### Charts not showing?
- Check internet connection (Plotly CDN)
- Try hard refresh (Ctrl+Shift+R)
- Check browser console for errors

## What's Included

### Real Data
- **7 companies**: AMD, CRM, GOOG, NVDA, RH, SPCX, TSLA
- **560 metrics** from Yahoo Finance
- **3-5 years** of historical data
- **22 metric types** tracked

### Features
- Natural language chatbot
- Interactive visualizations
- Real-time responses
- Modern web interface
- Mobile-responsive design

## Next Steps

1. ✅ Start the chatbot (`python3 app.py`)
2. ✅ Try example queries
3. ✅ Explore different companies
4. ✅ Compare metrics
5. ✅ Analyze trends

## Need Help?

- **Documentation**: See `CHATBOT.md` for detailed guide
- **Real Data Info**: See `REAL_DATA.md` for data insights
- **Usage Guide**: See `USAGE.md` for advanced features
- **Examples**: Click sidebar queries in the web interface

---

**Happy chatting! 🤖💬**
