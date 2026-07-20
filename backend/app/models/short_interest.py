"""
Short Interest model for tracking short selling data
"""
from sqlalchemy import Column, Integer, BigInteger, ForeignKey, Date, TIMESTAMP, DECIMAL, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base


class ShortInterest(Base):
    """Short interest data for stocks"""
    __tablename__ = "short_interest"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey('stocks.id', ondelete='CASCADE'), nullable=False, index=True)

    # Short interest details
    settlement_date = Column(Date, nullable=False, index=True)  # Settlement date of the report
    short_interest = Column(BigInteger, nullable=False)  # Number of shares sold short
    avg_volume_30d = Column(BigInteger, nullable=True)  # 30-day average volume
    days_to_cover = Column(DECIMAL(8, 2), nullable=True)  # short_interest / avg_volume_30d

    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    stock = relationship("Stock", back_populates="short_interest_data")

    __table_args__ = (
        UniqueConstraint('stock_id', 'settlement_date', name='uq_stock_settlement_date'),
    )
