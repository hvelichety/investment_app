"""
SEC Data Fetcher
Retrieves S-1 and 10-K filings from SEC EDGAR for specified companies
"""

import requests
import time
import json
import re
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from datetime import datetime


class SECDataFetcher:
    def __init__(self, user_agent: str = "Financial Metrics Database [email protected]"):
        self.base_url = "https://www.sec.gov"
        self.headers = {"User-Agent": user_agent}
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
    def get_cik(self, ticker: str) -> Optional[str]:
        """Get CIK number for a given ticker symbol"""
        ticker_url = f"{self.base_url}/cgi-bin/browse-edgar"
        params = {
            "action": "getcompany",
            "CIK": ticker,
            "type": "",
            "dateb": "",
            "owner": "exclude",
            "count": "10",
            "search_text": ""
        }
        
        try:
            response = self.session.get(ticker_url, params=params)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            cik_element = soup.find('span', {'class': 'companyName'})
            
            if cik_element:
                cik_match = re.search(r'CIK=(\d+)', str(cik_element))
                if cik_match:
                    return cik_match.group(1).zfill(10)
            
            company_info_url = f"{self.base_url}/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}&type=&dateb=&owner=exclude&count=10"
            response = self.session.get(company_info_url)
            cik_match = re.search(r'CIK=(\d{10})', response.text)
            if cik_match:
                return cik_match.group(1)
                
        except Exception as e:
            print(f"Error getting CIK for {ticker}: {e}")
        
        return None
    
    def get_company_filings(self, cik: str, filing_type: str = "10-K", count: int = 5) -> List[Dict]:
        """Get list of filings for a company"""
        url = f"{self.base_url}/cgi-bin/browse-edgar"
        params = {
            "action": "getcompany",
            "CIK": cik,
            "type": filing_type,
            "dateb": "",
            "owner": "exclude",
            "count": count,
            "search_text": ""
        }
        
        filings = []
        try:
            time.sleep(0.1)
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            filing_table = soup.find('table', {'class': 'tableFile2'})
            
            if filing_table:
                rows = filing_table.find_all('tr')[1:]
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 4:
                        filing_type_col = cols[0].text.strip()
                        filing_date = cols[3].text.strip()
                        
                        doc_link = cols[1].find('a', {'id': 'documentsbutton'})
                        if doc_link:
                            doc_url = self.base_url + doc_link['href']
                            
                            filings.append({
                                'type': filing_type_col,
                                'date': filing_date,
                                'documents_url': doc_url
                            })
        
        except Exception as e:
            print(f"Error getting filings for CIK {cik}: {e}")
        
        return filings
    
    def get_filing_document_url(self, documents_url: str) -> Optional[str]:
        """Get the main filing document URL from the documents page"""
        try:
            time.sleep(0.1)
            response = self.session.get(documents_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            doc_table = soup.find('table', {'class': 'tableFile'})
            
            if doc_table:
                rows = doc_table.find_all('tr')[1:]
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 3:
                        doc_type = cols[3].text.strip() if len(cols) > 3 else ""
                        description = cols[1].text.strip()
                        
                        if any(x in description.upper() for x in ['10-K', '10K', 'S-1', 'S1']) or \
                           any(x in doc_type.upper() for x in ['10-K', '10K', 'S-1', 'S1']):
                            doc_link = cols[2].find('a')
                            if doc_link:
                                return self.base_url + doc_link['href']
        
        except Exception as e:
            print(f"Error getting document URL: {e}")
        
        return None
    
    def fetch_filing_content(self, filing_url: str) -> Optional[str]:
        """Fetch the content of a filing document"""
        try:
            time.sleep(0.15)
            response = self.session.get(filing_url)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching filing content: {e}")
            return None
    
    def get_company_data(self, ticker: str) -> Dict:
        """Get comprehensive company filing data"""
        print(f"\nFetching data for {ticker}...")
        
        cik = self.get_cik(ticker)
        if not cik:
            print(f"Could not find CIK for {ticker}")
            return {"ticker": ticker, "error": "CIK not found"}
        
        print(f"CIK for {ticker}: {cik}")
        
        company_data = {
            "ticker": ticker,
            "cik": cik,
            "filings": {}
        }
        
        for filing_type in ["10-K", "S-1"]:
            print(f"Fetching {filing_type} filings...")
            filings = self.get_company_filings(cik, filing_type, count=3)
            
            if filings:
                company_data["filings"][filing_type] = []
                for filing in filings[:1]:
                    doc_url = self.get_filing_document_url(filing['documents_url'])
                    if doc_url:
                        content = self.fetch_filing_content(doc_url)
                        filing['document_url'] = doc_url
                        filing['content_length'] = len(content) if content else 0
                        filing['content_fetched'] = content is not None
                        
                        if content:
                            filing['content_preview'] = content
                        
                        company_data["filings"][filing_type].append(filing)
                        print(f"  - {filing_type} from {filing['date']}: {'✓' if content else '✗'}")
        
        return company_data


if __name__ == "__main__":
    fetcher = SECDataFetcher()
    
    companies = ["AMD", "CRM", "GOOG", "NVDA", "RH", "SPCX", "TSLA"]
    
    all_data = {}
    for ticker in companies:
        data = fetcher.get_company_data(ticker)
        all_data[ticker] = data
        time.sleep(0.5)
    
    with open('sec_data_raw.json', 'w') as f:
        json.dump(all_data, f, indent=2)
    
    print("\n✓ Data saved to sec_data_raw.json")
