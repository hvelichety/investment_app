"""
Test Script - Validates the database and pipeline components
"""

import os
import sys
import sqlite3
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database_manager import MetricsDatabase  # noqa: E402
from src.query_interface import MetricsQuery  # noqa: E402


def test_database_schema():
    """Test that database schema is correctly created"""
    print("Testing database schema...")
    
    db = MetricsDatabase("test_financial_metrics.db")
    db.connect()
    db.create_schema()
    
    cursor = db.cursor
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    expected_tables = [
        'all_metrics',
        'balance_sheet_metrics',
        'cash_flow_metrics',
        'companies',
        'filings',
        'margin_metrics',
        'operational_metrics',
        'per_share_metrics',
        'profitability_metrics',
        'revenue_metrics',
        'valuation_metrics'
    ]
    
    for table in expected_tables:
        if table in tables:
            print(f"  ✓ Table '{table}' exists")
        else:
            print(f"  ✗ Table '{table}' missing")
    
    db.close()
    return len(expected_tables) == len([t for t in expected_tables if t in tables])


def test_data_insertion():
    """Test inserting sample data"""
    print("\nTesting data insertion...")
    
    db = MetricsDatabase("test_financial_metrics.db")
    db.connect()
    
    company_id = db.insert_company("TEST", "0000000001", "Test Company Inc.")
    print(f"  ✓ Inserted company with ID: {company_id}")
    
    filing_id = db.insert_filing(company_id, "10-K", "2024-12-31")
    print(f"  ✓ Inserted filing with ID: {filing_id}")
    
    test_metrics = {
        'total_revenue': 1000000.0,
        'revenue_growth': 15.5,
        'gross_profit': 400000.0,
        'net_income': 150000.0,
        'gross_margin': 40.0,
        'net_margin': 15.0,
        'total_assets': 5000000.0,
        'cash_and_equivalents': 500000.0,
        'eps': 2.50,
        'employee_count': 5000
    }
    
    db.insert_metrics(filing_id, test_metrics)
    print(f"  ✓ Inserted {len(test_metrics)} metrics")
    
    result = db.get_company_metrics("TEST")
    print(f"  ✓ Retrieved {len(result)} rows of data")
    
    db.close()
    return True


def test_query_interface():
    """Test query interface functionality"""
    print("\nTesting query interface...")
    
    query = MetricsQuery("test_financial_metrics.db")
    
    companies = query.get_all_companies()
    print(f"  ✓ Retrieved {len(companies)} companies")
    
    metrics = query.get_all_metric_names()
    print(f"  ✓ Found {len(metrics)} unique metrics")
    
    overview = query.get_company_overview("TEST")
    print(f"  ✓ Generated company overview")
    
    query.close()
    return True


def test_export():
    """Test Excel export functionality"""
    print("\nTesting Excel export...")
    
    db = MetricsDatabase("test_financial_metrics.db")
    db.connect()
    
    try:
        db.export_to_excel("test_export.xlsx")
        print("  ✓ Excel export successful")
        result = True
    except Exception as e:
        print(f"  ✗ Excel export failed: {e}")
        result = False
    
    db.close()
    return result


def verify_real_database():
    """Verify the real database has expected structure"""
    print("\nVerifying real database structure...")
    
    try:
        # Default path resolves to data/financial_metrics.db
        query = MetricsQuery()
        
        companies = query.get_all_companies()
        print(f"  Companies in database: {len(companies)}")
        
        if not companies.empty:
            print(f"  Tickers: {companies['ticker'].tolist()}")
        
        metrics = query.get_all_metric_names()
        print(f"  Unique metrics: {len(metrics)}")
        
        query.close()
        return True
    except Exception as e:
        print(f"  Note: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("FINANCIAL METRICS DATABASE - TEST SUITE")
    print("=" * 60)
    
    results = []
    
    results.append(("Database Schema", test_database_schema()))
    results.append(("Data Insertion", test_data_insertion()))
    results.append(("Query Interface", test_query_interface()))
    results.append(("Excel Export", test_export()))
    results.append(("Real Database Structure", verify_real_database()))
    
    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name:30s}: {status}")
    
    total_passed = sum(1 for _, passed in results if passed)
    print(f"\nTotal: {total_passed}/{len(results)} tests passed")
    
    import os
    if os.path.exists("test_financial_metrics.db"):
        os.remove("test_financial_metrics.db")
        print("\n✓ Cleaned up test database")
    
    if os.path.exists("test_export.xlsx"):
        os.remove("test_export.xlsx")
        print("✓ Cleaned up test export file")
