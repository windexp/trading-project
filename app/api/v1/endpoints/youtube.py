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
    source_id: Optional[str] = None


class ChannelRequest(BaseModel):
    """채널/플레이리스트 추가 요청"""
    type: str = "channel"  # "channel" or "playlist"
    channel_id: Optional[str] = ""
    playlist_id: Optional[str] = ""
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
async def get_latest_videos(limit: int = 10, source_id: Optional[str] = None):
    """
    등록된 채널의 최신 영상 목록을 가져옵니다.
    
    Args:
        limit: 채널당 가져올 영상 수
        source_id: 필터링할 소스 ID (channel_id 또는 playlist_id)
    """
    try:
        service = get_youtube_summary_service()
        videos = service.get_all_latest_videos(limit_per_channel=limit)
        
        # 소스별 필터링
        if source_id:
            videos = [v for v in videos if v.get('source_id') == source_id]
        
        # 각 영상에 분석 여부 추가
        for video in videos:
            video['is_analyzed'] = service.is_video_analyzed(video['video_id'])
        
        return {
            "videos": videos,
            "total": len(videos),
            "channels": len(service.channel_ids),
            "filtered_by": source_id
        }
    except Exception as e:
        logger.error(f"Failed to get latest videos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summaries")
async def get_all_summaries(limit: int = 50, source_id: Optional[str] = None):
    """
    저장된 모든 요약 목록을 가져옵니다.
    
    Args:
        limit: 최대 반환 개수
        source_id: 필터링할 소스 ID (channel_id 또는 playlist_id)
    """
    try:
        service = get_youtube_summary_service()
        summaries = service.get_all_summaries(limit=limit, source_id=source_id)
        
        return {
            "summaries": summaries,
            "total": len(summaries),
            "filtered_by": source_id
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
        result = await service.analyze_video(
            request.video_id,
            request.title,
            request.channel_name,
            request.source_id
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
async def analyze_new_videos(max_videos: int = 10, delay_seconds: float = 3.0):
    """
    새 영상을 확인하고 분석합니다.
    
    Args:
        max_videos: 한 번에 분석할 최대 영상 수 (기본 10개, rate limit 보호)
        delay_seconds: 각 API 호출 사이의 대기 시간 (기본 3초)
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
        
        # 새 영상 분석 (rate limit 보호)
        results = await service.check_and_analyze_new_videos(
            max_videos=max_videos,
            delay_seconds=delay_seconds
        )
        
        return {
            "status": "success",
            "analyzed": results,
            "count": len(results),
            "total_unanalyzed": len(unanalyzed),
            "remaining": max(0, len(unanalyzed) - len(results))
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


@router.get("/channels/{identifier}")
async def get_channel(identifier: str):
    """
    특정 채널/플레이리스트 정보를 가져옵니다.
    """
    try:
        manager = get_channel_manager()
        channel = manager.get_channel(identifier)
        
        if not channel:
            raise HTTPException(status_code=404, detail="Channel/Playlist not found")
        
        return channel
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get channel {identifier}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/channels")
async def add_channel(request: ChannelRequest):
    """
    새 채널 또는 플레이리스트를 추가합니다.
    """
    try:
        manager = get_channel_manager()
        
        success = manager.add_channel(
            channel_id=request.channel_id,
            channel_name=request.channel_name,
            custom_prompt=request.custom_prompt,
            enabled=request.enabled,
            source_type=request.type,
            playlist_id=request.playlist_id
        )
        
        if success:
            identifier = request.playlist_id if request.type == "playlist" else request.channel_id
            channel = manager.get_channel(identifier)
            return {
                "status": "success",
                "message": f"{request.type.capitalize()} added",
                "channel": channel
            }
        else:
            raise HTTPException(status_code=400, detail=f"{request.type.capitalize()} already exists or failed to add")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add {request.type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/channels/{identifier}")
async def update_channel(identifier: str, request: ChannelUpdateRequest):
    """
    채널/플레이리스트 정보를 수정합니다.
    """
    try:
        manager = get_channel_manager()
        
        success = manager.update_channel(
            identifier=identifier,
            channel_name=request.channel_name,
            custom_prompt=request.custom_prompt,
            enabled=request.enabled
        )
        
        if success:
            channel = manager.get_channel(identifier)
            return {
                "status": "success",
                "message": f"Updated successfully",
                "channel": channel
            }
        else:
            raise HTTPException(status_code=404, detail="Channel/Playlist not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update {identifier}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/channels/{identifier}")
async def delete_channel(identifier: str):
    """
    채널/플레이리스트를 삭제합니다.
    """
    try:
        manager = get_channel_manager()
        success = manager.delete_channel(identifier)
        
        if success:
            return {"status": "success", "message": f"Deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Channel/Playlist not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete {identifier}: {e}")
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
