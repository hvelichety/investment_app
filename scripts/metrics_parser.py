"""
Financial Metrics Parser
Extracts key financial metrics from SEC filings and company data
"""

import re
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup
from datetime import datetime
import json


class MetricsParser:
    def __init__(self):
        self.metric_patterns = {
            'total_revenue': [
                r'(?:total\s+)?(?:net\s+)?(?:revenues?|sales)\s*[\$\s]*(\d+[,\d]*\.?\d*)\s*(?:million|billion)?',
            ],
            'revenue_growth': [
                r'revenue\s+growth\s+(?:of\s+|rate\s+)?(\d+\.?\d*)%',
            ],
            'gross_profit': [
                r'gross\s+profit\s*[\$\s]*(\d+[,\d]*\.?\d*)\s*(?:million|billion)?',
            ],
            'operating_income': [
                r'(?:operating\s+)?(?:income\s+from\s+operations|operating\s+income)\s*[\$\s]*(\d+[,\d]*\.?\d*)',
            ],
            'net_income': [
                r'net\s+(?:income|earnings?|profit)\s*[\$\s]*(\d+[,\d]*\.?\d*)\s*(?:million|billion)?',
            ],
            'ebitda': [
                r'EBITDA\s*[\$\s]*(\d+[,\d]*\.?\d*)\s*(?:million|billion)?',
            ],
            'gross_margin': [
                r'gross\s+(?:profit\s+)?margin\s+(?:of\s+)?(\d+\.?\d*)%',
            ],
            'operating_margin': [
                r'operating\s+margin\s+(?:of\s+)?(\d+\.?\d*)%',
            ],
            'net_margin': [
                r'net\s+(?:profit\s+)?margin\s+(?:of\s+)?(\d+\.?\d*)%',
            ],
            'total_assets': [
                r'total\s+assets\s*[\$\s]*(\d+[,\d]*\.?\d*)\s*(?:million|billion)?',
            ],
            'total_liabilities': [
                r'total\s+liabilities\s*[\$\s]*(\d+[,\d]*\.?\d*)',
            ],
            'stockholders_equity': [
                r'(?:total\s+)?(?:stockholders?\s+|shareholders?\s+)?equity\s*[\$\s]*(\d+[,\d]*\.?\d*)',
            ],
            'cash_and_equivalents': [
                r'cash\s+and\s+(?:cash\s+)?equivalents\s*[\$\s]*(\d+[,\d]*\.?\d*)',
            ],
            'total_debt': [
                r'total\s+debt\s*[\$\s]*(\d+[,\d]*\.?\d*)',
            ],
            'operating_cash_flow': [
                r'(?:net\s+)?cash\s+(?:provided\s+by|from)\s+operating\s+activities\s*[\$\s]*(\d+[,\d]*\.?\d*)',
            ],
            'free_cash_flow': [
                r'free\s+cash\s+flow\s*[\$\s]*(\d+[,\d]*\.?\d*)',
            ],
            'capex': [
                r'capital\s+expenditures?\s*[\$\s]*(\d+[,\d]*\.?\d*)',
            ],
            'eps': [
                r'(?:basic\s+)?(?:earnings|income)\s+per\s+share\s*[\$\s]*(\d+\.?\d*)',
            ],
            'book_value_per_share': [
                r'book\s+value\s+per\s+share\s*[\$\s]*(\d+\.?\d*)',
            ],
            'research_and_development': [
                r'research\s+and\s+development\s*[\$\s]*(\d+[,\d]*\.?\d*)',
            ],
            'sales_and_marketing': [
                r'(?:sales\s+and\s+marketing|selling\s+and\s+marketing)\s*[\$\s]*(\d+[,\d]*\.?\d*)',
            ],
            'employee_count': [
                r'(?:approximately\s+)?(\d+[,\d]*)\s+(?:full-time\s+)?employees',
            ],
            'market_cap': [
                r'market\s+capitalization\s*[\$\s]*(\d+[,\d]*\.?\d*)\s*(?:million|billion)?',
            ]
        }
    
    def clean_number(self, value_str: str) -> Optional[float]:
        """Clean and convert string to number"""
        if not value_str:
            return None
        value_str = value_str.replace(',', '').strip()
        try:
            return float(value_str)
        except (ValueError, AttributeError):
            return None
    
    def extract_text_from_html(self, html_content: str) -> str:
        """Extract clean text from HTML content"""
        soup = BeautifulSoup(html_content, 'lxml')
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        return text
    
    def extract_metrics_from_text(self, text: str) -> Dict[str, Any]:
        """Extract all metrics from text using patterns"""
        metrics = {}
        text_lower = text.lower()
        
        for metric_name, patterns in self.metric_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text_lower, re.IGNORECASE)
                for match in matches:
                    if match.group(1):
                        value = self.clean_number(match.group(1))
                        if value is not None:
                            if metric_name not in metrics:
                                metrics[metric_name] = []
                            metrics[metric_name].append({
                                'value': value,
                                'context': text[max(0, match.start()-50):min(len(text), match.end()+50)]
                            })
        
        consolidated_metrics = {}
        for metric_name, values in metrics.items():
            if values:
                consolidated_metrics[metric_name] = values[0]['value']
                consolidated_metrics[f"{metric_name}_all_values"] = [v['value'] for v in values]
        
        return consolidated_metrics
    
    def extract_all_metrics(self, filing_content: str, filing_type: str, filing_date: str) -> Dict:
        """Extract comprehensive metrics from a filing"""
        text = self.extract_text_from_html(filing_content)
        metrics = self.extract_metrics_from_text(text)
        
        return {
            'filing_type': filing_type,
            'filing_date': filing_date,
            'metrics': metrics,
            'text_length': len(text),
            'extraction_timestamp': datetime.now().isoformat()
        }
    
    def parse_company_filings(self, company_data: Dict, content_map: Dict = None) -> Dict:
        """Parse all filings for a company and extract metrics"""
        ticker = company_data.get('ticker')
        parsed_data = {
            'ticker': ticker,
            'cik': company_data.get('cik'),
            'filings_parsed': []
        }
        
        filings = company_data.get('filings', {})
        
        for filing_type, filing_list in filings.items():
            for filing in filing_list:
                if filing.get('content_fetched') and filing.get('content_preview'):
                    print(f"  Parsing {filing_type} from {filing['date']}...")
                    content = filing.get('content_preview', '')
                    if content:
                        metrics_data = self.extract_all_metrics(content, filing_type, filing['date'])
                        parsed_data['filings_parsed'].append(metrics_data)
        
        return parsed_data


if __name__ == "__main__":
    parser = MetricsParser()
    
    try:
        with open('sec_data_raw.json', 'r') as f:
            raw_data = json.load(f)
        
        parsed_results = {}
        for ticker, company_data in raw_data.items():
            print(f"\nParsing {ticker}...")
            parsed_results[ticker] = parser.parse_company_filings(company_data)
        
        with open('parsed_metrics.json', 'w') as f:
            json.dump(parsed_results, f, indent=2)
        
        print("\n✓ Parsed data saved to parsed_metrics.json")
    
    except FileNotFoundError:
        print("Error: sec_data_raw.json not found. Run sec_data_fetcher.py first.")
