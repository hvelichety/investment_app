"""
Financial Metrics Chatbot
AI-powered chatbot with natural language queries and visualizations
"""

from .query_interface import MetricsQuery
import pandas as pd
from typing import Dict, List, Optional, Tuple
import re
import json


class FinancialChatbot:
    def __init__(self, db_path: str = None):
        self.query = MetricsQuery(db_path)
        self.companies = self.query.get_all_companies()['ticker'].tolist()
        
    def close(self):
        self.query.close()
    
    def parse_query(self, user_input: str) -> Dict:
        """Parse user query to understand intent"""
        user_input_lower = user_input.lower()
        
        # Extract ticker if mentioned
        ticker = None
        for company in self.companies:
            if company.lower() in user_input_lower:
                ticker = company
                break

        # Alias common SpaceX references to SPCX
        if ticker is None and any(
            term in user_input_lower
            for term in ['spacex', 'starlink', 'starship']
        ):
            ticker = 'SPCX'
        
        query_type = None
        chart_type = None

        wants_segments = any(
            word in user_input_lower
            for word in [
                'segment', 'segments', 'breakdown', 'broken down',
                'by segment', 'starlink', 'connectivity', 'launch services',
                'ai / other', 'ai/other',
            ]
        )
        
        # Determine query type
        if wants_segments and (ticker or 'spcx' in user_input_lower or 'spacex' in user_input_lower):
            query_type = 'segments'
            ticker = ticker or 'SPCX'
        elif any(word in user_input_lower for word in ['compare', 'comparison', 'vs', 'versus']):
            query_type = 'compare'
        elif any(word in user_input_lower for word in ['trend', 'history', 'over time', 'historical']):
            query_type = 'trend'
        elif any(word in user_input_lower for word in ['latest', 'current', 'recent']):
            query_type = 'latest'
        elif any(word in user_input_lower for word in ['all companies', 'all', 'overview']):
            query_type = 'overview'
        elif ticker:
            query_type = 'company_detail'
        else:
            query_type = 'overview'
        
        # Determine metric
        metric = None
        if 'revenue' in user_input_lower or wants_segments:
            metric = 'revenue'
        elif 'profit' in user_input_lower or 'income' in user_input_lower:
            metric = 'profit'
        elif 'margin' in user_input_lower:
            metric = 'margin'
        elif 'cash' in user_input_lower:
            metric = 'cash_flow'
        elif 'employee' in user_input_lower:
            metric = 'employees'
        
        return {
            'type': query_type,
            'ticker': ticker,
            'metric': metric,
            'original': user_input
        }
    
    def generate_response(self, parsed_query: Dict) -> Tuple[str, Optional[str], Optional[Dict]]:
        """Generate text response and visualization"""
        query_type = parsed_query['type']
        ticker = parsed_query['ticker']
        metric = parsed_query['metric']
        
        try:
            if query_type == 'segments' and ticker:
                return self.get_segment_breakdown(ticker)
            if query_type == 'overview':
                return self.get_overview()
            elif query_type == 'compare':
                return self.compare_companies(metric)
            elif query_type == 'trend' and ticker:
                return self.get_trend(ticker, metric)
            elif query_type == 'company_detail' and ticker:
                # Prefer segment pie when asking about SPCX revenue specifically
                original = (parsed_query.get('original') or '').lower()
                if (
                    metric == 'revenue'
                    and self.query.has_segment_data(ticker)
                    and any(w in original for w in ['revenue', 'segment', 'breakdown'])
                ):
                    return self.get_segment_breakdown(ticker)
                return self.get_company_detail(ticker)
            elif query_type == 'latest' and ticker:
                return self.get_latest_metrics(ticker)
            else:
                return self.get_overview()
        except Exception as e:
            return f"I encountered an error: {str(e)}", None, None

    def _format_profitability(self, status: Optional[str]) -> str:
        mapping = {
            'profitable': 'Profitable (strong)',
            'near_breakeven': 'Near break-even / modest losses',
            'loss_making': 'Large losses',
        }
        if not status:
            return 'n/a'
        return mapping.get(status, status.replace('_', ' ').title())

    def get_segment_breakdown(self, ticker: str) -> Tuple[str, Optional[str], Optional[Dict]]:
        """Return operating-segment revenue mix for a company."""
        df = self.query.get_latest_segment_breakdown(ticker)
        if df.empty:
            return (
                f"No segment revenue data is available for {ticker} yet.",
                None,
                None,
            )

        filing_date = df.iloc[0]['filing_date']
        total_revenue = df['revenue'].sum()
        response = f"**🧩 {ticker} Revenue by Segment ({filing_date})**\n\n"
        response += f"**Total (sum of segments):** ${total_revenue/1e9:.2f}B\n\n"

        for _, row in df.iterrows():
            share = row['revenue_share_pct']
            share_txt = f"{share:.0f}%" if pd.notna(share) else "n/a"
            response += (
                f"**{row['segment_name']}** — ${row['revenue']/1e9:.2f}B "
                f"({share_txt})\n"
                f"- Profitability: {self._format_profitability(row.get('profitability_status'))}\n"
            )
            if pd.notna(row.get('notes')) and row.get('notes'):
                response += f"- {row['notes']}\n"
            response += "\n"

        chart_data = [{
            'values': (df['revenue'] / 1e9).tolist(),
            'labels': df['segment_name'].tolist(),
            'type': 'pie',
            'hole': 0.35,
            'textinfo': 'label+percent',
        }]
        chart_config = {
            'title': f'{ticker} Revenue Segments ({filing_date})',
        }
        return response, 'pie', {'data': chart_data, 'layout': chart_config}
    
    def get_overview(self) -> Tuple[str, str, Dict]:
        """Get overview of all companies"""
        revenue_df = self.query.get_revenue_comparison()
        latest = revenue_df.groupby('ticker').first().sort_values('total_revenue', ascending=False)
        
        response = "**📊 Financial Database Overview**\n\n"
        response += f"I have data for **{len(self.companies)} companies**: {', '.join(self.companies)}\n\n"
        response += "**Latest Revenue Rankings:**\n"
        
        for i, (ticker, row) in enumerate(latest.iterrows(), 1):
            if pd.notna(row['total_revenue']):
                response += f"{i}. **{ticker}**: ${row['total_revenue']/1e9:.2f}B\n"
        
        # Create bar chart
        chart_data = {
            'x': latest.index.tolist(),
            'y': (latest['total_revenue']/1e9).tolist(),
            'type': 'bar',
            'name': 'Revenue (Billions)'
        }
        
        chart_config = {
            'title': 'Revenue Comparison - All Companies',
            'xaxis': {'title': 'Company'},
            'yaxis': {'title': 'Revenue ($ Billions)'}
        }
        
        return response, 'bar', {'data': [chart_data], 'layout': chart_config}
    
    def compare_companies(self, metric: Optional[str]) -> Tuple[str, str, Dict]:
        """Compare companies across metrics"""
        if metric == 'profit' or metric == 'margin':
            prof_df = self.query.get_profitability_comparison()
            latest = prof_df.groupby('ticker').first()
            
            response = "**💰 Profitability Comparison**\n\n"
            sorted_df = latest.sort_values('net_margin', ascending=False)
            
            for ticker, row in sorted_df.iterrows():
                if pd.notna(row['net_margin']):
                    response += f"**{ticker}**: {row['net_margin']:.2f}% margin, ${row['net_income']/1e9:.2f}B net income\n"
            
            chart_data = {
                'x': sorted_df.index.tolist(),
                'y': sorted_df['net_margin'].tolist(),
                'type': 'bar',
                'name': 'Net Margin %'
            }
            
            chart_config = {
                'title': 'Net Profit Margin Comparison',
                'xaxis': {'title': 'Company'},
                'yaxis': {'title': 'Net Margin (%)'}
            }
            
            return response, 'bar', {'data': [chart_data], 'layout': chart_config}
        else:
            return self.get_overview()
    
    def get_trend(self, ticker: str, metric: Optional[str]) -> Tuple[str, str, Dict]:
        """Get trend data for a company"""
        df = self.query.db.get_company_metrics(ticker)
        
        if df.empty:
            return f"No data found for {ticker}", None, None
        
        df = df.sort_values('filing_date')
        
        response = f"**📈 {ticker} Trend Analysis**\n\n"
        
        if metric == 'revenue' or metric is None:
            if 'total_revenue' in df.columns:
                response += "**Revenue Over Time:**\n"
                for _, row in df.iterrows():
                    if pd.notna(row['total_revenue']):
                        response += f"- {row['filing_date']}: ${row['total_revenue']/1e9:.2f}B\n"
                
                chart_data = {
                    'x': df['filing_date'].tolist(),
                    'y': (df['total_revenue']/1e9).fillna(0).tolist(),
                    'type': 'scatter',
                    'mode': 'lines+markers',
                    'name': 'Revenue'
                }
                
                chart_config = {
                    'title': f'{ticker} Revenue Trend',
                    'xaxis': {'title': 'Date'},
                    'yaxis': {'title': 'Revenue ($ Billions)'}
                }
                
                return response, 'line', {'data': [chart_data], 'layout': chart_config}
        
        return response, None, None
    
    def get_company_detail(self, ticker: str) -> Tuple[str, str, Dict]:
        """Get detailed company information"""
        overview = self.query.get_company_overview(ticker)
        
        if 'error' in overview:
            return f"No data found for {ticker}", None, None
        
        df = self.query.db.get_company_metrics(ticker)
        latest = df.iloc[0] if not df.empty else None
        
        response = f"**🏢 {ticker} Company Profile**\n\n"
        response += f"**Filings**: {overview['filings_count']} reports\n"
        response += f"**Date Range**: {overview['date_range']['earliest']} to {overview['date_range']['latest']}\n\n"
        
        if latest is not None:
            response += f"**Latest Metrics ({latest['filing_date']}):**\n"
            if pd.notna(latest.get('total_revenue')):
                response += f"- Revenue: ${latest['total_revenue']/1e9:.2f}B\n"
            if pd.notna(latest.get('net_income')):
                response += f"- Net Income: ${latest['net_income']/1e9:.2f}B\n"
            if pd.notna(latest.get('net_margin')):
                response += f"- Net Margin: {latest['net_margin']:.2f}%\n"
            if pd.notna(latest.get('total_assets')):
                response += f"- Total Assets: ${latest['total_assets']/1e9:.2f}B\n"
            if pd.notna(latest.get('employee_count')):
                response += f"- Employees: {int(latest['employee_count']):,}\n"

        # Surface segment mix when available (e.g. SPCX)
        segments = self.query.get_latest_segment_breakdown(ticker)
        if not segments.empty:
            response += "\n**Revenue by Segment:**\n"
            for _, row in segments.iterrows():
                share = row['revenue_share_pct']
                share_txt = f"{share:.0f}%" if pd.notna(share) else "n/a"
                response += (
                    f"- {row['segment_name']}: ${row['revenue']/1e9:.2f}B "
                    f"({share_txt}) — {self._format_profitability(row.get('profitability_status'))}\n"
                )
            chart_data = [{
                'values': (segments['revenue'] / 1e9).tolist(),
                'labels': segments['segment_name'].tolist(),
                'type': 'pie',
                'hole': 0.35,
                'textinfo': 'label+percent',
            }]
            chart_config = {
                'title': f'{ticker} Revenue Segments ({segments.iloc[0]["filing_date"]})',
            }
            return response, 'pie', {'data': chart_data, 'layout': chart_config}
        
        # Create multi-metric chart
        df_sorted = df.sort_values('filing_date')
        
        chart_data = []
        if 'total_revenue' in df.columns:
            chart_data.append({
                'x': df_sorted['filing_date'].tolist(),
                'y': (df_sorted['total_revenue']/1e9).fillna(0).tolist(),
                'type': 'scatter',
                'mode': 'lines+markers',
                'name': 'Revenue (B)'
            })
        
        if 'net_income' in df.columns:
            chart_data.append({
                'x': df_sorted['filing_date'].tolist(),
                'y': (df_sorted['net_income']/1e9).fillna(0).tolist(),
                'type': 'scatter',
                'mode': 'lines+markers',
                'name': 'Net Income (B)'
            })
        
        chart_config = {
            'title': f'{ticker} Financial Performance',
            'xaxis': {'title': 'Date'},
            'yaxis': {'title': 'Amount ($ Billions)'}
        }
        
        return response, 'line', {'data': chart_data, 'layout': chart_config}
    
    def get_latest_metrics(self, ticker: str) -> Tuple[str, str, Dict]:
        """Get latest metrics for a company"""
        latest_df = self.query.get_latest_metrics(ticker)
        
        if latest_df.empty:
            return f"No data found for {ticker}", None, None
        
        filing_date = latest_df.iloc[0]['filing_date']
        
        response = f"**📊 {ticker} Latest Metrics ({filing_date})**\n\n"
        
        metrics_dict = {}
        for _, row in latest_df.iterrows():
            metric_name = row['metric_name']
            metric_value = row['metric_value']
            metrics_dict[metric_name] = metric_value
            
            if pd.notna(metric_value):
                if metric_value > 1e9:
                    response += f"- **{metric_name}**: ${metric_value/1e9:.2f}B\n"
                elif metric_value > 1e6:
                    response += f"- **{metric_name}**: ${metric_value/1e6:.2f}M\n"
                elif 'margin' in metric_name or 'percent' in metric_name:
                    response += f"- **{metric_name}**: {metric_value:.2f}%\n"
                else:
                    response += f"- **{metric_name}**: {metric_value:,.2f}\n"
        
        # Create pie chart for margins
        margin_data = []
        margin_labels = []
        
        for key in ['gross_margin', 'operating_margin', 'net_margin']:
            if key in metrics_dict and pd.notna(metrics_dict[key]):
                margin_labels.append(key.replace('_', ' ').title())
                margin_data.append(metrics_dict[key])
        
        if margin_data:
            chart_data = [{
                'values': margin_data,
                'labels': margin_labels,
                'type': 'pie',
                'hole': 0.4
            }]
            
            chart_config = {
                'title': f'{ticker} Profit Margins Breakdown'
            }
            
            return response, 'pie', {'data': chart_data, 'layout': chart_config}
        
        return response, None, None
    
    def chat(self, user_input: str) -> Dict:
        """Main chat interface"""
        parsed = self.parse_query(user_input)
        response, chart_type, chart_config = self.generate_response(parsed)
        
        return {
            'response': response,
            'chart_type': chart_type,
            'chart_config': chart_config,
            'parsed_query': parsed
        }


if __name__ == "__main__":
    chatbot = FinancialChatbot()
    
    print("Financial Metrics Chatbot")
    print("=" * 50)
    print("\nExample queries:")
    print("  - Show me an overview")
    print("  - Compare profitability of all companies")
    print("  - Show NVDA revenue trend")
    print("  - What are the latest metrics for TSLA?")
    print("  - Compare revenue across companies")
    print("  - Show SPCX revenue by segment")
    print("\nType 'quit' to exit\n")
    
    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'bye']:
            print("Goodbye!")
            break
        
        if not user_input:
            continue
        
        result = chatbot.chat(user_input)
        print(f"\nBot: {result['response']}")
        
        if result['chart_type']:
            print(f"[Chart: {result['chart_type']} chart would be displayed here]")
        
        print()
    
    chatbot.close()
