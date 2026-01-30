"""
News model for storing stock news articles and sentiment analysis
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, TIMESTAMP, DECIMAL, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base


class News(Base):
    """News articles related to stocks"""
    __tablename__ = "news"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey('stocks.id', ondelete='CASCADE'), nullable=False, index=True)

    # Article metadata from Polygon
    article_id = Column(String(255), unique=True, nullable=False, index=True)
    publisher = Column(String(255), nullable=True)
    title = Column(Text, nullable=False)
    author = Column(String(255), nullable=True)
    published_utc = Column(TIMESTAMP, nullable=False, index=True)
    article_url = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    keywords = Column(ARRAY(String), nullable=True)

    # Sentiment analysis from Polygon API insights
    sentiment = Column(String(20), nullable=True)  # 'positive', 'negative', 'neutral'
    sentiment_score = Column(DECIMAL(5, 4), nullable=True)  # -1.0 to 1.0
    sentiment_reasoning = Column(Text, nullable=True)  # Polygon's explanation of sentiment
    ticker = Column(String(10), nullable=True, index=True)  # Specific ticker for multi-ticker articles

    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    stock = relationship("Stock", back_populates="news")
