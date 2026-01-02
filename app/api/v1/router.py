from fastapi import APIRouter
from app.api.v1.endpoints import strategies, accounts, logs, fear_greed

api_router = APIRouter()
api_router.include_router(strategies.router, prefix="/strategies", tags=["strategies"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
api_router.include_router(logs.router, prefix="/logs", tags=["logs"])
api_router.include_router(fear_greed.router, prefix="/market", tags=["market"])
# Removed strategy_states and trade_logs as they are now part of the new schema structure

