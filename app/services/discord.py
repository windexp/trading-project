"""
Discord Service
Discord 채널로 메시지를 전송하는 서비스 (Webhook & Bot)
"""
import os
import json
import requests
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Discord 색상 매핑
COLOR_MAP = {
    "BLUE": 0x3498db,
    "GREEN": 0x2ecc71,
    "RED": 0xe74c3c,
    "YELLOW": 0xf39c12,
    "PURPLE": 0x9b59b6,
    "ORANGE": 0xe67e22,
    "GRAY": 0x95a5a6,
}


class DiscordWebhook:
    """Discord Webhook 클라이언트"""
    
    def __init__(self, channel: str = "private"):
        """
        Args:
            channel: "private" 또는 "public"
        """
        webhook_urls = self._load_webhook_urls()
        if channel not in webhook_urls:
            raise ValueError(f"Invalid channel: {channel}. Available: {list(webhook_urls.keys())}")
        
        self.url = webhook_urls[channel]
        self.channel = channel
        
    @staticmethod
    def _load_webhook_urls() -> Dict[str, str]:
        """환경 변수에서 Discord Webhook URL 로드"""
        webhook_url_str = os.getenv('DISCORD_WEBHOOK_URL', '{}')
        try:
            urls = json.loads(webhook_url_str)
            return urls
        except json.JSONDecodeError:
            logger.error("Failed to parse DISCORD_WEBHOOK_URL from .env")
            return {}
    
    def send_message(self, message: str) -> bool:
        """
        단순 텍스트 메시지 전송
        
        Args:
            message: 보낼 메시지
            
        Returns:
            성공 여부
        """
        payload = {"content": message}
        return self._send_request(payload)
    
    def send_embed_message(
        self, 
        title: str, 
        description: str, 
        color: str = "BLUE",
        fields: Optional[List[Dict[str, any]]] = None
    ) -> bool:
        """
        Embed 메시지 전송
        
        Args:
            title: 임베드 제목
            description: 임베드 설명
            color: 색상 ("BLUE", "GREEN", "RED", etc.)
            fields: 추가 필드 리스트 [{"name": "...", "value": "...", "inline": True/False}, ...]
            
        Returns:
            성공 여부
        """
        _color = COLOR_MAP.get(color, COLOR_MAP["BLUE"])
        
        embed = {
            "title": title,
            "description": description,
            "color": _color
        }
        
        if fields:
            embed["fields"] = fields
        
        payload = {"embeds": [embed]}
        return self._send_request(payload)
    
    def send_multi_embed(
        self, 
        title: str, 
        fields: List[Dict[str, any]], 
        color: str = "BLUE",
        description: Optional[str] = None
    ) -> bool:
        """
        여러 필드를 포함한 Embed 메시지 전송
        
        Args:
            title: 임베드 제목
            fields: 필드 리스트 [{"name": "...", "value": "...", "inline": True/False}, ...]
            color: 색상
            description: 임베드 설명 (옵션)
            
        Returns:
            성공 여부
        """
        _color = COLOR_MAP.get(color, COLOR_MAP["BLUE"])
        
        embed = {
            "title": title,
            "fields": fields,
            "color": _color
        }
        
        if description:
            embed["description"] = description
        
        payload = {"embeds": [embed]}
        return self._send_request(payload)
    
    def send_image(self, file_path: str) -> bool:
        """
        이미지 파일 전송
        
        Args:
            file_path: 이미지 파일 경로
            
        Returns:
            성공 여부
        """
        try:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                response = requests.post(self.url, files=files)
                
            if response.status_code in (200, 204):
                logger.info(f"✅ Image sent successfully to {self.channel}")
                return True
            else:
                logger.error(f"❌ Image send failed: {response.status_code}")
                logger.error(response.text)
                return False
                
        except Exception as e:
            logger.error(f"❌ Error sending image: {e}")
            return False
    
    def _send_request(self, payload: Dict) -> bool:
        """
        Discord API로 요청 전송
        
        Args:
            payload: JSON 페이로드
            
        Returns:
            성공 여부
        """
        try:
            response = requests.post(self.url, json=payload)
            
            if response.status_code in (200, 204):
                logger.info(f"✅ Message sent successfully to {self.channel}")
                return True
            else:
                logger.error(f"❌ Message send failed: {response.status_code}")
                logger.error(response.text)
                return False
                
        except Exception as e:
            logger.error(f"❌ Error sending message: {e}")
            return False


class DiscordBot:
    """Discord Bot 클라이언트 (Bot Token 사용)"""
    
    def __init__(self, channel: str = "private"):
        """
        Args:
            channel: "private" 또는 "public"
        """
        self.token = self._load_bot_token()
        self.channel_id = self._load_channel_ids().get(channel)
        
        if not self.channel_id:
            raise ValueError(f"Invalid channel: {channel}")
        
        self.channel = channel
        self.base_url = "https://discord.com/api/v10"
        
    @staticmethod
    def _load_bot_token() -> str:
        """환경 변수에서 Discord Bot Token 로드"""
        token = os.getenv('DISCORD_BOT_TOKEN', '')
        if not token:
            logger.error("DISCORD_BOT_TOKEN not found in .env")
        return token
    
    @staticmethod
    def _load_channel_ids() -> Dict[str, str]:
        """환경 변수에서 Discord Channel ID 로드"""
        channel_id_str = os.getenv('DISCORD_CHANNEL_ID', '{}')
        try:
            ids = json.loads(channel_id_str)
            return ids
        except json.JSONDecodeError:
            logger.error("Failed to parse DISCORD_CHANNEL_ID from .env")
            return {}
    
    def send_message(self, message: str) -> bool:
        """
        단순 텍스트 메시지 전송
        
        Args:
            message: 보낼 메시지
            
        Returns:
            성공 여부
        """
        url = f"{self.base_url}/channels/{self.channel_id}/messages"
        headers = {
            "Authorization": f"Bot {self.token}",
            "Content-Type": "application/json"
        }
        data = {
            "content": message
        }
        
        try:
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                logger.info(f"✅ Bot message sent successfully to {self.channel}")
                return True
            else:
                logger.error(f"❌ Bot message send failed: {response.status_code}")
                logger.error(response.json())
                return False
                
        except Exception as e:
            logger.error(f"❌ Error sending bot message: {e}")
            return False
    
    def send_embed_message(
        self, 
        title: str, 
        description: str, 
        color: str = "BLUE",
        fields: Optional[List[Dict[str, any]]] = None
    ) -> bool:
        """
        Embed 메시지 전송
        
        Args:
            title: 임베드 제목
            description: 임베드 설명
            color: 색상 ("BLUE", "GREEN", "RED", etc.)
            fields: 추가 필드 리스트
            
        Returns:
            성공 여부
        """
        url = f"{self.base_url}/channels/{self.channel_id}/messages"
        headers = {
            "Authorization": f"Bot {self.token}",
            "Content-Type": "application/json"
        }
        
        _color = COLOR_MAP.get(color, COLOR_MAP["BLUE"])
        
        embed = {
            "title": title,
            "description": description,
            "color": _color
        }
        
        if fields:
            embed["fields"] = fields
        
        data = {
            "embeds": [embed]
        }
        
        try:
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                logger.info(f"✅ Bot embed message sent successfully to {self.channel}")
                return True
            else:
                logger.error(f"❌ Bot embed message send failed: {response.status_code}")
                logger.error(response.json())
                return False
                
        except Exception as e:
            logger.error(f"❌ Error sending bot embed message: {e}")
            return False
    
    def send_multi_embed(
        self, 
        title: str, 
        fields: List[Dict[str, any]], 
        color: str = "BLUE",
        description: Optional[str] = None
    ) -> bool:
        """
        여러 필드를 포함한 Embed 메시지 전송
        
        Args:
            title: 임베드 제목
            fields: 필드 리스트
            color: 색상
            description: 임베드 설명 (옵션)
            
        Returns:
            성공 여부
        """
        url = f"{self.base_url}/channels/{self.channel_id}/messages"
        headers = {
            "Authorization": f"Bot {self.token}",
            "Content-Type": "application/json"
        }
        
        _color = COLOR_MAP.get(color, COLOR_MAP["BLUE"])
        
        embed = {
            "title": title,
            "fields": fields,
            "color": _color
        }
        
        if description:
            embed["description"] = description
        
        data = {
            "embeds": [embed]
        }
        
        try:
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                logger.info(f"✅ Bot multi-embed message sent successfully to {self.channel}")
                return True
            else:
                logger.error(f"❌ Bot multi-embed message send failed: {response.status_code}")
                logger.error(response.json())
                return False
                
        except Exception as e:
            logger.error(f"❌ Error sending bot multi-embed message: {e}")
            return False
