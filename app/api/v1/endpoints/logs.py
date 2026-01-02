"""
로그 관련 API 엔드포인트
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.core.logging_config import get_log_files, read_log_file

router = APIRouter()


class LogFileInfo(BaseModel):
    """로그 파일 정보"""
    name: str
    path: str
    size: int
    modified: float
    modified_date: str
    size_mb: float


@router.get("/files", response_model=List[LogFileInfo])
def list_log_files(limit: int = Query(default=50, ge=1, le=100)):
    """
    로그 파일 목록을 반환합니다.
    
    Args:
        limit: 반환할 최대 파일 개수 (1-100)
    """
    try:
        files = get_log_files(limit=limit)
        
        # 추가 정보 포맷팅
        result = []
        for file_info in files:
            result.append(LogFileInfo(
                name=file_info['name'],
                path=file_info['path'],
                size=file_info['size'],
                modified=file_info['modified'],
                modified_date=datetime.fromtimestamp(file_info['modified']).strftime('%Y-%m-%d %H:%M:%S'),
                size_mb=round(file_info['size'] / 1024 / 1024, 2)
            ))
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list log files: {str(e)}")


@router.get("/content", response_class=PlainTextResponse)
def get_log_content(
    filename: str = Query(default="trading.log", description="로그 파일명"),
    lines: int = Query(default=100, ge=1, le=10000, description="읽을 줄 수")
):
    """
    로그 파일의 마지막 N줄을 반환합니다.
    
    Args:
        filename: 로그 파일명
        lines: 읽을 줄 수 (1-10000)
    """
    try:
        content = read_log_file(filename, lines)
        return content
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Log file not found: {filename}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read log file: {str(e)}")
