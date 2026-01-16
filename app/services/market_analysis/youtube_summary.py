"""
YouTube Summary Service
YouTube 채널의 최신 영상을 모니터링하고 AI로 분석하는 서비스
"""
import os
import json
import re
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any
from pathlib import Path

import feedparser
from google import genai

logger = logging.getLogger(__name__)

# 데이터 저장 경로 (프로젝트 루트 기준)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SUMMARIES_DIR = DATA_DIR / "youtube_summaries"
CHANNELS_CONFIG_FILE = DATA_DIR / "youtube_channels.json"

# 기본 프롬프트 템플릿
DEFAULT_PROMPT = """당신은 주식 시장 분석 전문가입니다. 아래 YouTube 영상을 분석하여 주요 내용을 요약해주세요.

영상 정보:
- 제목: {title}
- 채널: {channel_name}
- URL: {video_url}

다음 형식으로 분석 결과를 제공해주세요:

1. **영상 개요**: 영상의 주요 주제와 목적을 2-3문장으로 요약

2. **기술적 분석 포인트**:
   - 언급된 주요 지표 (이동평균선, RSI, MACD 등)
   - 차트 패턴 분석 내용
   - 지지/저항 레벨

3. **시장 전망**:
   - 단기 전망 (1-2주)
   - 중기 전망 (1-3개월)
   - 주요 상승/하락 시나리오

4. **언급된 종목/지수**:
   - 종목명과 간단한 분석 내용

5. **핵심 투자 인사이트**:
   - 가장 중요한 3가지 포인트를 bullet point로 정리

6. **주의사항/리스크**:
   - 언급된 위험 요소나 주의해야 할 점

응답은 한국어로 작성하고, 명확하고 간결하게 정리해주세요."""


class YouTubeChannelManager:
    """YouTube 채널 및 프롬프트 설정 관리"""
    
    def __init__(self):
        self._ensure_config_file()
    
    def _ensure_config_file(self):
        """설정 파일이 없으면 생성"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        if not CHANNELS_CONFIG_FILE.exists():
            default_config = {
                "channels": [],
                "default_prompt": DEFAULT_PROMPT
            }
            with open(CHANNELS_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
    
    def _load_config(self) -> Dict[str, Any]:
        """설정 파일 로드"""
        try:
            with open(CHANNELS_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {"channels": [], "default_prompt": DEFAULT_PROMPT}
    
    def _save_config(self, config: Dict[str, Any]) -> bool:
        """설정 파일 저장"""
        try:
            with open(CHANNELS_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False
    
    def get_channels(self) -> List[Dict[str, Any]]:
        """등록된 채널 목록 반환"""
        config = self._load_config()
        return config.get("channels", [])
    
    def get_channel(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """특정 채널 정보 반환"""
        channels = self.get_channels()
        for channel in channels:
            if channel.get("channel_id") == channel_id:
                return channel
        return None
    
    def add_channel(self, channel_id: str, channel_name: str = "", 
                    custom_prompt: str = "", enabled: bool = True) -> bool:
        """채널 추가"""
        config = self._load_config()
        
        # 중복 확인
        for channel in config["channels"]:
            if channel.get("channel_id") == channel_id:
                return False  # 이미 존재
        
        # RSS에서 채널 이름 가져오기 (이름이 없는 경우)
        if not channel_name:
            try:
                RSS_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
                feed = feedparser.parse(RSS_URL)
                if hasattr(feed.feed, 'title'):
                    channel_name = feed.feed.title
                else:
                    channel_name = "Unknown Channel"
            except:
                channel_name = "Unknown Channel"
        
        config["channels"].append({
            "channel_id": channel_id,
            "channel_name": channel_name,
            "custom_prompt": custom_prompt,
            "enabled": enabled,
            "created_at": datetime.now().isoformat()
        })
        
        return self._save_config(config)
    
    def update_channel(self, channel_id: str, channel_name: str = None, 
                       custom_prompt: str = None, enabled: bool = None) -> bool:
        """채널 정보 수정"""
        config = self._load_config()
        
        for channel in config["channels"]:
            if channel.get("channel_id") == channel_id:
                if channel_name is not None:
                    channel["channel_name"] = channel_name
                if custom_prompt is not None:
                    channel["custom_prompt"] = custom_prompt
                if enabled is not None:
                    channel["enabled"] = enabled
                channel["updated_at"] = datetime.now().isoformat()
                return self._save_config(config)
        
        return False
    
    def delete_channel(self, channel_id: str) -> bool:
        """채널 삭제"""
        config = self._load_config()
        original_len = len(config["channels"])
        config["channels"] = [c for c in config["channels"] if c.get("channel_id") != channel_id]
        
        if len(config["channels"]) < original_len:
            return self._save_config(config)
        return False
    
    def get_default_prompt(self) -> str:
        """기본 프롬프트 반환"""
        config = self._load_config()
        prompt = config.get("default_prompt", DEFAULT_PROMPT)
        # 배열 형식이면 줄바꿈으로 연결
        if isinstance(prompt, list):
            return "\n".join(prompt)
        return prompt
    
    def set_default_prompt(self, prompt: str) -> bool:
        """기본 프롬프트 설정"""
        config = self._load_config()
        # 문자열이면 배열로 변환하여 저장 (가독성 향상)
        if isinstance(prompt, str):
            prompt = prompt.split("\n")
        config["default_prompt"] = prompt
        return self._save_config(config)
    
    def get_prompt_for_channel(self, channel_id: str) -> str:
        """채널에 맞는 프롬프트 반환 (커스텀 또는 기본)"""
        channel = self.get_channel(channel_id)
        if channel and channel.get("custom_prompt"):
            prompt = channel["custom_prompt"]
            # 배열 형식이면 줄바꿈으로 연결
            if isinstance(prompt, list):
                return "\n".join(prompt)
            return prompt
        return self.get_default_prompt()


class YouTubeSummaryService:
    """YouTube 채널 모니터링 및 AI 요약 서비스"""
    
    def __init__(self, gemini_api_key: Optional[str] = None):
        """
        Args:
            gemini_api_key: Gemini API 키
        """
        self.gemini_api_key = gemini_api_key
        self.gemini_client = None
        self.channel_manager = YouTubeChannelManager()
        
        # Gemini 클라이언트 초기화
        if self.gemini_api_key:
            os.environ['GEMINI_API_KEY'] = self.gemini_api_key
            self.gemini_client = genai.Client()
        
        # 저장 디렉토리 생성
        SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)
        
        logger.info("YouTubeSummaryService initialized")
    
    @property
    def channel_ids(self) -> List[str]:
        """활성화된 채널 ID 목록"""
        channels = self.channel_manager.get_channels()
        return [c["channel_id"] for c in channels if c.get("enabled", True)]

    def get_videos_from_rss(self, channel_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        RSS 피드를 통해 채널의 최신 영상 정보를 가져옵니다.
        """
        RSS_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        feed = feedparser.parse(RSS_URL)
        
        if not feed.entries:
            logger.warning(f"No videos found for channel: {channel_id}")
            return []
        
        channel_name = feed.feed.title if hasattr(feed.feed, 'title') else "Unknown"
        
        videos = []
        for entry in feed.entries[:limit]:
            video_id_match = re.search(r'v=([^&]+)', entry.link)
            if not video_id_match:
                continue
                
            video_id = video_id_match.group(1)
            published = entry.get('published', '')
            
            # 발행일 파싱
            try:
                if published:
                    published_dt = datetime.strptime(published, '%Y-%m-%dT%H:%M:%S%z')
                    published_str = published_dt.strftime('%Y-%m-%d %H:%M')
                else:
                    published_str = ''
            except:
                published_str = published
            
            videos.append({
                'video_id': video_id,
                'title': entry.title,
                'link': entry.link,
                'channel_id': channel_id,
                'channel_name': channel_name,
                'published': published_str,
                'published_raw': published
            })
        
        return videos

    def get_all_latest_videos(self, limit_per_channel: int = 5) -> List[Dict[str, Any]]:
        """모든 활성화된 채널의 최신 영상을 가져옵니다."""
        all_videos = []
        
        for channel_id in self.channel_ids:
            try:
                videos = self.get_videos_from_rss(channel_id, limit_per_channel)
                all_videos.extend(videos)
            except Exception as e:
                logger.error(f"Failed to fetch videos from channel {channel_id}: {e}")
        
        # 발행일 기준 정렬 (최신순)
        all_videos.sort(key=lambda x: x.get('published_raw', ''), reverse=True)
        
        return all_videos

    def is_video_analyzed(self, video_id: str) -> bool:
        """해당 영상이 이미 분석되었는지 확인"""
        summary_file = SUMMARIES_DIR / f"{video_id}.json"
        return summary_file.exists()

    def get_unanalyzed_videos(self) -> List[Dict[str, Any]]:
        """아직 분석되지 않은 새 영상 목록을 반환"""
        all_videos = self.get_all_latest_videos()
        return [v for v in all_videos if not self.is_video_analyzed(v['video_id'])]

    def analyze_video(self, video_id: str, video_title: str, channel_name: str, 
                      channel_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Gemini AI를 사용하여 영상 내용을 분석합니다.
        """
        if not self.gemini_client:
            logger.error("Gemini client not initialized")
            return None
        
        try:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            
            # 채널에 맞는 프롬프트 가져오기
            if channel_id:
                prompt_template = self.channel_manager.get_prompt_for_channel(channel_id)
            else:
                prompt_template = self.channel_manager.get_default_prompt()
            
            # 프롬프트 변수 치환
            prompt = prompt_template.format(
                title=video_title,
                channel_name=channel_name,
                video_url=video_url
            )

            # Gemini API 호출 (YouTube URL 분석)
            response = self.gemini_client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=[
                    {
                        "role": "user",
                        "parts": [
                            {"text": prompt},
                            {"file_data": {"file_uri": video_url, "mime_type": "video/*"}}
                        ]
                    }
                ]
            )
            
            summary_text = response.text
            
            # 분석 결과 저장
            result = {
                'video_id': video_id,
                'title': video_title,
                'channel_id': channel_id,
                'channel_name': channel_name,
                'url': video_url,
                'analyzed_at': datetime.now().isoformat(),
                'summary': summary_text,
                'model': 'gemini-3-flash-preview'
            }
            
            # JSON 파일로 저장
            self._save_summary(result)
            
            logger.info(f"Successfully analyzed video: {video_title}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to analyze video {video_id}: {e}")
            
            # 에러 발생 시에도 시도 기록
            error_result = {
                'video_id': video_id,
                'title': video_title,
                'channel_id': channel_id,
                'channel_name': channel_name,
                'url': f"https://www.youtube.com/watch?v={video_id}",
                'analyzed_at': datetime.now().isoformat(),
                'summary': None,
                'error': str(e),
                'model': 'gemini-3-flash-preview'
            }
            return error_result

    def _save_summary(self, result: Dict[str, Any]) -> None:
        """분석 결과를 JSON 파일로 저장"""
        video_id = result['video_id']
        summary_file = SUMMARIES_DIR / f"{video_id}.json"
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Summary saved: {summary_file}")

    def get_summary(self, video_id: str) -> Optional[Dict[str, Any]]:
        """저장된 요약 정보를 불러옵니다."""
        summary_file = SUMMARIES_DIR / f"{video_id}.json"
        
        if not summary_file.exists():
            return None
        
        with open(summary_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_all_summaries(self, limit: int = 50) -> List[Dict[str, Any]]:
        """저장된 모든 요약 목록을 반환합니다."""
        summaries = []
        
        if not SUMMARIES_DIR.exists():
            return summaries
        
        summary_files = sorted(
            SUMMARIES_DIR.glob("*.json"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )[:limit]
        
        for summary_file in summary_files:
            try:
                with open(summary_file, 'r', encoding='utf-8') as f:
                    summary = json.load(f)
                    summaries.append({
                        'video_id': summary.get('video_id'),
                        'title': summary.get('title'),
                        'channel_name': summary.get('channel_name'),
                        'url': summary.get('url'),
                        'analyzed_at': summary.get('analyzed_at'),
                        'has_error': bool(summary.get('error'))
                    })
            except Exception as e:
                logger.error(f"Failed to read summary file {summary_file}: {e}")
        
        return summaries

    def check_and_analyze_new_videos(self) -> List[Dict[str, Any]]:
        """새 영상을 확인하고 분석합니다."""
        unanalyzed = self.get_unanalyzed_videos()
        
        if not unanalyzed:
            logger.info("No new videos to analyze")
            return []
        
        results = []
        for video in unanalyzed:
            result = self.analyze_video(
                video['video_id'],
                video['title'],
                video['channel_name'],
                video.get('channel_id')
            )
            if result:
                results.append(result)
        
        return results

    def delete_summary(self, video_id: str) -> bool:
        """요약 파일을 삭제합니다."""
        summary_file = SUMMARIES_DIR / f"{video_id}.json"
        
        if summary_file.exists():
            summary_file.unlink()
            logger.info(f"Summary deleted: {video_id}")
            return True
        
        return False
    
    def cleanup_old_summaries(self, days: int = 7) -> int:
        """지정된 일수보다 오래된 요약 파일을 삭제합니다."""
        if not SUMMARIES_DIR.exists():
            return 0
        
        from datetime import timedelta
        cutoff_time = datetime.now().timestamp() - (days * 24 * 3600)
        deleted_count = 0
        
        for summary_file in SUMMARIES_DIR.glob("*.json"):
            try:
                if summary_file.stat().st_mtime < cutoff_time:
                    summary_file.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted old summary: {summary_file.name}")
            except Exception as e:
                logger.error(f"Failed to delete {summary_file.name}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old summary file(s)")
        
        return deleted_count


# 글로벌 서비스 인스턴스
_youtube_service_instance: Optional[YouTubeSummaryService] = None


def get_youtube_summary_service() -> YouTubeSummaryService:
    """YouTube Summary 서비스 인스턴스를 반환합니다."""
    global _youtube_service_instance
    
    if _youtube_service_instance is None:
        from app.core.config import settings
        gemini_api_key = getattr(settings, 'GEMINI_API_KEY', '') or os.getenv('GEMINI_API_KEY', '')
        _youtube_service_instance = YouTubeSummaryService(gemini_api_key=gemini_api_key)
    
    return _youtube_service_instance


def get_channel_manager() -> YouTubeChannelManager:
    """채널 관리자 인스턴스를 반환합니다."""
    return YouTubeChannelManager()
