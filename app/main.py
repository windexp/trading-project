
import sys
import os
from contextlib import asynccontextmanager


from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.core.config import settings
from app.api.v1.router import api_router
from app.core.database import engine, Base, SessionLocal
from app.core.init_db import init_accounts
from app.models.schema import Strategy, StrategySnapshot, Order
from app.services.scheduler import strategy_scheduler
from app.core.logging_config import setup_logging

# 로깅 설정
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 시작 시 DB 테이블 생성 및 계정 초기화
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        init_accounts(db)
    finally:
        db.close()
    
    # 스케줄러 시작
    strategy_scheduler.start()
    
    yield
    
    # 앱 종료 시 스케줄러 정지
    strategy_scheduler.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)


# Mount Static Files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return FileResponse("app/static/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, log_level="debug")
