#!/usr/bin/env python3
"""
Generate News Sentiment using FinBERT

This script uses FinBERT (ProsusAI/finbert) - a BERT model fine-tuned on
financial text for sentiment analysis. It processes all news articles
in the database and generates high-quality sentiment scores.

Why FinBERT?
- Trained on 10K+ financial sentences from analyst reports
- Understands financial terminology (e.g., "beat" = positive, "miss" = negative)
- Outputs: Positive, Negative, or Neutral with confidence scores
- ~75-80% accuracy on financial text

Expected Results:
- All 285K articles will have meaningful sentiment scores
- Replace Polygon's limited sentiment (only 15 non-zero articles)
- Expected +2-4% improvement in ML model AUC

Usage:
    docker exec stock_analyzer_ml_training python scripts/generate_news_sentiment.py

Expected runtime: 2-4 hours for 285K articles (GPU-accelerated)
"""

import sys
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple
import time

sys.path.insert(0, '/backend')
sys.path.insert(0, '/app/ml_training')

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm
import torch
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification

# Database connection
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://stockuser:stockpass123@database:5432/stock_analyzer'
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Model settings
MODEL_NAME = "ProsusAI/finbert"  # Financial BERT model
BATCH_SIZE = 32  # Process 32 articles at once
MAX_LENGTH = 512  # Max tokens per article

# Device detection
DEVICE = 0 if torch.cuda.is_available() else -1  # 0 = GPU, -1 = CPU
logger.info(f"Using device: {'GPU (CUDA)' if DEVICE == 0 else 'CPU'}")


# ============================================================================
# FINBERT SENTIMENT ANALYZER
# ============================================================================

class FinBertSentimentAnalyzer:
    """Financial sentiment analysis using FinBERT"""

    def __init__(self, model_name: str = MODEL_NAME, device: int = DEVICE):
        self.device = device
        logger.info(f"Loading FinBERT model: {model_name}")

        # Load model and tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)

        if device == 0:
            self.model = self.model.to('cuda')
            logger.info("Model loaded on GPU")

        # Label mapping for FinBERT
        self.label_map = {
            0: 'negative',
            1: 'neutral',
            2: 'positive'
        }

        # Score mapping (consistent with Polygon: -0.7, 0.0, +0.7)
        self.score_map = {
            'negative': -0.7,
            'neutral': 0.0,
            'positive': 0.7
        }

    def analyze_text(self, text: str) -> Tuple[str, float, float]:
        """
        Analyze sentiment of a single text

        Args:
            text: Article title + description

        Returns:
            Tuple of (sentiment, sentiment_score, confidence)
        """
        if not text or len(text.strip()) < 10:
            return 'neutral', 0.0, 0.0

        try:
            # Tokenize
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=MAX_LENGTH,
                padding=True
            )

            if self.device == 0:
                inputs = {k: v.to('cuda') for k, v in inputs.items()}

            # Predict
            with torch.no_grad():
                outputs = self.model(**inputs)
                predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
                predicted_label = torch.argmax(predictions, dim=-1).item()
                confidence = predictions[0][predicted_label].item()

            sentiment = self.label_map[predicted_label]
            score = self.score_map[sentiment]

            return sentiment, score, confidence

        except Exception as e:
            logger.debug(f"Error analyzing text: {e}")
            return 'neutral', 0.0, 0.0

    def analyze_batch(self, texts: List[str]) -> List[Tuple[str, float, float]]:
        """
        Analyze sentiment for a batch of texts

        Args:
            texts: List of article texts

        Returns:
            List of (sentiment, sentiment_score, confidence) tuples
        """
        results = []

        for text in texts:
            sentiment, score, conf = self.analyze_text(text)
            results.append((sentiment, score, conf))

        return results


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

def fetch_articles_without_finbert_sentiment(limit: int = None) -> pd.DataFrame:
    """
    Fetch articles that need FinBERT sentiment analysis

    Returns articles where:
    - sentiment_reasoning is NULL (no Polygon sentiment), OR
    - sentiment_score = 0 (Polygon neutral)
    """
    query = text("""
        SELECT
            id,
            stock_id,
            title,
            description,
            publisher,
            published_utc,
            sentiment as polygon_sentiment,
            sentiment_score as polygon_score
        FROM news
        WHERE published_utc >= '2020-01-01'
          AND (
              sentiment_reasoning IS NULL
              OR sentiment_score = 0
          )
        ORDER BY published_utc DESC
    """)

    if limit:
        query = text(f"{query} LIMIT {limit}")

    with engine.connect() as conn:
        df = pd.read_sql(query, conn)

    return df


def update_sentiment_scores(article_updates: List[Dict]) -> int:
    """
    Update sentiment scores in database

    Args:
        article_updates: List of dicts with id, sentiment, sentiment_score

    Returns:
        Number of rows updated
    """
    if not article_updates:
        return 0

    db = SessionLocal()
    updated = 0

    try:
        for update in article_updates:
            db.execute(
                text("""
                    UPDATE news
                    SET
                        sentiment = :sentiment,
                        sentiment_score = :sentiment_score,
                        sentiment_reasoning = :sentiment_reasoning
                    WHERE id = :id
                """),
                {
                    'id': update['id'],
                    'sentiment': update['sentiment'],
                    'sentiment_score': update['sentiment_score'],
                    'sentiment_reasoning': f"FinBERT: {update['confidence']:.2f} confidence"
                }
            )
            updated += 1

        db.commit()

    except Exception as e:
        logger.error(f"Database error: {e}")
        db.rollback()
    finally:
        db.close()

    return updated


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main sentiment generation function"""
    print("=" * 80)
    print(" " * 20)
    print("FinBERT Financial Sentiment Analysis")
    print(" " * 20)
    print("=" * 80)

    # Check GPU
    if torch.cuda.is_available():
        print(f"\n✅ GPU detected: {torch.cuda.get_device_name(0)}")
        print(f"   Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    else:
        print(f"\n⚠️  No GPU detected - using CPU (slower)")

    # Initialize analyzer
    print(f"\n🤖 Loading FinBERT model...")
    analyzer = FinBertSentimentAnalyzer()

    # Fetch articles needing analysis
    print(f"\n📊 Fetching articles needing sentiment analysis...")
    articles_df = fetch_articles_without_finbert_sentiment()

    print(f"   Articles to process: {len(articles_df):,}")

    if len(articles_df) == 0:
        print("\n✅ All articles already have FinBERT sentiment!")
        return

    # Prepare texts (title + description)
    print(f"\n🔍 Preparing article texts...")
    articles_df['text'] = (
        articles_df['title'].fillna('') + ' ' +
        articles_df['description'].fillna('')
    ).str.strip()

    # Process in batches
    print(f"\n🚀 Processing articles (batch size = {BATCH_SIZE})...")
    print("=" * 80)

    total_processed = 0
    total_positive = 0
    total_negative = 0
    total_neutral = 0
    start_time = time.time()

    for start_idx in tqdm(range(0, len(articles_df), BATCH_SIZE), desc="Analyzing"):
        end_idx = min(start_idx + BATCH_SIZE, len(articles_df))
        batch_df = articles_df.iloc[start_idx:end_idx]

        # Analyze batch
        results = analyzer.analyze_batch(batch_df['text'].tolist())

        # Prepare updates
        updates = []
        for (_, article), (sentiment, score, confidence) in zip(batch_df.iterrows(), results):
            updates.append({
                'id': article['id'],
                'sentiment': sentiment,
                'sentiment_score': score,
                'confidence': confidence
            })

            # Track statistics
            if sentiment == 'positive':
                total_positive += 1
            elif sentiment == 'negative':
                total_negative += 1
            else:
                total_neutral += 1

        # Update database
        updated = update_sentiment_scores(updates)
        total_processed += updated

        # Progress update every 10 batches
        if (start_idx // BATCH_SIZE) % 10 == 0:
            elapsed = time.time() - start_time
            rate = total_processed / (elapsed / 60)  # articles per minute
            remaining = (len(articles_df) - total_processed) / rate if rate > 0 else 0

            tqdm.write(
                f"  Progress: {total_processed:,}/{len(articles_df):,} "
                f"({total_processed/len(articles_df)*100:.1f}%) | "
                f"Rate: {rate:.0f}/min | "
                f"ETA: {remaining:.0f}min"
            )

    # Calculate duration
    duration = time.time() - start_time

    # Print summary
    print("\n" + "=" * 80)
    print("✅ FINBERT SENTIMENT ANALYSIS COMPLETE!")
    print("=" * 80)
    print(f"\n📊 Results:")
    print(f"   Total articles processed: {total_processed:,}")
    print(f"   Duration: {duration/60:.1f} minutes")
    print(f"   Average speed: {total_processed/(duration/60):.0f} articles/minute")

    print(f"\n📈 Sentiment Distribution:")
    total = total_positive + total_negative + total_neutral
    print(f"   Positive: {total_positive:,} ({total_positive/total*100:.1f}%)")
    print(f"   Negative: {total_negative:,} ({total_negative/total*100:.1f}%)")
    print(f"   Neutral:  {total_neutral:,} ({total_neutral/total*100:.1f}%)")

    # Verify database
    print(f"\n🔍 Verifying database update...")
    db = SessionLocal()
    try:
        result = db.execute(
            text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN sentiment_score != 0 THEN 1 END) as non_zero,
                    AVG(sentiment_score) as avg_score,
                    MIN(sentiment_score) as min_score,
                    MAX(sentiment_score) as max_score
                FROM news
                WHERE published_utc >= '2020-01-01'
            """)
        ).fetchone()

        print(f"   Total articles: {result[0]:,}")
        print(f"   Non-zero sentiment: {result[1]:,} ({result[1]/result[0]*100:.1f}%)")
        print(f"   Avg score: {result[3]:.4f} to {result[4]:.4f}")

    finally:
        db.close()

    print("\n💡 Next steps:")
    print(f"   1. Re-run feature engineering to use new sentiment:")
    print(f"      docker exec stock_analyzer_ml_training python scripts/feature_engineering.py")
    print(f"   2. Train ML model with improved news features:")
    print(f"      docker exec stock_analyzer_ml_training python train.py")
    print(f"   3. Expected AUC improvement: +2-4%")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
