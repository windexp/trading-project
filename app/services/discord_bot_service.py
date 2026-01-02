"""
Discord Bot Service
주식 조회 및 AI 대화 기능을 제공하는 Discord Bot
"""
import os
import json
import discord
from discord import app_commands
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict
import logging

from google import genai

from app.core.database import SessionLocal
from app.services.broker.utils import get_broker

logger = logging.getLogger(__name__)

# Discord 색상 매핑
COLOR_MAP = {
    "BLUE": 0x3498DB, "GREEN": 0x57F287, "YELLOW": 0xFF9632, "RED": 0xED4245,
    "DBLUE": 0x5865F2, "DGREEN": 0x57F287, "DYELLOW": 0xFF9632, "DRED": 0xEB459E,
    "PURPLE": 0x9B59B6, "SKYBLUE": 0x1ABC9C, "GREY": 0x95A5A6, "ORANGE": 0xE67E22
}

AVAILABLE_MODELS = {
    "gemini-2.0-flash-exp": "Free (default)",
    "gemini-1.5-flash": "Free",
    "gemini-1.5-pro": "Free (limited)",
}

SYSTEM_INSTRUCTION = "You are a helpful AI assistant specialized in stock trading and investment. Provide professional advice on stock markets, investment strategies, and financial information."


class ConversationManager:
    """AI 대화 관리"""
    
    def __init__(self, max_messages=20):str]] = defaultdict(list)
        self.user_settings = defaultdict(lambda: {"model": "gemini-2.0-flash-exp"})

    def add_message(self, user_id: int, message: str):
        """사용자 메시지 추가"""
        self.conversations[user_id].append(message)
        # 최대 메시지 수 유지 (대화 컨텍스트)
        while len(self.conversations[user_id]) > self.max_messages:
            self.conversations[user_id].pop(0)

    def get_conversation_history(self, user_id: int) -> str:
        """대화 히스토리를 문자열로 반환"""
        messages = self.conversations[user_id]
        if not messages:
            return ""
        return "\n\n".join(messages)
    def get_messages(self, user_id: int) -> List[Dict]:
        return self.conversations[user_id]

    def reset_conversation(self, user_id: int):
        self.conversations[user_id].clear()


class TradingBot(discord.Client):
    """Trading Discord Bot"""
    
    def __init__(self, bot_token: str, gemini_key: Optional[str] = None, 
                 default_account: Optional[str] = None,
                 allowed_channel_ids: Optional[List[int]] = None):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        
        self.bot_token = bot_token
        self.tree = app_commands.CommandTree(self)
        self.default_account = default_account
        self# API 키를 환경 변수에 설정 (genai.Client()가 자동으로 읽음)
            os.environ['GEMINI_API_KEY'] = gemini_key
            self.gemini_client = genai.Client(nnel_ids or []
        
        # Gemini 설정 (옵션)
        self.ai_enabled = bool(gemini_key)
        if self.ai_enabled:
            genai.configure(api_key=gemini_key)
            self.conversation_manager = ConversationManager()
        
        logger.info(f"Trading Bot initialized (AI: {'enabled' if self.ai_enabled else 'disabled'})")

    async def setup_hook(self):
        """봇 초기 설정"""
        self.setup_commands()
        await self.tree.sync()
        logger.info("Bot commands synced")

    def _check_permissions(self, channel_id: int) -> bool:
        """채널 권한 확인"""
        if self.allowed_channel_ids and channel_id not in self.allowed_channel_ids:
            return False
        return True

    def setup_commands(self):
        """Bot 명령어 설정"""
        
        # Price 명령어
        @self.tree.command(
            name="price",
            description="Get current price for a ticker"
        )
        async def price_callback(interaction: discord.Interaction, ticker: str):
            if not self._check_permissions(interaction.channel_id):
                await interaction.response.send_message("❌ This command is not available in this channel.", ephemeral=True)
                return
            
            await interaction.response.defer()
            
            try:
                ticker = ticker.upper()
                db = SessionLocal()
                
                try:
                    broker = get_broker(self.default_account, db)
                    if not broker:
                        await interaction.followup.send(f"❌ Failed to initialize broker")
                        return
                    
                    # 현재 가격 조회
                    raw_price = broker.get_price(ticker)
                    price_info = broker.parse_price_response(raw_price)
                    
                    if price_info['price'] is None:
                        await interaction.followup.send(f"❌ Failed to get price for {ticker}")
                        return
                    
                    current_price = price_info['price']
                    change_pct = price_info.get('change_pct', 0)
                    
                    # 색상 결정
                    if change_pct > 0:
                        color = COLOR_MAP["RED"]
                        arrow = "📈"
                    elif change_pct < 0:
                        color = COLOR_MAP["BLUE"]
                        arrow = "📉"
                    else:
                        color = COLOR_MAP["GREY"]
                        arrow = "➡️"
                    
                    embed = discord.Embed(
                        title=f"{arrow} {ticker} Price",
                        color=color,
                        timestamp=datetime.now()
                    )
                    embed.add_field(
                        name="Current Price", 
                        value=f"`${current_price:.2f}`", 
                        inline=True
                    )
                    embed.add_field(
                        name="Change", 
                        value=f"`{change_pct:+.2f}%`", 
                        inline=True
                    )
                    
                    await interaction.followup.send(embed=embed)
                    
                finally:
                    db.close()
                    
            except Exception as e:
                logger.error(f"Error in price command: {e}")
                await interaction.followup.send(f"❌ Error: {str(e)}")

        # Balance 명령어
        @self.tree.command(
            name="balance",
            description="Get account balance"
        )
        async def balance_callback(interaction: discord.Interaction):
            if not self._check_permissions(interaction.channel_id):
                await interaction.response.send_message("❌ This command is not available in this channel.", ephemeral=True)
                return
            
            await interaction.response.defer()
            
            try:
                db = SessionLocal()
                
                try:
                    broker = get_broker(self.default_account, db)
                    if not broker:
                        await interaction.followup.send(f"❌ Failed to initialize broker")
                        return
                    
                    # 잔고 조회
                    raw_balance = broker.get_balance()
                    balance_info = broker.parse_balance_response(raw_balance)
                    
                    embed = discord.Embed(
                        title="💰 Account Balance",
                        color=COLOR_MAP["GREEN"],
                        timestamp=datetime.now()
                    )
                    
                    embed.add_field(
                        name="Total Assets",
                        value=f"`${balance_info.get('total_assets', 0):,.2f}`",
                        inline=True
                    )
                    embed.add_field(
                        name="Cash",
                        value=f"`${balance_info.get('cash', 0):,.2f}`",
                        inline=True
                    )
                    embed.add_field(
                        name="Securities",
                        value=f"`${balance_info.get('securities', 0):,.2f}`",
                        inline=True
                    )
                    
                    await interaction.followup.send(embed=embed)
                    
                finally:
                    db.close()
                    
            except Exception as e:
                logger.error(f"Error in balance command: {e}")
                await interaction.followup.send(f"❌ Error: {str(e)}")

        # Holdings 명령어
        @self.tree.command(
            name="holdings",
            description="Get current holdings"
        )
        async def holdings_callback(interaction: discord.Interaction):
            if not self._check_permissions(interaction.channel_id):
                await interaction.response.send_message("❌ This command is not available in this channel.", ephemeral=True)
                return
            
            await interaction.response.defer()
            
            try:
                db = SessionLocal()
                
                try:
                    broker = get_broker(self.default_account, db)
                    if not broker:
                        await interaction.followup.send(f"❌ Failed to initialize broker")
                        return
                    
                    # 보유 종목 조회
                    raw_holdings = broker.get_balance()
                    holdings_info = broker.parse_balance_response(raw_holdings)
                    holdings = holdings_info.get('holdings', [])
                    
                    if not holdings:
                        await interaction.followup.send("📭 No holdings found")
                        return
                    
                    embed = discord.Embed(
                        title="📊 Current Holdings",
                        color=COLOR_MAP["BLUE"],
                        timestamp=datetime.now()
                    )
                    
                    for holding in holdings[:10]:  # 최대 10개
                        ticker = holding.get('ticker', 'N/A')
                        qty = holding.get('quantity', 0)
                        avg_price = holding.get('avg_price', 0)
                        current_value = holding.get('current_value', 0)
                        pnl = holding.get('pnl', 0)
                        pnl_pct = holding.get('pnl_pct', 0)
                        
                        value_text = (
                            f"Qty: `{qty}`\n"
                            f"Avg: `${avg_price:.2f}`\n"
                            f"Value: `${current_value:.2f}`\n"
                            f"P&L: `${pnl:+.2f} ({pnl_pct:+.2f}%)`"
                        )
                        
                        embed.add_field(
                            name=f"{ticker}",
                            value=value_text,
                            inline=True
                        )
                    
                    await interaction.followup.send(embed=embed)
                    
                finally:
                    db.close()
                    
            except Exception as e:
                logger.error(f"Error in holdings command: {e}")
                await interaction.followup.send(f"❌ Error: {str(e)}")

        # AI 관련 명령어 (AI가 활성화된 경우만)
        if self.ai_enabled:
            @self.tree.command(
                name="reset",
                description="Reset conversation history"
            )
            async def reset_callback(interaction: discord.Interaction):
                self.conversation_manager.reset_conversation(interaction.user.id)
                await interaction.response.send_message("✅ Conversation history reset")

            @self.tree.command(
                name="model",
                description="Change AI model"
            )
            async def model_callback(interaction: discord.Interaction, model: str):
                if model not in AVAILABLE_MODELS:
                    available = "\n".join([f"• {m}" for m in AVAILABLE_MODELS.keys()])
                    await interaction.response.send_message(
                        f"❌ Invalid model. Available models:\n{available}",
                        ephemeral=True
                    )
                    return
                
                self.conversation_manager.user_settings[interaction.user.id]["model"] = model
                await interaction.response.send_message(f"✅ Model changed to {model}")

        # Help 명령어
        @self.tree.command(
            name="help",
            description="Show available commands"
        )
        async def help_callback(interaction: discord.Interaction):
            help_embed = discord.Embed(
                title="🤖 Trading Bot Commands",
                description="Available commands for trading bot",
                color=COLOR_MAP["BLUE"]
            )
            
            help_embed.add_field(
                name="📊 Market Data",
                value=(
                    "`/price <ticker>`: Get current price\n"
                    "`/balance`: Get account balance\n"
                    "`/holdings`: Get current holdings"
                ),
                inline=False
            )
            
            if self.ai_enabled:
                help_embed.add_field(
                    name="🤖 AI Chat",
                    value=(
                        "Send a message to chat with AI\n"
                        "`/model <model>`: Change AI model\n"
                        "`/reset`: Reset conversation history"
                    ),
                    inline=False
                )
                
                help_embed.add_field(
                    name="Available Models",
                    value="\n".join([f"• {model}: {desc}" for model, desc in AVAILABLE_MODELS.items()]),
                    inline=False
                )
            
            await interaction.response.send_message(embed=help_embed)

    async def on_ready(self):
        """Bot이 준비되었을 때"""
        logger.info(f'Trading Bot is ready as {self.user}')
        try:
            self.tree.clear_commands(guild=None)
            await self.tree.sync()
            logger.info("Commands cleared and synced")
            
            self.setup_commands()
            synced = await self.tree.sync()
            logger.info(f"✅ {len(synced)} commands synced")
        except Exception as e:
            logger.error(f"❌ Error syncing commands: {e}")

    async def call_ai_api(self, user_id: int, message: str) -> str:
        """Gemini API 호출"""
        if not self.ai_enabled:
            return "AI is not enabled for this bot."
        # 대화 히스토리 가져오기
            conversation_history = self.conversation_manager.get_conversation_history(user_id)
            
            # 현재 메시지를 히스토리에 추가
            self.conversation_manager.add_message(user_id, f"User: {message}")
            
            # 프롬프트 구성 (시스템 지시사항 + 대화 히스토리 + 현재 메시지)
            if conversation_history:
                full_prompt = f"{SYSTEM_INSTRUCTION}\n\nPrevious conversation:\n{conversation_history}\n\nUser: {message}\n\nAssistant:"
            else:
                full_prompt = f"{SYSTEM_INSTRUCTION}\n\nUser: {message}\n\nAssistant:"
            
            model_name = self.conversation_manager.user_settings[user_id]["model"]
            
            # Gemini API 호출
            response = self.gemini_client.models.generate_content(
                model=model_name,
                contents=full_prompt
            )
            
            response_text = response.text
            
            # 응답을 히스토리에 추가
            self.conversation_manager.add_message(user_id, f"Assistant: {response_text}")
            
            return f"[{model_name}] {response_text}"
            
            self.conversation_manager.add_message(user_id, response.text, "model")
            return response_text
        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}")
            return f"❌ AI API error: {str(e)}"

    async def on_message(self, message):
        """메시지 수신 시"""
        # 봇 자신의 메시지 무시
        if message.author == self.user:
            return
        
        # 채널 권한 확인
        if not self._check_permissions(message.channel.id):
            return
        
        # 명령어는 무시 (slash commands)
        if message.content.startswith('/'):
            return
        
        # AI 대화
        if self.ai_enabled:
            async with message.channel.typing():
                response = await self.call_ai_api(message.author.id, message.content)
                
                # 긴 메시지는 분할 전송
                if len(response) > 2000:
                    for i in range(0, len(response), 2000):
                        await message.reply(response[i:i + 2000])
                else:
                    await message.reply(response)

    def start_bot(self):
        """봇 시작"""
        try:
            self.run(self.bot_token)
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            raise


def create_bot_from_env() -> Optional[TradingBot]:
    """환경 변수에서 봇 설정을 읽어 생성"""
    bot_token = os.getenv('DISCORD_BOT_TOKEN')
    if not bot_token:
        logger.warning("DISCORD_BOT_TOKEN not found in environment")
        return None
    
    gemini_key = os.getenv('GEMINI_API_KEY')
    default_account = os.getenv('DISCORD_BOT_DEFAULT_ACCOUNT')
    
    # 허용된 채널 ID (DISCORD_CHANNEL_ID에서 읽기)
    channel_id_str = os.getenv('DISCORD_CHANNEL_ID', '{}')
    try:
        channel_ids = json.loads(channel_id_str)
        allowed_channel_ids = [int(cid) for cid in channel_ids.values()]
    except (json.JSONDecodeError, ValueError):
        allowed_channel_ids = []
    
    return TradingBot(
        bot_token=bot_token,
        gemini_key=gemini_key,
        default_account=default_account,
        allowed_channel_ids=allowed_channel_ids
    )


if __name__ == "__main__":
    # 독립 실행
    from dotenv import load_dotenv
    load_dotenv()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    bot = create_bot_from_env()
    if bot:
        logger.info("Starting Discord bot...")
        bot.start_bot()
    else:
        logger.error("Failed to create bot from environment variables")
