"""
스케줄러 서비스
- 모든 활성화된 전략에 대해 일일 루틴 실행
- APScheduler를 사용하여 매일 오후 6시에 실행
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import logging
from typing import Optional
import pytz

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.schema import Strategy
from app.models.account import Account
from app.models.enums import StrategyStatus
from app.services.strategies.inf_buy_strategy import InfBuyStrategy
from app.services.strategies.vr_strategy import VRStrategy
from app.services.broker.utils import get_broker
from app.services.discord import DiscordWebhook

logger = logging.getLogger(__name__)

class StrategyScheduler:
    """전략 스케줄러"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Seoul'))
        
    def start(self):
        """스케줄러 시작"""
        # 매일 오후 6시 30분 실행 (Daily Routine)
        self.scheduler.add_job(
            func=self.execute_all_daily_routines,
            trigger=CronTrigger(hour=18, minute=30, day_of_week='mon-fri'),
            id='daily_strategy_routine',
            name='Execute all strategies daily routine',
            replace_existing=True
        )
        
        # 매일 오전 7시에 실행 (Daily Summary)
        self.scheduler.add_job(
            func=self.send_all_daily_summaries,
            trigger=CronTrigger(hour=7, minute=0, day_of_week='tue-sat'),
            id='daily_summary_notification',
            name='Send daily summaries to Discord',
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("✅ Strategy scheduler started")
        logger.info("   - Daily routines: 6:30 PM KST")
        logger.info("   - Daily summaries: 7:00 AM KST")
        
    def stop(self):
        """스케줄러 중지"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
    
    def execute_all_daily_routines(self):
        """모든 활성 전략의 daily routine 실행"""
        logger.info("=" * 80)
        logger.info(f"🕐 Starting Daily Strategy Routine - {datetime.now(pytz.timezone('Asia/Seoul'))}")
        logger.info("=" * 80)
        
        db: Session = SessionLocal()
        try:
            # ACTIVE 상태의 모든 전략 조회
            active_strategies = db.query(Strategy).filter(
                Strategy.status == StrategyStatus.ACTIVE
            ).all()
            
            if not active_strategies:
                logger.info("No active strategies found.")
                return
            
            logger.info(f"Found {len(active_strategies)} active strategy(s)")
            
            # 각 전략에 대해 daily routine 실행
            for strategy in active_strategies:
                try:
                    self._execute_strategy_routine(strategy, db)
                except Exception as e:
                    logger.error(f"❌ Error executing strategy {strategy.name}: {e}")
                    logger.exception(e)
                    # 하나의 전략이 실패해도 다른 전략은 계속 실행
                    continue
            
            logger.info("=" * 80)
            logger.info("✅ Daily Strategy Routine Completed")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"❌ Error in execute_all_daily_routines: {e}")
            logger.exception(e)
        finally:
            db.close()
    
    def _execute_strategy_routine(self, strategy: Strategy, db: Session):
        """개별 전략의 daily routine 실행"""
        logger.info("-" * 80)
        logger.info(f"▶️  Executing strategy: {strategy.name} ({strategy.strategy_code})")
        logger.info(f"    Account: {strategy.account_name}")
        logger.info("-" * 80)
        
        # 브로커 초기화
        broker = get_broker(strategy.account_name, db)
        if not broker:
            logger.error(f"❌ Failed to initialize broker for account {strategy.account_name}")
            return
        
        # 전략 타입에 따라 실행
        try:
            if strategy.strategy_code == "InfBuy":
                strategy_instance = InfBuyStrategy(strategy, broker, db)
            elif strategy.strategy_code == "VR":
                strategy_instance = VRStrategy(strategy, broker, db)
            else:
                logger.error(f"❌ Unknown strategy code: {strategy.strategy_code}")
                return
            
            # Daily routine 실행
            strategy_instance.execute_daily_routine()
            logger.info(f"✅ Strategy {strategy.name} completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Error executing strategy {strategy.name}: {e}")
            raise
    
    def execute_now(self):
        """테스트용: 즉시 실행"""
        logger.info("⚡ Manual execution triggered")
        self.execute_all_daily_routines()
    
    def send_all_daily_summaries(self, channel: str = "private"):
        """모든 활성 전략의 일일 요약을 Discord로 전송"""
        logger.info("=" * 80)
        logger.info(f"📊 Starting Daily Summary Notification - {datetime.now(pytz.timezone('Asia/Seoul'))}")
        logger.info("=" * 80)
        
        db: Session = SessionLocal()
        try:
            # Discord 웹훅 초기화
            discord = DiscordWebhook(channel=channel)
            
            # ACTIVE 상태의 모든 전략 조회
            active_strategies = db.query(Strategy).filter(
                Strategy.status == StrategyStatus.ACTIVE
            ).all()
            
            if not active_strategies:
                logger.info("No active strategies found.")
                return
            
            logger.info(f"Found {len(active_strategies)} active strategy(s)")
            
            # 각 전략에 대해 summary 생성 및 Discord 전송
            for strategy in active_strategies:
                try:
                    self._send_strategy_summary(strategy, discord, db)
                except Exception as e:
                    logger.error(f"❌ Error processing strategy {strategy.name}: {e}")
                    logger.exception(e)
                    continue
            
            logger.info("=" * 80)
            logger.info("✅ Daily Summary Notification Completed")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"❌ Error in send_all_daily_summaries: {e}")
            logger.exception(e)
        finally:
            db.close()
    
    def _send_strategy_summary(self, strategy: Strategy, discord: DiscordWebhook, db: Session):
        """개별 전략의 summary를 Discord로 전송"""
        logger.info("-" * 80)
        logger.info(f"▶️  Processing strategy: {strategy.name} ({strategy.strategy_code})")
        logger.info("-" * 80)
        
        # 브로커 초기화
        broker = get_broker(strategy.account_name, db)
        if not broker:
            logger.error(f"❌ Failed to initialize broker for account {strategy.account_name}")
            return
        
        # 전략 인스턴스 생성
        try:
            if strategy.strategy_code == "InfBuy":
                strategy_instance = InfBuyStrategy(strategy, broker, db)
            elif strategy.strategy_code == "VR":
                strategy_instance = VRStrategy(strategy, broker, db)
            else:
                logger.error(f"❌ Unknown strategy code: {strategy.strategy_code}")
                return
            
            # Summary 생성
            summary = strategy_instance.generate_daily_summary()
            
            if not summary.get("success"):
                logger.error(f"❌ Failed to generate summary: {summary.get('error')}")
                return
            
            # Discord 메시지 포맷팅
            fields = []
            
            # 기본 정보
            fields.append({
                "name": "📊 Strategy Info",
                "value": f"**Type:** {summary['strategy_code']}\n**Ticker:** {summary['ticker']}\n**Cycle:** {summary['cycle']}",
                "inline": False
            })
            
            # 전략별 상태 정보
            state = summary["current_state"]
            if strategy.strategy_code == "InfBuy":
                fields.append({
                    "name": "💰 Current State",
                    "value": (
                        f"**Quantity:** {state['quantity']}\n"
                        f"**Avg Price:** ${state['avg_price']:.2f}\n"
                        f"**Balance:** ${state['balance']:.2f}\n"
                        f"**Equity:** ${state['equity']:.2f}\n"
                        f"**Investment:** ${state['investment']:.2f}\n"
                        f"**T:** {state['current_t']}\n"
                        f"**Daily Profit:** ${state['daily_profit']:.2f}"
                    ),
                    "inline": False
                })
                
                # Last 주문 정보 (마지막 스냅샷)
                last_orders = summary.get("last_orders", {})
                if last_orders:
                    buy = last_orders.get("buy", {})
                    sell = last_orders.get("sell", {})
                    value_parts = []
                    
                    if buy.get("submitted", 0) > 0:
                        value_parts.append(
                            f"**Buy:** {buy['submitted']} submitted, "
                            f"{buy['filled_qty']} filled @ ${buy['avg_price']:.2f} = ${buy['filled_value']:.2f}"
                        )
                    
                    if sell.get("submitted", 0) > 0:
                        value_parts.append(
                            f"**Sell:** {sell['submitted']} submitted, "
                            f"{sell['filled_qty']} filled @ ${sell['avg_price']:.2f} = ${sell['filled_value']:.2f}"
                        )
                    
                    if value_parts:
                        fields.append({
                            "name": f"📅 Last Orders (마지막 스냅샷 - Total: {last_orders['total']})",
                            "value": "\n".join(value_parts),
                            "inline": False
                        })
                
                # Cycle 주문 정보 (전체 사이클)
                cycle_orders = summary["cycle_orders"]
                fields.append({
                    "name": f"📈 Cycle Orders (전체 사이클 - Total: {cycle_orders['total']})",
                    "value": (
                        f"**Buy:** {cycle_orders['buy']['filled_qty']} @ ${cycle_orders['buy']['avg_price']:.2f} = ${cycle_orders['buy']['filled_value']:.2f}\n"
                        f"**Sell:** {cycle_orders['sell']['filled_qty']} @ ${cycle_orders['sell']['avg_price']:.2f} = ${cycle_orders['sell']['filled_value']:.2f}"
                    ),
                    "inline": False
                })
                
            elif strategy.strategy_code == "VR":
                fields.append({
                    "name": "💰 Current State",
                    "value": (
                        f"**Quantity:** {state['qty']}\n"
                        f"**Avg Price:** ${state['avg_price']:.2f}\n"
                        f"**Pool:** ${state['pool']:.2f}\n"
                        f"**Equity:** ${state['equity']:.2f}\n"
                        f"**V:** ${state['v']:.2f}\n"
                        f"**Cycle Profit:** ${state['cycle_profit']:.2f}"
                    ),
                    "inline": False
                })
                
                # Last Orders (어제 주문)
                last_orders = summary.get("last_orders", {})
                if last_orders:
                    buy = last_orders.get("buy", {})
                    sell = last_orders.get("sell", {})
                    value_parts = []
                    
                    if buy.get("submitted", 0) > 0:
                        value_parts.append(
                            f"**Buy:** {buy['submitted']} submitted, "
                            f"{buy['filled_qty']} filled @ ${buy['avg_price']:.2f} = ${buy['filled_value']:.2f}"
                        )
                    
                    if sell.get("submitted", 0) > 0:
                        value_parts.append(
                            f"**Sell:** {sell['submitted']} submitted, "
                            f"{sell['filled_qty']} filled @ ${sell['avg_price']:.2f} = ${sell['filled_value']:.2f}"
                        )
                    
                    if value_parts:
                        fields.append({
                            "name": f"📅 Last Orders (어제 주문 - Total: {last_orders['total']})",
                            "value": "\n".join(value_parts),
                            "inline": False
                        })
                
                # Snapshot Orders (스냅샷의 모든 주문)
                snapshot_orders = summary.get("snapshot_orders", {})
                if snapshot_orders and snapshot_orders.get("total", 0) > 0:
                    fields.append({
                        "name": f"📈 Snapshot Orders (스냅샷 전체 - Total: {snapshot_orders['total']})",
                        "value": (
                            f"**Buy:** {snapshot_orders['buy']['filled_qty']} @ ${snapshot_orders['buy']['avg_price']:.2f} = ${snapshot_orders['buy']['filled_value']:.2f}\n"
                            f"**Sell:** {snapshot_orders['sell']['filled_qty']} @ ${snapshot_orders['sell']['avg_price']:.2f} = ${snapshot_orders['sell']['filled_value']:.2f}"
                        ),
                        "inline": False
                    })
            
            # Discord로 전송
            logger.info("=" * 80)
            logger.info(f"📤 Discord Message Preview for {strategy.name}")
            logger.info("=" * 80)
            logger.info(f"Title: 📊 Daily Summary: {strategy.name}")
            logger.info("-" * 80)
            for i, field in enumerate(fields, 1):
                logger.info(f"Field {i}: {field['name']}")
                logger.info(f"Value:\n{field['value']}")
                logger.info("-" * 80)
            logger.info("=" * 80)
            
            success = discord.send_multi_embed(
                title=f"📊 Daily Summary: {strategy.name}",
                fields=fields,
                color="BLUE"
            )
            
            if success:
                logger.info(f"✅ Summary sent to Discord for {strategy.name}")
            else:
                logger.error(f"❌ Failed to send summary to Discord for {strategy.name}")
                
        except Exception as e:
            logger.error(f"❌ Error creating strategy instance: {e}")
            raise


# 글로벌 스케줄러 인스턴스
strategy_scheduler = StrategyScheduler()
