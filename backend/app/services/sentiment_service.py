"""
sentiment_service.py

Sentiment analysis service adapted from oldTools/sentiment
Provides news scraping and sentiment analysis using FinBERT and Polygon.io
"""

import pandas as pd
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from polygon import RESTClient
from polygon.rest.models import TickerNews
from typing import List, Dict, Tuple
import re
from datetime import datetime


class NewsScraper:
    """Fetch news articles from Polygon.io API"""

    def __init__(self, api_key: str, tickers: List[str], limit_per_ticker: int = 20):
        """
        Args:
            api_key: Polygon.io API key
            tickers: List of ticker symbols (e.g., ["AAPL", "NVDA"])
            limit_per_ticker: Number of news articles to fetch per ticker
        """
        self.api_key = api_key
        self.tickers = tickers
        self.limit_per_ticker = limit_per_ticker
        self.client = RESTClient(api_key)

    def get_news(self) -> pd.DataFrame:
        """Fetch news for all tickers"""
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
                            continue

                        parsed_data.append([
                            ticker,
                            dt,
                            headline,
                            description,
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
        """Remove non-ASCII characters from headlines and summaries"""
        df['Headline'] = df['Headline'].apply(lambda x: re.sub(r'[^\x00-\x7F]+', '', x).strip())
        df['Summary'] = df['Summary'].apply(lambda x: re.sub(r'[^\x00-\x7F]+', '', x).strip())
        return df


class SentimentAnalyzer:
    """Analyze sentiment of news headlines using FinBERT"""

    def __init__(self, ticker_list: List[str], polygon_api_key: str, limit_per_ticker: int = 50):
        """
        Args:
            ticker_list: List of stock tickers to analyze
            polygon_api_key: Polygon.io API key
            limit_per_ticker: Number of news articles per ticker
        """
        # Detect device for transformer inference
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"

        # Load FinBERT model for financial sentiment analysis
        self.tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
        self.model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert").to(self.device)
        self.labels = ["positive", "negative", "neutral"]

        # News scraping setup
        self.ticker_list = ticker_list
        self.polygon_api_key = polygon_api_key
        self.news_scraper = NewsScraper(self.polygon_api_key, self.ticker_list, limit_per_ticker=limit_per_ticker)

        # Storage
        self.news = None
        self.cumulative_df = None
        self.num_runs = 0

    def get_current_sentiment(self, threshold: float = 0.9) -> pd.DataFrame:
        """Fetch news and analyze sentiment"""
        self.news = self.news_scraper.get_news()
        return self.clean_analysis(threshold)

    def estimate_sentiment(self, text: str) -> Tuple[float, str]:
        """Estimate sentiment for a single text"""
        if text:
            tokens = self.tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512).to(self.device)

            with torch.no_grad():
                result = self.model(tokens["input_ids"], attention_mask=tokens["attention_mask"])["logits"]

            result = torch.nn.functional.softmax(torch.sum(result, 0), dim=-1)
            probability = result[torch.argmax(result)].detach().cpu().numpy()
            sentiment = self.labels[torch.argmax(result)]

            return float(probability), sentiment
        else:
            return 0.0, self.labels[-1]

    def sentiment_analysis(self) -> pd.DataFrame:
        """Perform sentiment analysis on all news headlines"""
        result = self.news['Headline'].apply(lambda text: self.estimate_sentiment(text))
        self.news['SCORE_PROB'] = result.apply(lambda x: x[0])
        self.news['SCORE_SENT'] = result.apply(lambda x: x[1])
        return self.news

    def clean_analysis(self, threshold: float = 0.9) -> pd.DataFrame:
        """Return only high-confidence non-neutral sentiments"""
        self.sentiment_analysis()
        return self.news[(self.news.SCORE_PROB >= threshold) & (self.news.SCORE_SENT != "neutral")]

    def get_stats(self) -> pd.DataFrame:
        """Calculate sentiment statistics per ticker"""
        if self.news is None or 'SCORE_SENT' not in self.news.columns:
            return pd.DataFrame()

        summary_df = self.news.groupby('Ticker')['SCORE_SENT'].value_counts().unstack(fill_value=0)

        # Ensure all columns exist
        for col in ['positive', 'negative', 'neutral']:
            if col not in summary_df.columns:
                summary_df[col] = 0

        summary_df = summary_df.rename(columns={
            'positive': 'Positive_C',
            'negative': 'Negative_C',
            'neutral': 'Neutral_C'
        })

        # Calculate total sentiment mentions
        summary_df['Volume'] = summary_df[['Positive_C', 'Negative_C', 'Neutral_C']].sum(axis=1)

        # Calculate sentiment percentages
        summary_df['Negative_P'] = round((summary_df['Negative_C'] / summary_df['Volume']) * 100, 1)
        summary_df['Neutral_P'] = round((summary_df['Neutral_C'] / summary_df['Volume']) * 100, 1)
        summary_df['Positive_P'] = round((summary_df['Positive_C'] / summary_df['Volume']) * 100, 1)

        # Calculate Sentiment Index from -100 to 100
        summary_df['Sent_Index'] = ((summary_df['Positive_C'] - summary_df['Negative_C']) / summary_df['Volume']) * 100

        summary_df = summary_df.reset_index()

        # Track trend over multiple runs
        if self.cumulative_df is None:
            self.cumulative_df = summary_df.copy()
            summary_df['Trend'] = "Neutral"
        else:
            self.num_runs += 1
            summary_df['Trend'] = summary_df.apply(
                lambda row: (
                    "Rise" if row['Sent_Index'] > self.cumulative_df.loc[
                        self.cumulative_df["Ticker"] == row["Ticker"], 'Sent_Index'
                    ].values[0] else
                    "Fall" if row['Sent_Index'] < self.cumulative_df.loc[
                        self.cumulative_df["Ticker"] == row["Ticker"], 'Sent_Index'
                    ].values[0] else
                    "Neutral"
                ),
                axis=1
            )

            # Update cumulative averages
            for col in ['Positive_C', 'Negative_C', 'Neutral_C', 'Volume',
                       'Positive_P', 'Negative_P', 'Neutral_P', 'Sent_Index']:
                self.cumulative_df[col] = (
                    self.cumulative_df[col] * self.num_runs + summary_df[col]
                ) / (self.num_runs + 1)

        self.summary_df = summary_df
        return summary_df


class SentimentService:
    """High-level service for sentiment analysis operations"""

    def __init__(self, polygon_api_key: str):
        self.polygon_api_key = polygon_api_key
        self.analyzers = {}

    def analyze_sentiment(self, ticker: str, limit_per_ticker: int = 50, threshold: float = 0.9) -> Dict:
        """
        Analyze sentiment for a single ticker

        Args:
            ticker: Stock ticker symbol
            limit_per_ticker: Number of news articles to fetch
            threshold: Confidence threshold for sentiment

        Returns:
            Dictionary with sentiment analysis results
        """
        analyzer = SentimentAnalyzer([ticker], self.polygon_api_key, limit_per_ticker)

        # Get sentiment data
        sentiment_df = analyzer.get_current_sentiment(threshold)
        stats = analyzer.get_stats()

        if stats.empty:
            return {
                'ticker': ticker,
                'sentiment_index': 0.0,
                'positive_count': 0,
                'negative_count': 0,
                'neutral_count': 0,
                'positive_pct': 0.0,
                'negative_pct': 0.0,
                'neutral_pct': 0.0,
                'total_articles': 0,
                'trend': 'Neutral',
                'news': []
            }

        ticker_stats = stats[stats['Ticker'] == ticker].iloc[0]

        news_list = []
        if not sentiment_df.empty:
            news_list = sentiment_df.to_dict('records')

        return {
            'ticker': ticker,
            'sentiment_index': float(ticker_stats['Sent_Index']),
            'positive_count': int(ticker_stats['Positive_C']),
            'negative_count': int(ticker_stats['Negative_C']),
            'neutral_count': int(ticker_stats['Neutral_C']),
            'positive_pct': float(ticker_stats['Positive_P']),
            'negative_pct': float(ticker_stats['Negative_P']),
            'neutral_pct': float(ticker_stats['Neutral_P']),
            'total_articles': int(ticker_stats['Volume']),
            'trend': ticker_stats['Trend'],
            'news': news_list
        }

    def analyze_multiple_tickers(self, tickers: List[str], limit_per_ticker: int = 50, threshold: float = 0.9) -> Dict:
        """
        Analyze sentiment for multiple tickers

        Args:
            tickers: List of stock ticker symbols
            limit_per_ticker: Number of news articles to fetch per ticker
            threshold: Confidence threshold for sentiment

        Returns:
            Dictionary with sentiment analysis results for all tickers
        """
        analyzer = SentimentAnalyzer(tickers, self.polygon_api_key, limit_per_ticker)

        # Get sentiment data
        sentiment_df = analyzer.get_current_sentiment(threshold)
        stats = analyzer.get_stats()

        results = []
        for ticker in tickers:
            ticker_stats = stats[stats['Ticker'] == ticker]

            if ticker_stats.empty:
                results.append({
                    'ticker': ticker,
                    'sentiment_index': 0.0,
                    'positive_count': 0,
                    'negative_count': 0,
                    'neutral_count': 0,
                    'positive_pct': 0.0,
                    'negative_pct': 0.0,
                    'neutral_pct': 0.0,
                    'total_articles': 0,
                    'trend': 'Neutral'
                })
            else:
                ticker_row = ticker_stats.iloc[0]
                results.append({
                    'ticker': ticker,
                    'sentiment_index': float(ticker_row['Sent_Index']),
                    'positive_count': int(ticker_row['Positive_C']),
                    'negative_count': int(ticker_row['Negative_C']),
                    'neutral_count': int(ticker_row['Neutral_C']),
                    'positive_pct': float(ticker_row['Positive_P']),
                    'negative_pct': float(ticker_row['Negative_P']),
                    'neutral_pct': float(ticker_row['Neutral_P']),
                    'total_articles': int(ticker_row['Volume']),
                    'trend': ticker_row['Trend']
                })

        # Get high-confidence news articles
        news_list = []
        if not sentiment_df.empty:
            news_list = sentiment_df.to_dict('records')

        return {
            'tickers': results,
            'news': news_list,
            'total_articles_analyzed': len(analyzer.news) if analyzer.news is not None else 0
        }
