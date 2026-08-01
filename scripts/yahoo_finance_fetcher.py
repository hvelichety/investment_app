"""
Yahoo Finance Data Fetcher
Retrieves real financial data from Yahoo Finance API
"""

import yfinance as yf
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
import time


class YahooFinanceDataFetcher:
    def __init__(self):
        self.session = None
    
    def get_company_info(self, ticker: str) -> Dict:
        """Get basic company information"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            return {
                'ticker': ticker,
                'company_name': info.get('longName', info.get('shortName', ticker)),
                'sector': info.get('sector'),
                'industry': info.get('industry'),
                'website': info.get('website'),
                'description': info.get('longBusinessSummary'),
                'cik': info.get('cik'),
                'employees': info.get('fullTimeEmployees'),
                'market_cap': info.get('marketCap'),
                'exchange': info.get('exchange')
            }
        except Exception as e:
            print(f"Error getting info for {ticker}: {e}")
            return {'ticker': ticker, 'error': str(e)}
    
    def get_financial_statements(self, ticker: str) -> Dict:
        """Get income statement, balance sheet, and cash flow data"""
        try:
            stock = yf.Ticker(ticker)
            
            # Get financial statements
            income_stmt = stock.financials  # Annual income statement
            balance_sheet = stock.balance_sheet  # Annual balance sheet
            cash_flow = stock.cashflow  # Annual cash flow
            
            quarterly_income = stock.quarterly_financials
            quarterly_balance = stock.quarterly_balance_sheet
            quarterly_cashflow = stock.quarterly_cashflow
            
            return {
                'ticker': ticker,
                'annual_income_statement': income_stmt,
                'annual_balance_sheet': balance_sheet,
                'annual_cash_flow': cash_flow,
                'quarterly_income_statement': quarterly_income,
                'quarterly_balance_sheet': quarterly_balance,
                'quarterly_cash_flow': quarterly_cashflow
            }
        except Exception as e:
            print(f"Error getting financials for {ticker}: {e}")
            return {'ticker': ticker, 'error': str(e)}
    
    def extract_metrics_from_financials(self, ticker: str) -> Dict:
        """Extract all available metrics from financial statements"""
        print(f"\nFetching data for {ticker}...")
        
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Get financial statements
            income_stmt = stock.financials
            balance_sheet = stock.balance_sheet
            cash_flow = stock.cashflow
            
            metrics = {
                'ticker': ticker,
                'company_name': info.get('longName', info.get('shortName', ticker)),
                'cik': str(info.get('cik', '')).zfill(10) if info.get('cik') else None,
                'filings': []
            }
            
            # Process each year of data
            if not income_stmt.empty:
                for date in income_stmt.columns:
                    filing_date = date.strftime('%Y-%m-%d')
                    year = date.year
                    
                    print(f"  Processing data for {year}...")
                    
                    filing_metrics = {}
                    
                    # Income Statement Metrics
                    if 'Total Revenue' in income_stmt.index:
                        filing_metrics['total_revenue'] = income_stmt.loc['Total Revenue', date]
                    
                    if 'Gross Profit' in income_stmt.index:
                        filing_metrics['gross_profit'] = income_stmt.loc['Gross Profit', date]
                    
                    if 'Operating Income' in income_stmt.index:
                        filing_metrics['operating_income'] = income_stmt.loc['Operating Income', date]
                    elif 'EBIT' in income_stmt.index:
                        filing_metrics['operating_income'] = income_stmt.loc['EBIT', date]
                    
                    if 'Net Income' in income_stmt.index:
                        filing_metrics['net_income'] = income_stmt.loc['Net Income', date]
                    
                    if 'EBITDA' in income_stmt.index:
                        filing_metrics['ebitda'] = income_stmt.loc['EBITDA', date]
                    
                    if 'Research And Development' in income_stmt.index:
                        filing_metrics['research_and_development'] = income_stmt.loc['Research And Development', date]
                    elif 'Research Development' in income_stmt.index:
                        filing_metrics['research_and_development'] = income_stmt.loc['Research Development', date]
                    
                    if 'Selling General And Administration' in income_stmt.index:
                        filing_metrics['sales_and_marketing'] = income_stmt.loc['Selling General And Administration', date]
                    
                    # Calculate margins
                    if 'total_revenue' in filing_metrics and filing_metrics['total_revenue']:
                        if 'gross_profit' in filing_metrics:
                            filing_metrics['gross_margin'] = (filing_metrics['gross_profit'] / filing_metrics['total_revenue']) * 100
                        if 'operating_income' in filing_metrics:
                            filing_metrics['operating_margin'] = (filing_metrics['operating_income'] / filing_metrics['total_revenue']) * 100
                        if 'net_income' in filing_metrics:
                            filing_metrics['net_margin'] = (filing_metrics['net_income'] / filing_metrics['total_revenue']) * 100
                    
                    # Balance Sheet Metrics
                    if not balance_sheet.empty and date in balance_sheet.columns:
                        if 'Total Assets' in balance_sheet.index:
                            filing_metrics['total_assets'] = balance_sheet.loc['Total Assets', date]
                        
                        if 'Total Liabilities Net Minority Interest' in balance_sheet.index:
                            filing_metrics['total_liabilities'] = balance_sheet.loc['Total Liabilities Net Minority Interest', date]
                        elif 'Total Liabilities' in balance_sheet.index:
                            filing_metrics['total_liabilities'] = balance_sheet.loc['Total Liabilities', date]
                        
                        if 'Stockholders Equity' in balance_sheet.index:
                            filing_metrics['stockholders_equity'] = balance_sheet.loc['Stockholders Equity', date]
                        elif 'Total Equity Gross Minority Interest' in balance_sheet.index:
                            filing_metrics['stockholders_equity'] = balance_sheet.loc['Total Equity Gross Minority Interest', date]
                        
                        if 'Cash And Cash Equivalents' in balance_sheet.index:
                            filing_metrics['cash_and_equivalents'] = balance_sheet.loc['Cash And Cash Equivalents', date]
                        
                        if 'Total Debt' in balance_sheet.index:
                            filing_metrics['total_debt'] = balance_sheet.loc['Total Debt', date]
                        elif 'Long Term Debt' in balance_sheet.index and 'Current Debt' in balance_sheet.index:
                            filing_metrics['total_debt'] = balance_sheet.loc['Long Term Debt', date] + balance_sheet.loc['Current Debt', date]
                    
                    # Cash Flow Metrics
                    if not cash_flow.empty and date in cash_flow.columns:
                        if 'Operating Cash Flow' in cash_flow.index:
                            filing_metrics['operating_cash_flow'] = cash_flow.loc['Operating Cash Flow', date]
                        
                        if 'Free Cash Flow' in cash_flow.index:
                            filing_metrics['free_cash_flow'] = cash_flow.loc['Free Cash Flow', date]
                        
                        if 'Capital Expenditure' in cash_flow.index:
                            filing_metrics['capex'] = abs(cash_flow.loc['Capital Expenditure', date])
                    
                    # Additional info metrics
                    filing_metrics['market_cap'] = info.get('marketCap')
                    filing_metrics['employee_count'] = info.get('fullTimeEmployees')
                    
                    # Per-share metrics
                    shares_outstanding = info.get('sharesOutstanding')
                    if shares_outstanding and 'net_income' in filing_metrics:
                        filing_metrics['eps'] = filing_metrics['net_income'] / shares_outstanding
                    
                    if shares_outstanding and 'stockholders_equity' in filing_metrics:
                        filing_metrics['book_value_per_share'] = filing_metrics['stockholders_equity'] / shares_outstanding
                    
                    # Clean up NaN values
                    clean_metrics = {}
                    for key, value in filing_metrics.items():
                        if pd.notna(value):
                            clean_metrics[key] = float(value) if isinstance(value, (int, float)) else value
                    
                    metrics['filings'].append({
                        'filing_type': '10-K',
                        'filing_date': filing_date,
                        'year': year,
                        'metrics': clean_metrics
                    })
            
            print(f"  ✓ Extracted {len(metrics['filings'])} years of data")
            return metrics
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            return {'ticker': ticker, 'error': str(e)}
    
    def get_all_companies_data(self, tickers: List[str]) -> Dict:
        """Get data for multiple companies"""
        all_data = {}
        
        for ticker in tickers:
            data = self.extract_metrics_from_financials(ticker)
            all_data[ticker] = data
            time.sleep(0.5)  # Rate limiting
        
        return all_data


if __name__ == "__main__":
    fetcher = YahooFinanceDataFetcher()
    
    # Test with one company
    test_ticker = "NVDA"
    print(f"Testing with {test_ticker}...")
    
    data = fetcher.extract_metrics_from_financials(test_ticker)
    
    if 'error' not in data:
        print(f"\n✓ Successfully fetched data for {data['company_name']}")
        print(f"  CIK: {data.get('cik')}")
        print(f"  Years of data: {len(data['filings'])}")
        
        if data['filings']:
            latest = data['filings'][0]
            print(f"\n  Latest filing ({latest['filing_date']}):")
            for metric, value in list(latest['metrics'].items())[:10]:
                print(f"    {metric}: {value:,.2f}" if isinstance(value, (int, float)) else f"    {metric}: {value}")
    else:
        print(f"\n✗ Error: {data['error']}")
