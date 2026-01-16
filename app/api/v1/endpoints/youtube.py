"""
YouTube Summary API Endpoints
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import logging

from app.services.market_analysis.youtube_summary import (
    get_youtube_summary_service, 
    get_channel_manager
)

logger = logging.getLogger(__name__)
router = APIRouter()


class AnalyzeRequest(BaseModel):
    """영상 분석 요청"""
    video_id: str
    title: str
    channel_name: str
    channel_id: Optional[str] = None


class ChannelRequest(BaseModel):
    """채널 추가/수정 요청"""
    channel_id: str
    channel_name: Optional[str] = ""
    custom_prompt: Optional[str] = ""
    enabled: Optional[bool] = True


class ChannelUpdateRequest(BaseModel):
    """채널 수정 요청"""
    channel_name: Optional[str] = None
    custom_prompt: Optional[str] = None
    enabled: Optional[bool] = None


class PromptRequest(BaseModel):
    """프롬프트 수정 요청"""
    prompt: str


class VideoInfo(BaseModel):
    """영상 정보"""
    video_id: str
    title: str
    link: str
    channel_id: str
    channel_name: str
    published: str


class SummaryResponse(BaseModel):
    """요약 응답"""
    video_id: str
    title: str
    channel_name: str
    url: str
    analyzed_at: str
    summary: Optional[str] = None
    error: Optional[str] = None


@router.get("/videos")
async def get_latest_videos(limit: int = 10):
    """
    등록된 채널의 최신 영상 목록을 가져옵니다.
    """
    try:
        service = get_youtube_summary_service()
        videos = service.get_all_latest_videos(limit_per_channel=limit)
        
        # 각 영상에 분석 여부 추가
        for video in videos:
            video['is_analyzed'] = service.is_video_analyzed(video['video_id'])
        
        return {
            "videos": videos,
            "total": len(videos),
            "channels": len(service.channel_ids)
        }
    except Exception as e:
        logger.error(f"Failed to get latest videos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summaries")
async def get_all_summaries(limit: int = 50):
    """
    저장된 모든 요약 목록을 가져옵니다.
    """
    try:
        service = get_youtube_summary_service()
        summaries = service.get_all_summaries(limit=limit)
        
        return {
            "summaries": summaries,
            "total": len(summaries)
        }
    except Exception as e:
        logger.error(f"Failed to get summaries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary/{video_id}")
async def get_summary(video_id: str):
    """
    특정 영상의 요약 정보를 가져옵니다.
    """
    try:
        service = get_youtube_summary_service()
        summary = service.get_summary(video_id)
        
        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found")
        
        return summary
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get summary for {video_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
async def analyze_video(request: AnalyzeRequest):
    """
    영상을 분석합니다.
    """
    try:
        service = get_youtube_summary_service()
        
        # 이미 분석된 영상인지 확인
        if service.is_video_analyzed(request.video_id):
            existing = service.get_summary(request.video_id)
            return {
                "status": "already_analyzed",
                "summary": existing
            }
        
        # 분석 실행
        result = service.analyze_video(
            request.video_id,
            request.title,
            request.channel_name,
            request.channel_id
        )
        
        if result:
            return {
                "status": "success",
                "summary": result
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to analyze video")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to analyze video {request.video_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-new")
async def analyze_new_videos():
    """
    새 영상을 확인하고 분석합니다.
    """
    try:
        service = get_youtube_summary_service()
        
        # 분석되지 않은 영상 확인
        unanalyzed = service.get_unanalyzed_videos()
        
        if not unanalyzed:
            return {
                "status": "no_new_videos",
                "analyzed": [],
                "count": 0
            }
        
        # 새 영상 분석
        results = service.check_and_analyze_new_videos()
        
        return {
            "status": "success",
            "analyzed": results,
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"Failed to analyze new videos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/summary/{video_id}")
async def delete_summary(video_id: str):
    """
    요약을 삭제합니다.
    """
    try:
        service = get_youtube_summary_service()
        success = service.delete_summary(video_id)
        
        if success:
            return {"status": "success", "message": f"Summary {video_id} deleted"}
        else:
            raise HTTPException(status_code=404, detail="Summary not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete summary {video_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/channels")
async def get_channels():
    """
    등록된 채널 정보를 가져옵니다.
    """
    try:
        manager = get_channel_manager()
        channels = manager.get_channels()
        
        return {
            "channels": channels,
            "total": len(channels)
        }
    except Exception as e:
        logger.error(f"Failed to get channels: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/channels/{channel_id}")
async def get_channel(channel_id: str):
    """
    특정 채널 정보를 가져옵니다.
    """
    try:
        manager = get_channel_manager()
        channel = manager.get_channel(channel_id)
        
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")
        
        return channel
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get channel {channel_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/channels")
async def add_channel(request: ChannelRequest):
    """
    새 채널을 추가합니다.
    """
    try:
        manager = get_channel_manager()
        
        success = manager.add_channel(
            channel_id=request.channel_id,
            channel_name=request.channel_name,
            custom_prompt=request.custom_prompt,
            enabled=request.enabled
        )
        
        if success:
            channel = manager.get_channel(request.channel_id)
            return {
                "status": "success",
                "message": f"Channel {request.channel_id} added",
                "channel": channel
            }
        else:
            raise HTTPException(status_code=400, detail="Channel already exists or failed to add")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add channel: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/channels/{channel_id}")
async def update_channel(channel_id: str, request: ChannelUpdateRequest):
    """
    채널 정보를 수정합니다.
    """
    try:
        manager = get_channel_manager()
        
        success = manager.update_channel(
            channel_id=channel_id,
            channel_name=request.channel_name,
            custom_prompt=request.custom_prompt,
            enabled=request.enabled
        )
        
        if success:
            channel = manager.get_channel(channel_id)
            return {
                "status": "success",
                "message": f"Channel {channel_id} updated",
                "channel": channel
            }
        else:
            raise HTTPException(status_code=404, detail="Channel not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update channel {channel_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/channels/{channel_id}")
async def delete_channel(channel_id: str):
    """
    채널을 삭제합니다.
    """
    try:
        manager = get_channel_manager()
        success = manager.delete_channel(channel_id)
        
        if success:
            return {"status": "success", "message": f"Channel {channel_id} deleted"}
        else:
            raise HTTPException(status_code=404, detail="Channel not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete channel {channel_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prompt/default")
async def get_default_prompt():
    """
    기본 프롬프트를 가져옵니다.
    """
    try:
        manager = get_channel_manager()
        prompt = manager.get_default_prompt()
        
        return {"prompt": prompt}
    except Exception as e:
        logger.error(f"Failed to get default prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/prompt/default")
async def set_default_prompt(request: PromptRequest):
    """
    기본 프롬프트를 설정합니다.
    """
    try:
        manager = get_channel_manager()
        success = manager.set_default_prompt(request.prompt)
        
        if success:
            return {"status": "success", "message": "Default prompt updated"}
        else:
            raise HTTPException(status_code=500, detail="Failed to update prompt")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set default prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))
