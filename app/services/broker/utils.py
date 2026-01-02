"""
Broker utility functions
"""
from typing import Optional
from sqlalchemy.orm import Session
from app.models.account import Account
from app.services.broker.base import BaseBroker
from app.services.broker.koreainvestment import KoreaInvestmentBroker


def get_broker(account_name: str, db: Session) -> Optional[BaseBroker]:
    """
    계정명으로 브로커 인스턴스를 생성합니다.
    
    Args:
        account_name: 계정 번호 (예: "12345678-01")
        db: 데이터베이스 세션
        
    Returns:
        BaseBroker: 브로커 인스턴스 또는 None
    """
    account = db.query(Account).filter(Account.account_no == account_name).first()
    if not account:
        return None
    
    if account.broker == "KIS":
        return KoreaInvestmentBroker(
            account_no=account.account_no,
            app_key=account.app_key,
            app_secret=account.app_secret
        )
    else:
        # 다른 브로커 지원 시 추가
        raise ValueError(f"Unsupported broker: {account.broker}")
