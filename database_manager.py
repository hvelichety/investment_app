"""
Database Manager
Creates and manages SQLite database for company financial metrics
"""

import sqlite3
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
import pandas as pd


class MetricsDatabase:
    def __init__(self, db_path: str = "financial_metrics.db"):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
    
    def connect(self):
        """Connect to the database"""
        # check_same_thread=False allows use from Flask request threads;
        # access is serialized with a lock in app.py.
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
    
    def create_schema(self):
        """Create database schema for storing metrics"""
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                company_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT UNIQUE NOT NULL,
                cik TEXT,
                company_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS filings (
                filing_id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                filing_type TEXT NOT NULL,
                filing_date DATE NOT NULL,
                document_url TEXT,
                extraction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies(company_id)
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS revenue_metrics (
                metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                filing_id INTEGER,
                total_revenue REAL,
                revenue_growth REAL,
                FOREIGN KEY (filing_id) REFERENCES filings(filing_id)
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS profitability_metrics (
                metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                filing_id INTEGER,
                gross_profit REAL,
                operating_income REAL,
                net_income REAL,
                ebitda REAL,
                FOREIGN KEY (filing_id) REFERENCES filings(filing_id)
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS margin_metrics (
                metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                filing_id INTEGER,
                gross_margin REAL,
                operating_margin REAL,
                net_margin REAL,
                FOREIGN KEY (filing_id) REFERENCES filings(filing_id)
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS balance_sheet_metrics (
                metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                filing_id INTEGER,
                total_assets REAL,
                total_liabilities REAL,
                stockholders_equity REAL,
                cash_and_equivalents REAL,
                total_debt REAL,
                FOREIGN KEY (filing_id) REFERENCES filings(filing_id)
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS cash_flow_metrics (
                metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                filing_id INTEGER,
                operating_cash_flow REAL,
                free_cash_flow REAL,
                capex REAL,
                FOREIGN KEY (filing_id) REFERENCES filings(filing_id)
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS per_share_metrics (
                metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                filing_id INTEGER,
                eps REAL,
                book_value_per_share REAL,
                FOREIGN KEY (filing_id) REFERENCES filings(filing_id)
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS operational_metrics (
                metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                filing_id INTEGER,
                research_and_development REAL,
                sales_and_marketing REAL,
                employee_count INTEGER,
                FOREIGN KEY (filing_id) REFERENCES filings(filing_id)
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS valuation_metrics (
                metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                filing_id INTEGER,
                market_cap REAL,
                FOREIGN KEY (filing_id) REFERENCES filings(filing_id)
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS all_metrics (
                metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                filing_id INTEGER,
                metric_name TEXT NOT NULL,
                metric_value REAL,
                metric_unit TEXT,
                FOREIGN KEY (filing_id) REFERENCES filings(filing_id)
            )
        """)
        
        self.conn.commit()
        print("✓ Database schema created successfully")
    
    def insert_company(self, ticker: str, cik: Optional[str] = None, company_name: Optional[str] = None) -> int:
        """Insert or get company ID"""
        self.cursor.execute(
            "SELECT company_id FROM companies WHERE ticker = ?",
            (ticker,)
        )
        result = self.cursor.fetchone()
        
        if result:
            return result[0]
        
        self.cursor.execute(
            "INSERT INTO companies (ticker, cik, company_name) VALUES (?, ?, ?)",
            (ticker, cik, company_name)
        )
        self.conn.commit()
        return self.cursor.lastrowid
    
    def insert_filing(self, company_id: int, filing_type: str, filing_date: str, document_url: Optional[str] = None) -> int:
        """Insert filing record"""
        self.cursor.execute(
            "INSERT INTO filings (company_id, filing_type, filing_date, document_url) VALUES (?, ?, ?, ?)",
            (company_id, filing_type, filing_date, document_url)
        )
        self.conn.commit()
        return self.cursor.lastrowid
    
    def insert_metrics(self, filing_id: int, metrics: Dict[str, Any]):
        """Insert all metrics for a filing"""
        
        revenue_cols = ['total_revenue', 'revenue_growth']
        revenue_values = [metrics.get(col) for col in revenue_cols]
        if any(v is not None for v in revenue_values):
            placeholders = ','.join(['?' for _ in revenue_cols])
            self.cursor.execute(
                f"INSERT INTO revenue_metrics (filing_id, {','.join(revenue_cols)}) VALUES (?, {placeholders})",
                [filing_id] + revenue_values
            )
        
        profitability_cols = ['gross_profit', 'operating_income', 'net_income', 'ebitda']
        profitability_values = [metrics.get(col) for col in profitability_cols]
        if any(v is not None for v in profitability_values):
            placeholders = ','.join(['?' for _ in profitability_cols])
            self.cursor.execute(
                f"INSERT INTO profitability_metrics (filing_id, {','.join(profitability_cols)}) VALUES (?, {placeholders})",
                [filing_id] + profitability_values
            )
        
        margin_cols = ['gross_margin', 'operating_margin', 'net_margin']
        margin_values = [metrics.get(col) for col in margin_cols]
        if any(v is not None for v in margin_values):
            placeholders = ','.join(['?' for _ in margin_cols])
            self.cursor.execute(
                f"INSERT INTO margin_metrics (filing_id, {','.join(margin_cols)}) VALUES (?, {placeholders})",
                [filing_id] + margin_values
            )
        
        balance_cols = ['total_assets', 'total_liabilities', 'stockholders_equity', 'cash_and_equivalents', 'total_debt']
        balance_values = [metrics.get(col) for col in balance_cols]
        if any(v is not None for v in balance_values):
            placeholders = ','.join(['?' for _ in balance_cols])
            self.cursor.execute(
                f"INSERT INTO balance_sheet_metrics (filing_id, {','.join(balance_cols)}) VALUES (?, {placeholders})",
                [filing_id] + balance_values
            )
        
        cash_flow_cols = ['operating_cash_flow', 'free_cash_flow', 'capex']
        cash_flow_values = [metrics.get(col) for col in cash_flow_cols]
        if any(v is not None for v in cash_flow_values):
            placeholders = ','.join(['?' for _ in cash_flow_cols])
            self.cursor.execute(
                f"INSERT INTO cash_flow_metrics (filing_id, {','.join(cash_flow_cols)}) VALUES (?, {placeholders})",
                [filing_id] + cash_flow_values
            )
        
        per_share_cols = ['eps', 'book_value_per_share']
        per_share_values = [metrics.get(col) for col in per_share_cols]
        if any(v is not None for v in per_share_values):
            placeholders = ','.join(['?' for _ in per_share_cols])
            self.cursor.execute(
                f"INSERT INTO per_share_metrics (filing_id, {','.join(per_share_cols)}) VALUES (?, {placeholders})",
                [filing_id] + per_share_values
            )
        
        operational_cols = ['research_and_development', 'sales_and_marketing', 'employee_count']
        operational_values = [metrics.get(col) for col in operational_cols]
        if any(v is not None for v in operational_values):
            placeholders = ','.join(['?' for _ in operational_cols])
            self.cursor.execute(
                f"INSERT INTO operational_metrics (filing_id, {','.join(operational_cols)}) VALUES (?, {placeholders})",
                [filing_id] + operational_values
            )
        
        valuation_cols = ['market_cap']
        valuation_values = [metrics.get(col) for col in valuation_cols]
        if any(v is not None for v in valuation_values):
            self.cursor.execute(
                "INSERT INTO valuation_metrics (filing_id, market_cap) VALUES (?, ?)",
                [filing_id] + valuation_values
            )
        
        for metric_name, metric_value in metrics.items():
            if isinstance(metric_value, (int, float)):
                self.cursor.execute(
                    "INSERT INTO all_metrics (filing_id, metric_name, metric_value) VALUES (?, ?, ?)",
                    (filing_id, metric_name, metric_value)
                )
        
        self.conn.commit()
    
    def get_company_metrics(self, ticker: str) -> pd.DataFrame:
        """Get all metrics for a company"""
        query = """
            SELECT 
                c.ticker,
                f.filing_type,
                f.filing_date,
                r.total_revenue,
                r.revenue_growth,
                p.gross_profit,
                p.operating_income,
                p.net_income,
                p.ebitda,
                m.gross_margin,
                m.operating_margin,
                m.net_margin,
                b.total_assets,
                b.total_liabilities,
                b.stockholders_equity,
                b.cash_and_equivalents,
                b.total_debt,
                cf.operating_cash_flow,
                cf.free_cash_flow,
                cf.capex,
                ps.eps,
                ps.book_value_per_share,
                o.research_and_development,
                o.sales_and_marketing,
                o.employee_count,
                v.market_cap
            FROM companies c
            LEFT JOIN filings f ON c.company_id = f.company_id
            LEFT JOIN revenue_metrics r ON f.filing_id = r.filing_id
            LEFT JOIN profitability_metrics p ON f.filing_id = p.filing_id
            LEFT JOIN margin_metrics m ON f.filing_id = m.filing_id
            LEFT JOIN balance_sheet_metrics b ON f.filing_id = b.filing_id
            LEFT JOIN cash_flow_metrics cf ON f.filing_id = cf.filing_id
            LEFT JOIN per_share_metrics ps ON f.filing_id = ps.filing_id
            LEFT JOIN operational_metrics o ON f.filing_id = o.filing_id
            LEFT JOIN valuation_metrics v ON f.filing_id = v.filing_id
            WHERE c.ticker = ?
            ORDER BY f.filing_date DESC
        """
        
        return pd.read_sql_query(query, self.conn, params=(ticker,))
    
    def get_all_companies_metrics(self) -> pd.DataFrame:
        """Get metrics for all companies"""
        query = """
            SELECT 
                c.ticker,
                c.company_name,
                f.filing_type,
                f.filing_date,
                am.metric_name,
                am.metric_value
            FROM companies c
            LEFT JOIN filings f ON c.company_id = f.company_id
            LEFT JOIN all_metrics am ON f.filing_id = am.filing_id
            ORDER BY c.ticker, f.filing_date DESC, am.metric_name
        """
        
        return pd.read_sql_query(query, self.conn)
    
    def export_to_excel(self, output_file: str = "financial_metrics.xlsx"):
        """Export all data to Excel with multiple sheets"""
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            companies_df = pd.read_sql_query("SELECT * FROM companies", self.conn)
            companies_df.to_excel(writer, sheet_name='Companies', index=False)
            
            filings_df = pd.read_sql_query("""
                SELECT f.*, c.ticker 
                FROM filings f 
                JOIN companies c ON f.company_id = c.company_id
            """, self.conn)
            filings_df.to_excel(writer, sheet_name='Filings', index=False)
            
            all_metrics_df = self.get_all_companies_metrics()
            all_metrics_df.to_excel(writer, sheet_name='All_Metrics', index=False)
            
            for ticker in companies_df['ticker']:
                company_metrics = self.get_company_metrics(ticker)
                if not company_metrics.empty:
                    company_metrics.to_excel(writer, sheet_name=f'{ticker}_Metrics', index=False)
        
        print(f"✓ Data exported to {output_file}")


if __name__ == "__main__":
    db = MetricsDatabase()
    db.connect()
    db.create_schema()
    
    print("\nDatabase schema created at financial_metrics.db")
    print("\nTables created:")
    print("  - companies")
    print("  - filings")
    print("  - revenue_metrics")
    print("  - profitability_metrics")
    print("  - margin_metrics")
    print("  - balance_sheet_metrics")
    print("  - cash_flow_metrics")
    print("  - per_share_metrics")
    print("  - operational_metrics")
    print("  - valuation_metrics")
    print("  - all_metrics")
    
    db.close()
