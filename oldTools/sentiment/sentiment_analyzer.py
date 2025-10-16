"""
sentiment_analyzer.py

Purpose:
    - Provides sentiment analysis of recent news headlines for selected tickers.
    - Uses FinBERT transformer to assign sentiment (positive, negative, neutral) with probabilities.
    - Fetches news via Finnhub and your NewsScraper.

Typical usage:
    analyzer = SentimentAnalyzer([symbol])
    sentiment_df = analyzer.get_current_sentiment()
    stats = analyzer.get_stats()
"""

import pandas as pd
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from typing import Tuple
from tools.sentiment.news_scraper import NewsScraper
import finnhub

class SentimentAnalyzer:
    def __init__(self, ticker_list, polygon_api_key):
        # Detect device for transformer inference
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
        self.model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert").to(self.device)
        self.labels = ["positive", "negative", "neutral"]
        self.news = None
        self.cumulative_df = None  
        self.num_runs = 0

        # News API and scraping setup
        self.ticker_list = ticker_list
        self.polygon_api_key = polygon_api_key
        self.news_scraper = NewsScraper(self.polygon_api_key, self.ticker_list, limit_per_ticker=50)

    def get_current_sentiment(self):
        self.news = self.news_scraper.get_news()
        return self.clean_analysis()

    def estimate_sentiment(self, news):
        if news:
            tokens = self.tokenizer(news, return_tensors="pt", padding=True).to(self.device)
            result = self.model(tokens["input_ids"], attention_mask=tokens["attention_mask"])["logits"]
            result = torch.nn.functional.softmax(torch.sum(result, 0), dim=-1)
            probability = result[torch.argmax(result)].detach().cpu().numpy()
            sentiment = self.labels[torch.argmax(result)]
            return probability, sentiment
        else:
            return 0, self.labels[-1]
        
    def sentiment_analysis(self) -> pd.DataFrame:
        result = self.news['Headline'].apply(lambda text: self.estimate_sentiment(text))
        # self.news[['SCORE_PROB','SCORE_SENT']] = self.news.apply(
        #     lambda x: self.estimate_sentiment(x['Headline']), axis=1, result_type='expand'
        # )
        self.news['SCORE_PROB'] = result.apply(lambda x: x[0])
        self.news['SCORE_SENT'] = result.apply(lambda x: x[1])
        return self.news

    def clean_analysis(self, treshold: float = 0.9) -> pd.DataFrame:
        self.sentiment_analysis()
        return self.news[(self.news.SCORE_PROB >= treshold) & (self.news.SCORE_SENT != "neutral")]

    def get_stats(self, treshold: float = 0.9) -> pd.DataFrame:
        self.summary_df = self.news.groupby('Ticker')['SCORE_SENT'].value_counts().unstack(fill_value=0)

        # Ensure all columns exist!
        for col in ['positive', 'negative', 'neutral']:
            if col not in self.summary_df.columns:
                self.summary_df[col] = 0

        self.summary_df = self.summary_df.rename(columns={
            'positive': 'Positive_C', 'negative': 'Negative_C', 'neutral': 'Neutral_C'
        })

        # Calculate total sentiment mentions (volume)
        self.summary_df['Volume'] = self.summary_df[['Positive_C', 'Negative_C', 'Neutral_C']].sum(axis=1)

        # Calculate sentiment percentages
        self.summary_df['Negative_P'] = round((self.summary_df['Negative_C'] / self.summary_df['Volume']) * 100, 1)
        self.summary_df['Neutral_P'] = round((self.summary_df['Neutral_C'] / self.summary_df['Volume']) * 100, 1)
        self.summary_df['Positive_P'] = round((self.summary_df['Positive_C'] / self.summary_df['Volume']) * 100, 1)

        # Calculate Sentiment Index from -100 to 100
        self.summary_df['Sent_Index'] = ((self.summary_df['Positive_C'] - self.summary_df['Negative_C']) /  self.summary_df['Volume']) * 100
        self.summary_df = self.summary_df.reset_index()

        if self.cumulative_df is None:
            self.cumulative_df = self.summary_df.copy()
            self.summary_df['Trend'] = "Neutral"
        else:
            self.num_runs += 1
            self.summary_df['Trend'] = self.summary_df.apply(lambda row: 
                "Rise" if row['Sent_Index'] > self.cumulative_df.loc[self.cumulative_df["Ticker"] == row["Ticker"], 'Sent_Index'].values[0] else  
                "Fall" if row['Sent_Index'] < self.cumulative_df.loc[self.cumulative_df["Ticker"] == row["Ticker"], 'Sent_Index'].values[0] else  
                "Neutral", axis=1)
            for col in ['Positive_C', 'Negative_C', 'Neutral_C', 
                        'Volume', 'Positive_P', 'Negative_P', 'Neutral_P', 'Sent_Index']:
                self.cumulative_df[col] = (self.cumulative_df[col] * self.num_runs + self.summary_df[col]) / (self.num_runs + 1)
        return self.summary_df

if __name__ == "__main__":
    # Replace with your real API key
    POLYGON_API_KEY = "slkk84FyTZ20BA1tBZFFCEnnCB6wcv_W"
    tickers = ["VST","TSLA"]

    analyzer = SentimentAnalyzer(ticker_list=tickers, polygon_api_key=POLYGON_API_KEY)
    df = analyzer.get_current_sentiment()
    print("\nHeadlines with sentiment:\n", df[['Ticker', 'Headline', 'SCORE_PROB', 'SCORE_SENT']].head(10))
    stats = analyzer.get_stats()
    print("\nSentiment stats:\n", stats.head(10))