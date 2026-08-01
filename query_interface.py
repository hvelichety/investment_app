"""
Query Interface
Provides convenient methods to query and analyze the financial metrics database
"""

import sqlite3
import pandas as pd
from typing import List, Optional, Dict
from database_manager import MetricsDatabase


class MetricsQuery:
    def __init__(self, db_path: str = "financial_metrics.db"):
        self.db = MetricsDatabase(db_path)
        self.db.connect()
    
    def close(self):
        self.db.close()
    
    def get_all_companies(self) -> pd.DataFrame:
        """Get list of all companies in database"""
        query = "SELECT * FROM companies ORDER BY ticker"
        return pd.read_sql_query(query, self.db.conn)
    
    def get_company_overview(self, ticker: str) -> Dict:
        """Get overview of a company's data"""
        df = self.db.get_company_metrics(ticker)
        
        if df.empty:
            return {"error": f"No data found for {ticker}"}
        
        overview = {
            "ticker": ticker,
            "filings_count": len(df),
            "date_range": {
                "earliest": df['filing_date'].min(),
                "latest": df['filing_date'].max()
            },
            "latest_metrics": df.iloc[0].to_dict() if not df.empty else {}
        }
        
        return overview
    
    def compare_companies(self, tickers: List[str], metric: str) -> pd.DataFrame:
        """Compare a specific metric across companies"""
        query = f"""
            SELECT 
                c.ticker,
                f.filing_date,
                am.metric_value
            FROM companies c
            JOIN filings f ON c.company_id = f.company_id
            JOIN all_metrics am ON f.filing_id = am.filing_id
            WHERE c.ticker IN ({','.join(['?' for _ in tickers])})
            AND am.metric_name = ?
            ORDER BY f.filing_date DESC
        """
        
        return pd.read_sql_query(query, self.db.conn, params=tickers + [metric])
    
    def get_latest_metrics(self, ticker: str) -> pd.DataFrame:
        """Get the most recent metrics for a company"""
        query = """
            SELECT 
                am.metric_name,
                am.metric_value,
                f.filing_type,
                f.filing_date
            FROM companies c
            JOIN filings f ON c.company_id = f.company_id
            JOIN all_metrics am ON f.filing_id = am.filing_id
            WHERE c.ticker = ?
            AND f.filing_date = (
                SELECT MAX(filing_date) 
                FROM filings 
                WHERE company_id = c.company_id
            )
            ORDER BY am.metric_name
        """
        
        return pd.read_sql_query(query, self.db.conn, params=(ticker,))
    
    def get_metric_trends(self, ticker: str, metric_name: str) -> pd.DataFrame:
        """Get historical trend for a specific metric"""
        query = """
            SELECT 
                f.filing_date,
                f.filing_type,
                am.metric_value
            FROM companies c
            JOIN filings f ON c.company_id = f.company_id
            JOIN all_metrics am ON f.filing_id = am.filing_id
            WHERE c.ticker = ?
            AND am.metric_name = ?
            ORDER BY f.filing_date DESC
        """
        
        return pd.read_sql_query(query, self.db.conn, params=(ticker, metric_name))
    
    def get_all_metric_names(self) -> List[str]:
        """Get list of all unique metric names in database"""
        query = "SELECT DISTINCT metric_name FROM all_metrics ORDER BY metric_name"
        df = pd.read_sql_query(query, self.db.conn)
        return df['metric_name'].tolist()
    
    def search_metrics(self, search_term: str) -> pd.DataFrame:
        """Search for metrics containing a specific term"""
        query = """
            SELECT DISTINCT 
                c.ticker,
                am.metric_name,
                am.metric_value,
                f.filing_date
            FROM companies c
            JOIN filings f ON c.company_id = f.company_id
            JOIN all_metrics am ON f.filing_id = am.filing_id
            WHERE am.metric_name LIKE ?
            ORDER BY c.ticker, f.filing_date DESC
        """
        
        return pd.read_sql_query(query, self.db.conn, params=(f"%{search_term}%",))
    
    def get_revenue_comparison(self) -> pd.DataFrame:
        """Compare revenue metrics across all companies"""
        query = """
            SELECT 
                c.ticker,
                f.filing_date,
                r.total_revenue,
                r.revenue_growth
            FROM companies c
            JOIN filings f ON c.company_id = f.company_id
            LEFT JOIN revenue_metrics r ON f.filing_id = r.filing_id
            WHERE r.total_revenue IS NOT NULL
            ORDER BY c.ticker, f.filing_date DESC
        """
        
        return pd.read_sql_query(query, self.db.conn)
    
    def get_profitability_comparison(self) -> pd.DataFrame:
        """Compare profitability metrics across all companies"""
        query = """
            SELECT 
                c.ticker,
                f.filing_date,
                p.gross_profit,
                p.operating_income,
                p.net_income,
                m.gross_margin,
                m.operating_margin,
                m.net_margin
            FROM companies c
            JOIN filings f ON c.company_id = f.company_id
            LEFT JOIN profitability_metrics p ON f.filing_id = p.filing_id
            LEFT JOIN margin_metrics m ON f.filing_id = m.filing_id
            WHERE p.net_income IS NOT NULL OR m.net_margin IS NOT NULL
            ORDER BY c.ticker, f.filing_date DESC
        """
        
        return pd.read_sql_query(query, self.db.conn)
    
    def generate_company_report(self, ticker: str, output_file: Optional[str] = None) -> str:
        """Generate a comprehensive report for a company"""
        report = []
        report.append("=" * 80)
        report.append(f"FINANCIAL METRICS REPORT: {ticker}")
        report.append("=" * 80)
        
        overview = self.get_company_overview(ticker)
        if "error" in overview:
            return overview["error"]
        
        report.append(f"\nFilings Count: {overview['filings_count']}")
        report.append(f"Date Range: {overview['date_range']['earliest']} to {overview['date_range']['latest']}")
        
        latest = self.get_latest_metrics(ticker)
        if not latest.empty:
            report.append(f"\n\nLATEST METRICS ({latest.iloc[0]['filing_date']}):")
            report.append("-" * 80)
            for _, row in latest.iterrows():
                report.append(f"{row['metric_name']:40s}: {row['metric_value']:15,.2f}")
        
        all_metrics = self.db.get_company_metrics(ticker)
        if not all_metrics.empty:
            report.append("\n\nCOMPREHENSIVE METRICS SUMMARY:")
            report.append("-" * 80)
            report.append(all_metrics.to_string())
        
        report_text = "\n".join(report)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_text)
            print(f"✓ Report saved to {output_file}")
        
        return report_text


if __name__ == "__main__":
    query = MetricsQuery()
    
    print("Available companies:")
    print(query.get_all_companies())
    
    print("\n\nAvailable metrics:")
    metrics = query.get_all_metric_names()
    for i, metric in enumerate(metrics, 1):
        print(f"{i}. {metric}")
    
    print("\n\nRevenue Comparison:")
    print(query.get_revenue_comparison())
    
    companies = query.get_all_companies()['ticker'].tolist()
    if companies:
        ticker = companies[0]
        print(f"\n\nSample Report for {ticker}:")
        print(query.generate_company_report(ticker))
    
    query.close()
