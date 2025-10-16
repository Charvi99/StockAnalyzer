from sqlalchemy import Column, Integer, String, TIMESTAMP, DECIMAL, BigInteger, ForeignKey, CheckConstraint, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(255))
    sector = Column(String(100))
    industry = Column(String(100))
    is_tracked = Column(Boolean, default=True, server_default='true')
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    prices = relationship("StockPrice", back_populates="stock", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="stock", cascade="all, delete-orphan")
    indicators = relationship("TechnicalIndicator", back_populates="stock", cascade="all, delete-orphan")
    sentiment_scores = relationship("SentimentScore", back_populates="stock", cascade="all, delete-orphan")


class StockPrice(Base):
    __tablename__ = "stock_prices"

    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(TIMESTAMP, nullable=False)
    open = Column(DECIMAL(12, 4))
    high = Column(DECIMAL(12, 4))
    low = Column(DECIMAL(12, 4))
    close = Column(DECIMAL(12, 4))
    volume = Column(BigInteger)
    adjusted_close = Column(DECIMAL(12, 4))

    # Relationship
    stock = relationship("Stock", back_populates="prices")


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    prediction_date = Column(TIMESTAMP, nullable=False)
    target_date = Column(TIMESTAMP, nullable=False)
    predicted_price = Column(DECIMAL(12, 4))
    predicted_change_percent = Column(DECIMAL(8, 4))
    confidence_score = Column(DECIMAL(5, 4))
    model_version = Column(String(50))
    recommendation = Column(String(10))
    created_at = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        CheckConstraint("recommendation IN ('BUY', 'SELL', 'HOLD')", name="check_recommendation"),
    )

    # Relationships
    stock = relationship("Stock", back_populates="predictions")
    performance = relationship("PredictionPerformance", back_populates="prediction", cascade="all, delete-orphan")


class PredictionPerformance(Base):
    __tablename__ = "prediction_performance"

    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False)
    actual_price = Column(DECIMAL(12, 4))
    actual_change_percent = Column(DECIMAL(8, 4))
    prediction_error = Column(DECIMAL(12, 4))
    accuracy_score = Column(DECIMAL(5, 4))
    evaluated_at = Column(TIMESTAMP, server_default=func.now())

    # Relationship
    prediction = relationship("Prediction", back_populates="performance")


class TechnicalIndicator(Base):
    __tablename__ = "technical_indicators"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(TIMESTAMP, nullable=False)
    indicator_name = Column(String(50), nullable=False)
    value = Column(DECIMAL(12, 4))

    # Relationship
    stock = relationship("Stock", back_populates="indicators")


class SentimentScore(Base):
    __tablename__ = "sentiment_scores"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(TIMESTAMP, nullable=False)
    sentiment_index = Column(DECIMAL(8, 4))
    positive_count = Column(Integer, default=0)
    negative_count = Column(Integer, default=0)
    neutral_count = Column(Integer, default=0)
    positive_pct = Column(DECIMAL(5, 2))
    negative_pct = Column(DECIMAL(5, 2))
    neutral_pct = Column(DECIMAL(5, 2))
    total_articles = Column(Integer, default=0)
    trend = Column(String(20))
    created_at = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        CheckConstraint("trend IN ('Rise', 'Fall', 'Neutral')", name="check_trend"),
    )

    # Relationship
    stock = relationship("Stock", back_populates="sentiment_scores")
