from sqlalchemy import Column, Integer, String, TIMESTAMP, DECIMAL, BigInteger, ForeignKey, CheckConstraint, Boolean, Text, text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
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
    candlestick_patterns = relationship("CandlestickPattern", back_populates="stock", cascade="all, delete-orphan")
    chart_patterns = relationship("ChartPattern", back_populates="stock", cascade="all, delete-orphan")


class StockPrice(Base):
    __tablename__ = "stock_prices"

    # Composite primary key: (stock_id, timeframe, timestamp)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), primary_key=True)
    timeframe = Column(String(10), primary_key=True)  # '1m', '5m', '15m', '1h', '4h', '1d', '1w'
    timestamp = Column(TIMESTAMP, primary_key=True)

    id = Column(Integer, server_default=text("nextval('stock_prices_id_seq'::regclass)"))
    open = Column(DECIMAL(12, 4))
    high = Column(DECIMAL(12, 4))
    low = Column(DECIMAL(12, 4))
    close = Column(DECIMAL(12, 4))
    volume = Column(BigInteger)
    adjusted_close = Column(DECIMAL(12, 4))

    # Add constraint for valid timeframes
    __table_args__ = (
        CheckConstraint(
            "timeframe IN ('1m', '5m', '15m', '30m', '1h', '2h', '4h', '1d', '1w', '1mo')",
            name="check_valid_timeframe"
        ),
    )

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


class CandlestickPattern(Base):
    __tablename__ = "candlestick_patterns"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    pattern_name = Column(String(100), nullable=False)
    pattern_type = Column(String(20), nullable=False)
    timestamp = Column(TIMESTAMP, nullable=False)
    confidence_score = Column(DECIMAL(5, 4), default=1.0)
    candle_data = Column(JSONB)  # Stores OHLC data for the pattern
    user_confirmed = Column(Boolean, default=None, nullable=True)  # NULL = not reviewed, TRUE = confirmed, FALSE = rejected
    confirmed_at = Column(TIMESTAMP, nullable=True)
    confirmed_by = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        CheckConstraint("pattern_type IN ('bullish', 'bearish', 'neutral')", name="check_pattern_type"),
    )

    # Relationship
    stock = relationship("Stock", back_populates="candlestick_patterns")


class ChartPattern(Base):
    __tablename__ = "chart_patterns"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    pattern_name = Column(String(100), nullable=False)
    pattern_type = Column(String(20), nullable=False)  # reversal, continuation
    signal = Column(String(20), nullable=False)  # bullish, bearish, neutral
    start_date = Column(TIMESTAMP, nullable=False)
    end_date = Column(TIMESTAMP, nullable=False)
    breakout_price = Column(DECIMAL(12, 4))
    target_price = Column(DECIMAL(12, 4))
    stop_loss = Column(DECIMAL(12, 4))
    confidence_score = Column(DECIMAL(5, 4), default=0.5)
    key_points = Column(JSONB)  # Support/resistance levels, peaks, troughs
    trendlines = Column(JSONB)  # Line coordinates for visualization

    # Multi-timeframe analysis fields
    primary_timeframe = Column(String(10), default='1d')  # Primary timeframe detected on
    detected_on_timeframes = Column(JSONB)  # List of timeframes: ['1h', '4h', '1d']
    confirmation_level = Column(Integer, default=1)  # 1=single, 2=two, 3=three timeframes
    base_confidence = Column(DECIMAL(5, 4))  # Original confidence before boost
    alignment_score = Column(DECIMAL(5, 4))  # Cross-timeframe alignment (0.0-1.0)

    user_confirmed = Column(Boolean, default=None, nullable=True)
    confirmed_at = Column(TIMESTAMP, nullable=True)
    confirmed_by = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        CheckConstraint("pattern_type IN ('reversal', 'continuation')", name="check_chart_pattern_type"),
        CheckConstraint("signal IN ('bullish', 'bearish', 'neutral')", name="check_chart_signal"),
    )

    # Relationship
    stock = relationship("Stock", back_populates="chart_patterns")
