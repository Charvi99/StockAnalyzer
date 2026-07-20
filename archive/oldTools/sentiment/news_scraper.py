"""
polygon_news_scraper.py

Fetches news for given tickers using Polygon.io official Python SDK.
Returns clean DataFrame: Ticker, Datetime, Headline, Summary, Source, URL.
"""

from polygon import RESTClient
from polygon.rest.models import TickerNews
import pandas as pd

class NewsScraper:
    def __init__(self, api_key: str, tickers: list, limit_per_ticker: int = 20):
        """
        Args:
            api_key (str): Your Polygon.io API key.
            tickers (list): List of ticker symbols, e.g. ["AAPL", "NVDA"]
            limit_per_ticker (int): How many news per ticker to fetch.
        """
        self.api_key = api_key
        self.tickers = tickers
        self.limit_per_ticker = limit_per_ticker
        self.client = RESTClient(api_key)

    def get_news(self) -> pd.DataFrame:
        """
        Fetches news for all tickers, returns pd.DataFrame.
        """
        parsed_data = []
        for ticker in self.tickers:
            try:
                news_iter = self.client.list_ticker_news(
                    ticker=ticker,
                    order="desc",
                    limit=self.limit_per_ticker,
                    sort="published_utc"
                )
                count = 0
                for n in news_iter:
                    if isinstance(n, TickerNews):
                        headline = n.title or ""
                        description = n.description or ""
                        url = n.article_url or ""
                        source = n.publisher.name if n.publisher else ""
                        dt = n.published_utc

                        if not headline.strip():
                            continue  # Skip if no title

                        parsed_data.append([
                            ticker,
                            dt,
                            headline,
                            description,  # <--- This is the summary/description field
                            source,
                            url
                        ])
                        count += 1
                        if count >= self.limit_per_ticker:
                            break
            except Exception as e:
                print(f"[{ticker}] Error fetching news: {e}")
                continue

        df = pd.DataFrame(parsed_data, columns=['Ticker', 'Datetime', 'Headline', 'Summary', 'Source', 'URL'])
        return df

    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Optional: Lowercase, strip non-ascii chars from headline and summary.
        """
        import re
        df['Headline'] = df['Headline'].apply(lambda x: re.sub(r'[^\x00-\x7F]+', '', x).strip())
        df['Summary'] = df['Summary'].apply(lambda x: re.sub(r'[^\x00-\x7F]+', '', x).strip())
        return df

if __name__ == "__main__":
    # EXAMPLE USAGE
    POLYGON_API_KEY = "slkk84FyTZ20BA1tBZFFCEnnCB6wcv_W"
    tickers = ["NVDA", "AAPL"]
    scraper = NewsScraper(POLYGON_API_KEY, tickers, limit_per_ticker=20)
    df = scraper.get_news()
    print(df.to_string(index=False))

    clean_df = scraper.clean_data(df)
    print("\nFinal Polygon News DataFrame (first 10 rows):\n")
    print(clean_df.head(10).to_string(index=False))
