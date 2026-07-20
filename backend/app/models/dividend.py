"""
Dividend model for storing dividend payment history
"""
from sqlalchemy import Column, Integer, String, ForeignKey, Date, TIMESTAMP, DECIMAL, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base


class Dividend(Base):
    """Dividend payments for stocks"""
    __tablename__ = "dividends"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey('stocks.id', ondelete='CASCADE'), nullable=False, index=True)

    # Dividend dates
    ex_dividend_date = Column(Date, nullable=False, index=True)  # Date stock trades ex-dividend
    payment_date = Column(Date, nullable=True)  # Actual payment date
    record_date = Column(Date, nullable=True)  # Date to be on record
    declaration_date = Column(Date, nullable=True)  # Date dividend was declared

    # Dividend details
    cash_amount = Column(DECIMAL(12, 4), nullable=False)  # Dividend amount per share
    frequency = Column(Integer, nullable=True)  # 1=annually, 4=quarterly, 12=monthly
    dividend_type = Column(String(50), nullable=True)  # 'CD' = cash, 'SC' = stock, etc.

    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    stock = relationship("Stock", back_populates="dividends")

    __table_args__ = (
        UniqueConstraint('stock_id', 'ex_dividend_date', name='uq_stock_ex_dividend_date'),
    )
