
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 시작 시 DB 테이블 생성 및 계정 초기화
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        init_accounts(db)
    finally:
        db.close()
    yield
    # 앱 종료 시 추가 정리 작업 필요시 여기에 작성


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
