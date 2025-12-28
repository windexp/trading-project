from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.sql import func
from app.core.database import Base

class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    account_no = Column(String, unique=True, index=True, nullable=False) # 12345678-01
    account_name = Column(String, nullable=True) # e.g., "VR_Main"

    # API Credentials (Optional: if different per account)
    app_key = Column(String, nullable=True)
    app_secret = Column(String, nullable=True)

    # Broker (for multi-broker support)
    broker = Column(String, nullable=True, default="KIS")

    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Account(account_no={self.account_no}, name={self.account_name}, broker={self.broker})>"
