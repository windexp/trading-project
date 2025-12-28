from pydantic import BaseModel, Json
from typing import Dict, Any, Optional
from datetime import datetime

class StrategyStateBase(BaseModel):
    strategy_name: str
    strategy_type: str
    config: Dict[str, Any]
    state: Dict[str, Any]
    is_active: bool = True

class StrategyStateCreate(StrategyStateBase):
    pass

class StrategyStateUpdate(BaseModel):
    config: Optional[Dict[str, Any]] = None
    state: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class StrategyStateResponse(StrategyStateBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
