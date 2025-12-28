from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, JSON,
    UniqueConstraint, Index, Boolean, Numeric, Text
)
from sqlalchemy.orm import relationship
from datetime import datetime
import pytz
# KST timezone-aware datetime 생성 함수
def now_kst():
    return datetime.now(pytz.timezone('Asia/Seoul'))
from app.core.database import Base
from app.models.enums import StrategyStatus, OrderStatus, OrderType

# 1. 전략 마스터 테이블
class Strategy(Base):
    __tablename__ = 'strategy'
    id = Column(Integer, primary_key=True)
    name = Column(String(30), unique=True, nullable=False)
    account_name = Column(String(30), nullable=False) # e.g. "64827830-01"
    strategy_code = Column(String(30), nullable=False) # "VR", "InfBuy"
    status = Column(String(30), nullable=False, default=StrategyStatus.ACTIVE)
    base_params = Column(JSON, nullable=False)
    description = Column(String(255))
    
    # 관계
    snapshots = relationship(
        "StrategySnapshot",
        back_populates="strategy",
        order_by="desc(StrategySnapshot.created_at)",
        cascade="all, delete-orphan"
    )
    
    created_at = Column(DateTime, default=now_kst, nullable=False)
    updated_at = Column(DateTime, default=now_kst, onupdate=now_kst)
    
    __table_args__ = (
        Index('ix_strategy_code_status', 'strategy_code', 'status'),
        Index('ix_strategy_name_status', 'name', 'status'),
    )

# 2. 전략 실행/상태 테이블
class StrategySnapshot(Base):
    __tablename__ = 'strategy_snapshot'
    id = Column(Integer, primary_key=True)
    strategy_id = Column(Integer, ForeignKey('strategy.id'), nullable=False)
    status = Column(String(30), nullable=False) # e.g. "IN_PROGRESS", "COMPLETED"
    cycle = Column(Integer, default=1)
    step = Column(Integer, default=1)
    progress = Column(JSON, nullable=False)       # parameters by strategy (The State)
    created_at = Column(DateTime, default=now_kst, nullable=False)  # 실행 시각
    updated_at = Column(DateTime, default=now_kst, onupdate=now_kst)
    executed_at = Column(DateTime, nullable=True)  # 주문이 실제로 성공한 날짜

    strategy = relationship("Strategy", back_populates="snapshots")
    orders = relationship("Order", back_populates="snapshot", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('strategy_id', 'created_at', name='uq_strategy_status_once_per_time'),
        Index('ix_strategy_id_round_number', 'strategy_id', 'cycle'),
    )

# 3. 주문 테이블
class Order(Base):
    __tablename__ = 'order'
    id = Column(Integer, primary_key=True)
    # 증권사 주문번호 (UNIQUE, 비즈니스 키)
    order_id = Column(String(30), unique=True, nullable=False, index=True)
    snapshot_id = Column(Integer, ForeignKey('strategy_snapshot.id'), nullable=False)

    order_status = Column(String(30), nullable=False, default=OrderStatus.SUBMITTED)
    order_type = Column(String(30), nullable=False) # BUY / SELL

    symbol = Column(String(20), nullable=False)
    order_qty = Column(Integer, nullable=False)
    order_price = Column(Numeric(15, 4), nullable=False)

    ordered_at = Column(DateTime, default=now_kst, nullable=False)
    updated_at = Column(DateTime, default=now_kst, onupdate=now_kst)

    filled_qty = Column(Integer, default=0)
    filled_price = Column(Numeric(15, 4))
    fees = Column(Numeric(10, 2), default=0)

    extra = Column(JSON) # For storing original API response or debug info
    
    # 관계
    snapshot = relationship("StrategySnapshot", back_populates="orders")

    __table_args__ = (
        Index('ix_order_status_symbol', 'order_status', 'symbol'),
        Index('ix_order_snapshot_id_status', 'snapshot_id', 'order_status'),
        Index('ix_order_ordered_at', 'ordered_at'),
    )
