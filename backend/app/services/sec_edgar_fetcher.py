"""
SEC EDGAR API Client for Insider Trading Data (Form 4)

This service fetches insider trading data from the SEC EDGAR database.
EDGAR (Electronic Data Gathering, Analysis, and Retrieval) is the official
SEC filing system.

Data Source: https://www.sec.gov/edgar/sec-api-documentation
Rate Limit: 10 requests/second (we use 5 to be safe)

Form 4 Filings:
- Required for all insider trades (officers, directors, >10% shareholders)
- Must be filed within 2 business days of the trade
- Contains: insider info, transaction type, shares, price, dates
"""

import requests
import time
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import xml.etree.ElementTree as ET
from urllib.parse import quote

logger = logging.getLogger(__name__)


class SECEdgarFetcher:
    """
    SEC EDGAR API client for fetching insider trading data (Form 4 filings)

    Rate limited to 5 requests/second (official limit is 10/sec)
    """

    # SEC EDGAR API endpoints
    BASE_URL = "https://www.sec.gov"
    DATA_BASE_URL = "https://data.sec.gov"  # For JSON submissions API
    COMPANY_TICKERS_URL = f"{BASE_URL}/Files/edgar/data/company_tickers.json"
    COMPANY_SUBMISSIONS_URL = f"{BASE_URL}/data/sec-api-documentation"  # Needs CIK
    SEARCH_API_URL = "https://efts.sec.gov/LATEST/search-index"

    # User-Agent required by SEC
    USER_AGENT = "StockAnalyzer stock-analyzer@example.com"

    def __init__(self, requests_per_second: int = 5):
        """
        Initialize SEC EDGAR fetcher

        Args:
            requests_per_second: Rate limit (default: 5, max: 10)
        """
        self.requests_per_second = min(requests_per_second, 10)
        self.min_request_interval = 1.0 / self.requests_per_second
        self.last_request_time = 0

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.USER_AGENT,
            'Accept-Encoding': 'gzip, deflate',
            'Accept': 'application/json'
        })

        logger.info(f"✅ SEC EDGAR Fetcher initialized (rate limit: {self.requests_per_second}/sec)")

    def _rate_limit(self):
        """Ensure we don't exceed rate limit"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last_request
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def fetch_company_tickers(self) -> Dict[str, Dict[str, Any]]:
        """
        Fetch complete company ticker to CIK mapping

        Returns:
            Dictionary mapping ticker -> {cik, title, exchange}
        """
        self._rate_limit()

        try:
            logger.info("Fetching SEC company tickers...")
            response = self.session.get(self.COMPANY_TICKERS_URL)
            response.raise_for_status()

            data = response.json()

            # Transform: {0: {ticker: "AAPL", cik: "0000320193", ...}}
            # To: {"AAPL": {cik: "0000320193", ...}}
            ticker_map = {}
            for item in data.values():
                ticker = item['ticker'].upper()
                ticker_map[ticker] = {
                    'cik': item['cik_str'],
                    'title': item['title'],
                    'exchange': item.get('exchange', '')
                }

            logger.info(f"✅ Loaded {len(ticker_map)} ticker mappings")
            return ticker_map

        except Exception as e:
            logger.error(f"❌ Error fetching company tickers: {e}")
            return {}

    def fetch_company_submissions(self, cik: str) -> Optional[Dict[str, Any]]:
        """
        Fetch all filings for a company

        Args:
            cik: Company CIK (with or without leading zeros)

        Returns:
            Dictionary with company filings data
        """
        # Ensure CIK has leading zeros (10 digits)
        cik_padded = str(cik).zfill(10)

        self._rate_limit()

        url = f"{self.DATA_BASE_URL}/submissions/CIK{cik_padded}.json"

        try:
            logger.debug(f"Fetching submissions for CIK {cik_padded}")
            response = self.session.get(url)

            if response.status_code == 404:
                logger.warning(f"No submissions found for CIK {cik_padded}")
                return None

            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"❌ Error fetching submissions for {cik}: {e}")
            return None

    def get_form4_filings(self, cik: str, start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None,
                          count: int = 100) -> List[Dict[str, Any]]:
        """
        Get Form 4 filings for a company

        Args:
            cik: Company CIK
            start_date: Filter filings after this date
            end_date: Filter filings before this date
            count: Maximum number of filings to return

        Returns:
            List of Form 4 filing metadata
        """
        submissions = self.fetch_company_submissions(cik)

        if not submissions:
            return []

        # Get recent filings
        filings = submissions.get('filings', {}).get('recent', {})

        # Filter for Form 4 (insider trading)
        form4_indices = [
            i for i, form in enumerate(filings.get('form', []))
            if form == '4'
        ]

        # Filter by date range
        filtered_filings = []
        for idx in form4_indices:
            filing_date_str = filings['filingDate'][idx]

            if not filing_date_str:
                continue

            try:
                filing_date = datetime.fromisoformat(filing_date_str.replace('Z', '+00:00'))

                # Apply date filters
                if start_date and filing_date < start_date:
                    continue
                if end_date and filing_date > end_date:
                    continue

                # Build filing metadata
                filing_info = {
                    'accession_number': filings['accessionNumber'][idx],
                    'filing_date': filing_date_str,
                    'report_date': filings.get('reportDate', [])[idx] if idx < len(filings.get('reportDate', [])) else None,
                    'acceptance_time': filings.get('acceptanceDateTime', [])[idx] if idx < len(filings.get('acceptanceDateTime', [])) else None,
                    'act': filings.get('act', [])[idx] if idx < len(filings.get('act', [])) else None,
                    'form': '4',
                    'file_number': filings.get('fileNumber', [])[idx] if idx < len(filings.get('fileNumber', [])) else None,
                    'film_number': filings.get('filmNumber', [])[idx] if idx < len(filings.get('filmNumber', [])) else None,
                    'items': filings.get('items', [])[idx] if idx < len(filings.get('items', [])) else None,
                    'size': filings.get('size', [])[idx] if idx < len(filings.get('size', [])) else None,
                    'is_xbrl': filings.get('isXBRL', [])[idx] if idx < len(filings.get('isXBRL', [])) else None,
                    'is_inline_xbrl': filings.get('isInlineXBRL', [])[idx] if idx < len(filings.get('isInlineXBRL', [])) else None,
                    'primary_doc': filings.get('primaryDocument', [])[idx] if idx < len(filings.get('primaryDocument', [])) else None,
                    'primary_doc_description': filings.get('primaryDocDescription', [])[idx] if idx < len(filings.get('primaryDocDescription', [])) else None,
                }

                filtered_filings.append(filing_info)

                # Limit results
                if len(filtered_filings) >= count:
                    break

            except Exception as e:
                logger.debug(f"Error parsing filing date {filing_date_str}: {e}")
                continue

        logger.info(f"Found {len(filtered_filings)} Form 4 filings for CIK {cik}")
        return filtered_filings

    def fetch_form4_content(self, cik: str, accession_number: str,
                           primary_doc: str) -> Optional[Dict[str, Any]]:
        """
        Fetch and parse Form 4 filing content

        Args:
            cik: Company CIK
            accession_number: Filing accession number
            primary_doc: Primary document filename (not used, we use .txt instead)

        Returns:
            Parsed Form 4 data with insider transactions
        """
        # Build URL: https://www.sec.gov/Archives/edgar/data/320193/0001462356-25-000012/0001462356-25-000012.txt
        # The .txt file contains the raw SGML/XML data (not the HTML display version)
        cik_clean = str(cik).lstrip('0')
        accession_clean = accession_number.replace('-', '')

        url = f"{self.BASE_URL}/Archives/edgar/data/{cik_clean}/{accession_clean}/{accession_number}.txt"

        self._rate_limit()

        try:
            logger.debug(f"Fetching Form 4 content: {url}")
            response = self.session.get(url)
            response.raise_for_status()

            # Parse Form 4 (SGML/XML format)
            content = response.text

            # Check if it contains XML/SGML data
            if '<?xml' not in content and '<ownershipDocument>' not in content and '<SEC-HEADER>' not in content:
                logger.warning(f"Unexpected content format for {accession_number}")
                return None

            return self._parse_form4_sgml(content, accession_number)

        except Exception as e:
            logger.error(f"❌ Error fetching Form 4 content {accession_number}: {e}")
            return None

    def _parse_form4_xml(self, xml_content: str, accession_number: str) -> Dict[str, Any]:
        """
        Parse Form 4 XML content

        Args:
            xml_content: XML content from SEC
            accession_number: Filing accession number

        Returns:
            Parsed Form 4 data
        """
        try:
            # Remove namespace if present
            xml_content = re.sub(r'xmlns[^"]*"[^"]*"', '', xml_content)

            root = ET.fromstring(xml_content)

            data = {
                'accession_number': accession_number,
                'period_of_report': None,
                'insiders': []
            }

            # Extract period of report
            period_elem = root.find('.//periodOfReport')
            if period_elem is not None and period_elem.text:
                data['period_of_report'] = period_elem.text

            # Extract issuer info
            issuer = {}
            issuer_cik = root.find('.//issuerCik')
            issuer_ticker = root.find('.//issuerTicker')
            issuer_name = root.find('.//issuerName')

            if issuer_cik is not None:
                issuer['cik'] = issuer_cik.text
            if issuer_ticker is not None:
                issuer['ticker'] = issuer_ticker.text
            if issuer_name is not None:
                issuer['name'] = issuer_name.text

            data['issuer'] = issuer

            # Extract reporting owner info
            reporting_owner = {}
            owner_cik = root.find('.//reportingOwnerCik')
            owner_name = root.find('.//reportingOwnerName')
            owner_title = root.find('.//reportingOwnerTitle')

            if owner_cik is not None:
                reporting_owner['cik'] = owner_cik.text
            if owner_name is not None:
                reporting_owner['name'] = owner_name.text
            if owner_title is not None:
                reporting_owner['title'] = owner_title.text

            data['reporting_owner'] = reporting_owner

            # Extract non-derivative transactions (these are the actual stock trades)
            transactions = []

            for txn_elem in root.findall('.//nonDerivativeTransaction'):
                txn = self._parse_transaction(txn_elem)
                if txn:
                    transactions.append(txn)

            data['transactions'] = transactions

            return data

        except Exception as e:
            logger.error(f"❌ Error parsing Form 4 XML: {e}")
            return None

    def _parse_form4_sgml(self, sgml_content: str, accession_number: str) -> Dict[str, Any]:
        """
        Parse Form 4 SGML content (SEC's older format)

        Args:
            sgml_content: SGML content from SEC .txt file
            accession_number: Filing accession number

        Returns:
            Parsed Form 4 data
        """
        try:
            data = {
                'accession_number': accession_number,
                'period_of_report': None,
                'insiders': []
            }

            # Extract period of report
            period_match = re.search(r'CONFORMED PERIOD OF REPORT:\s+(\d{8})', sgml_content)
            if period_match:
                period_str = period_match.group(1)
                try:
                    data['period_of_report'] = f"{period_str[:4]}-{period_str[4:6]}-{period_str[6:8]}"
                except:
                    pass

            # Extract reporting owner info
            owner_name_match = re.search(r'COMPANY CONFORMED NAME:\s+([^\r\n]+)', sgml_content)
            owner_name = owner_name_match.group(1).strip() if owner_name_match else ''

            owner_title_match = re.search(r'TITLE:\s+([^\r\n]+)', sgml_content)
            owner_title = owner_title_match.group(1).strip() if owner_title_match else ''

            data['reporting_owner'] = {
                'name': owner_name,
                'title': owner_title
            }

            # Extract non-derivative transactions
            transactions = []

            # Find all non-derivative transaction tables
            # Pattern: RPTP - NONDERIVATIVE TRANSACTIONS
            # Each transaction has: Date, Type, Amount, Price, etc.

            # Look for transaction data using regex patterns
            # Format 1: Table-based SGML
            # <NONDERIVATIVE TABLE>
            #   <TR>
            #     <TD>Transaction Date<TD>2025-11-12
            # ...

            # Format 2: Line-based format
            # Transaction Date: 2025-11-12
            # Amount of Shares: 1000

            # Try to find transaction dates and amounts
            # Pattern: YYYY-MM-DD followed by transaction codes (P=Purchase, S=Sale)

            # Find all occurrences of transaction dates
            date_pattern = r'(\d{4}-\d{2}-\d{2})'

            # Look for transaction sections
            # Search for patterns like: "P" or "Purchase" or "S" or "Sale" near dates

            # Split into sections by transaction
            # Each transaction section typically starts with a date

            # More robust approach: Find the DERIVATIVE TABLE section and parse it
            nonderiv_match = re.search(r'<NONDERIVATIVE TABLE>(.*?)</NONDERIVATIVE TABLE>', sgml_content, re.DOTALL)

            if nonderiv_match:
                table_content = nonderiv_match.group(1)
                # Parse the table rows
                # Each row might be <TR>...</TR> or plain text

                # Look for transaction patterns
                # Common format: Date | Type | Shares | Price | Total

                # Try to extract transactions using multiple regex patterns
                # Pattern 1: Date followed by transaction code and amounts

                # Find all potential transactions
                # Look for lines with transaction codes (P, S, A, etc.)

                lines = table_content.split('\n')
                current_txn = {}

                for line in lines:
                    # Look for transaction date
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', line)
                    if date_match:
                        if current_txn:
                            transactions.append(current_txn)
                        current_txn = {'transaction_date': date_match.group(1)}

                    # Look for transaction codes
                    if re.search(r'\b(Purchase|P|buy|Buy)\b', line):
                        current_txn['transaction_type_code'] = 'P'
                    elif re.search(r'\b(Sale|S|sell|Sell)\b', line):
                        current_txn['transaction_type_code'] = 'S'

                    # Look for share amounts
                    shares_match = re.search(r'(\d+(?:,\d+)*)\s*shares?', line, re.IGNORECASE)
                    if shares_match:
                        shares_str = shares_match.group(1).replace(',', '')
                        current_txn['shares'] = float(shares_str)

                    # Look for price
                    price_match = re.search(r'\$?(\d+(?:\.\d+)*)', line)
                    if price_match:
                        current_txn['price_per_share'] = float(price_match.group(1))

                # Add last transaction
                if current_txn:
                    transactions.append(current_txn)

            # Fallback: Look for simple patterns
            if not transactions:
                # Try to find transactions using date + code pattern
                # Format: "2025-11-12 P 1000" or similar

                # Find all dates in the document
                all_dates = re.findall(r'(\d{4}-\d{2}-\d{2})', sgml_content)

                # Look for transaction codes nearby
                for date_str in set(all_dates):  # Dedupe
                    # Search for transaction codes near this date
                    date_context = self._find_context(sgml_content, date_str, context_chars=200)

                    if 'P' in date_context or 'Purchase' in date_context:
                        transactions.append({
                            'transaction_date': date_str,
                            'transaction_type_code': 'P',
                            'shares': 0,  # Not found
                            'price_per_share': 0
                        })
                    elif 'S' in date_context or 'Sale' in date_context:
                        transactions.append({
                            'transaction_date': date_str,
                            'transaction_type_code': 'S',
                            'shares': 0,
                            'price_per_share': 0
                        })

            logger.debug(f"Extracted {len(transactions)} transactions from SGML")
            data['transactions'] = transactions

            return data

        except Exception as e:
            logger.error(f"❌ Error parsing Form 4 SGML: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _find_context(self, content: str, target: str, context_chars: int = 200) -> str:
        """Find context around a target string in content"""
        idx = content.find(target)
        if idx == -1:
            return ''

        start = max(0, idx - context_chars)
        end = min(len(content), idx + len(target) + context_chars)

        return content[start:end]

    def _parse_transaction(self, txn_elem: ET.Element) -> Optional[Dict[str, Any]]:
        """
        Parse a single transaction from Form 4

        Args:
            txn_elem: XML element for transaction

        Returns:
            Transaction dictionary
        """
        try:
            txn = {}

            # Transaction coding
            coding = txn_elem.find('.//transactionCoding')
            if coding is not None:
                txn_type = coding.find('transactionType')
                if txn_type is not None:
                    txn['transaction_type'] = txn_type.text

                # Transaction type codes:
                # P - Purchase (Open market or private)
                # S - Sale (Open market or private)
                # A - Grant (Award)
                # D - Sale (exempt)
                # F - Payment (In lieu of sale)
                # etc.

            # Transaction amounts
            amounts = txn_elem.find('.//transactionAmounts')
            if amounts is not None:
                shares = amounts.find('transactionShares')
                if shares is not None and shares.find('value') is not None:
                    txn['shares'] = float(shares.find('value').text)

                price = amounts.find('transactionPricePerShare')
                if price is not None and price.find('value') is not None:
                    txn['price_per_share'] = float(price.find('value').text)

                total = amounts.find('transactionTotalValue')
                if total is not None and total.find('value') is not None:
                    txn['total_value'] = float(total.find('value').text)

                acquired_disposed = amounts.find('transactionAcquiredDisposedCode')
                if acquired_disposed is not None and acquired_disposed.find('value') is not None:
                    code = acquired_disposed.find('value').text
                    txn['acquired_disposed'] = code  # A=Acquired, D=Disposed

            # Transaction date
            date_elem = txn_elem.find('.//transactionDate')
            if date_elem is not None:
                value = date_elem.find('value')
                if value is not None:
                    txn['transaction_date'] = value.text

            # Ownership type (direct or indirect)
            ownership = txn_elem.find('.//ownershipNature')
            if ownership is not None:
                direct_indirect = ownership.find('directOrIndirectOwnership')
                if direct_indirect is not None and direct_indirect.find('value') is not None:
                    txn['ownership_type'] = direct_indirect.find('value').text

            return txn if txn else None

        except Exception as e:
            logger.debug(f"Error parsing transaction: {e}")
            return None

    def search_filings(self, ticker: str, filing_type: str = '4',
                       start_date: Optional[datetime] = None,
                       end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Search for filings using SEC search API

        Args:
            ticker: Stock ticker symbol
            filing_type: Filing type (default: '4' for Form 4)
            start_date: Start date for search
            end_date: End date for search

        Returns:
            List of filing metadata
        """
        self._rate_limit()

        # Build search query
        query = f'"{ticker}" AND "{filing_type}"'

        params = {
            'q': query,
            'dateRange': 'custom',
            'category': 'form-cat2',
            'startdt': start_date.strftime('%Y-%m-%d') if start_date else '2020-01-01',
            'enddt': end_date.strftime('%Y-%m-%d') if end_date else datetime.now().strftime('%Y-%m-%d'),
            'entityName': ticker
        }

        try:
            response = self.session.get(self.SEARCH_API_URL, params=params)
            response.raise_for_status()

            data = response.json()

            # Extract hits from search results
            hits = data.get('hits', {}).get('hit', [])

            filings = []
            for hit in hits:
                # Parse search result
                filings.append({
                    'accession_number': hit.get('accession_no'),
                    'filing_date': hit.get('file_date'),
                    'form': hit.get('form'),
                    'cik': hit.get('cik'),
                    'ticker': ticker
                })

            logger.info(f"Found {len(filings)} {filing_type} filings for {ticker}")
            return filings

        except Exception as e:
            logger.error(f"❌ Error searching filings: {e}")
            return []


def main():
    """Test SEC EDGAR fetcher"""
    logging.basicConfig(level=logging.INFO)

    fetcher = SECEdgarFetcher()

    # Test 1: Fetch company tickers
    print("\n" + "=" * 80)
    print("TEST 1: Fetch Company Tickers")
    print("=" * 80)
    tickers = fetcher.fetch_company_tickers()
    print(f"\nTotal tickers: {len(tickers)}")
    print(f"Sample AAPL: {tickers.get('AAPL')}")

    # Test 2: Get Apple CIK
    apple_cik = tickers.get('AAPL', {}).get('cik', '0000320193')

    # Test 3: Get Form 4 filings for Apple
    print("\n" + "=" * 80)
    print("TEST 2: Get Form 4 Filings for Apple")
    print("=" * 80)
    filings = fetcher.get_form4_filings(
        apple_cik,
        start_date=datetime.now() - timedelta(days=30),
        count=5
    )

    print(f"\nFound {len(filings)} Form 4 filings")
    if filings:
        print(f"\nMost recent filing:")
        print(f"  Accession: {filings[0]['accession_number']}")
        print(f"  Date: {filings[0]['filing_date']}")
        print(f"  Primary Doc: {filings[0]['primary_doc']}")

        # Test 4: Fetch full Form 4 content
        if filings[0].get('primary_doc'):
            print("\n" + "=" * 80)
            print("TEST 3: Fetch Form 4 Content")
            print("=" * 80)
            content = fetcher.fetch_form4_content(
                apple_cik,
                filings[0]['accession_number'],
                filings[0]['primary_doc']
            )

            if content:
                print(f"\nPeriod of Report: {content.get('period_of_report')}")
                print(f"Reporting Owner: {content.get('reporting_owner', {}).get('name')}")
                print(f"Owner Title: {content.get('reporting_owner', {}).get('title')}")
                print(f"Number of Transactions: {len(content.get('transactions', []))}")

                if content.get('transactions'):
                    print(f"\nFirst Transaction:")
                    txn = content['transactions'][0]
                    print(f"  Type: {txn.get('transaction_type')}")
                    print(f"  Shares: {txn.get('shares')}")
                    print(f"  Price: ${txn.get('price_per_share', 0):.2f}")
                    print(f"  Total: ${txn.get('total_value', 0):,.2f}")
                    print(f"  Date: {txn.get('transaction_date')}")
                    print(f"  Acquired/Disposed: {txn.get('acquired_disposed')}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
