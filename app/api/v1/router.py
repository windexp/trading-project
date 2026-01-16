from fastapi import APIRouter
from app.api.v1.endpoints import strategies, accounts, logs, youtube

api_router = APIRouter()
api_router.include_router(strategies.router, prefix="/strategies", tags=["strategies"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
api_router.include_router(logs.router, prefix="/logs", tags=["logs"])
api_router.include_router(youtube.router, prefix="/youtube", tags=["youtube"])

