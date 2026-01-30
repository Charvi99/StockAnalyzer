"""
Stock Split model for tracking stock split history
"""
from sqlalchemy import Column, Integer, ForeignKey, Date, TIMESTAMP, DECIMAL, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base


class StockSplit(Base):
    """Stock splits history"""
    __tablename__ = "stock_splits"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey('stocks.id', ondelete='CASCADE'), nullable=False, index=True)

    # Split details
    execution_date = Column(Date, nullable=False, index=True)  # Date split takes effect
    split_from = Column(DECIMAL(12, 6), nullable=False)  # Original shares (e.g., 1.0)
    split_to = Column(DECIMAL(12, 6), nullable=False)  # New shares (e.g., 2.0 for 2-for-1)
    split_ratio = Column(DECIMAL(12, 6), nullable=False)  # Calculated ratio (split_to / split_from)

    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    stock = relationship("Stock", back_populates="splits")

    __table_args__ = (
        UniqueConstraint('stock_id', 'execution_date', name='uq_stock_execution_date'),
    )
