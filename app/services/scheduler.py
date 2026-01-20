"""
스케줄러 서비스
- 모든 활성화된 전략에 대해 일일 루틴 실행
- APScheduler를 사용하여 매일 오후 6시에 실행
- YouTube 채널 모니터링 (1시간마다)
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
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
        # YouTube 분석용 별도 스레드 풀 (최대 2개 동시 실행)
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="youtube_worker")
        
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
        
        # 1시간마다 YouTube 새 영상 체크 및 분석
        self.scheduler.add_job(
            func=self.check_youtube_new_videos,
            trigger=IntervalTrigger(hours=1),
            id='youtube_video_check',
            name='Check and analyze new YouTube videos',
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("✅ Strategy scheduler started")
        logger.info("   - Daily routines: 6:30 PM KST (Mon-Fri)")
        logger.info("   - Daily summaries: 7:00 AM KST (Tue-Sat)")
        logger.info("   - YouTube check: Every 1 hour")
        
        # 서버 시작 시 YouTube 체크 한 번 실행
        self.check_youtube_new_videos()
        
    def stop(self):
        """스케줄러 중지"""
        if self.scheduler.running:
            self.scheduler.shutdown()
        # 실행 중인 YouTube 작업이 완료될 때까지 대기
        self.executor.shutdown(wait=True, cancel_futures=False)
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
                strategy_name = strategy.name  # 에러 발생 전에 이름 저장
                try:
                    self._execute_strategy_routine(strategy, db)
                except Exception as e:
                    db.rollback()  # 트랜잭션 롤백 후 새 트랜잭션 시작
                    logger.error(f"❌ Error executing strategy {strategy_name}: {e}")
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
        strategy_name = strategy.name  # 에러 발생 전에 이름 저장
        strategy_code = strategy.strategy_code
        account_name = strategy.account_name
        
        logger.info("-" * 80)
        logger.info(f"▶️  Executing strategy: {strategy_name} ({strategy_code})")
        logger.info(f"    Account: {account_name}")
        logger.info("-" * 80)
        
        # 브로커 초기화
        broker = get_broker(account_name, db)
        if not broker:
            logger.error(f"❌ Failed to initialize broker for account {account_name}")
            return
        
        # 전략 타입에 따라 실행
        try:
            if strategy_code == "InfBuy":
                strategy_instance = InfBuyStrategy(strategy, broker, db)
            elif strategy_code == "VR":
                strategy_instance = VRStrategy(strategy, broker, db)
            else:
                logger.error(f"❌ Unknown strategy code: {strategy_code}")
                return
            
            # Daily routine 실행
            strategy_instance.execute_daily_routine()
            logger.info(f"✅ Strategy {strategy_name} completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Error executing strategy {strategy_name}: {e}")
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

    def check_youtube_new_videos(self):
        """YouTube 새 영상을 체크하고 분석합니다 (비동기 실행)."""
        # 별도 스레드에서 실행하여 메인 스케줄러를 블로킹하지 않음
        self.executor.submit(self._check_youtube_new_videos_worker)
        logger.info("🎬 YouTube video check started in background thread")
    
    def _check_youtube_new_videos_worker(self):
        """YouTube 체크 실제 작업 (별도 스레드에서 실행)."""
        logger.info("=" * 80)
        logger.info(f"🎬 YouTube Video Check - {datetime.now(pytz.timezone('Asia/Seoul'))}")
        logger.info("=" * 80)
        
        try:
            from app.services.market_analysis.youtube_summary import get_youtube_summary_service
            
            service = get_youtube_summary_service()
            
            # 1주일 이상 된 요약 파일 정리
            deleted_count = service.cleanup_old_summaries(days=7)
            if deleted_count > 0:
                logger.info(f"🗑️  Cleaned up {deleted_count} old summary file(s)")
            
            # 등록된 채널 수 확인
            channel_count = len(service.channel_ids)
            if channel_count == 0:
                logger.info("No YouTube channels registered. Skipping.")
                return
            
            logger.info(f"Checking {channel_count} channel(s) for new videos...")
            
            # 새 영상 확인
            unanalyzed = service.get_unanalyzed_videos()
            
            if not unanalyzed:
                logger.info("No new videos to analyze.")
                return
            
            logger.info(f"Found {len(unanalyzed)} new video(s) to analyze")
            
            # 새 영상 분석 (async 함수이므로 asyncio.run 사용)
            import asyncio
            results = asyncio.run(service.check_and_analyze_new_videos())
            
            success_count = sum(1 for r in results if r.get('summary') and not r.get('error'))
            error_count = len(results) - success_count
            
            # 성공적으로 분석된 영상은 Discord에 알림
            if success_count > 0:
                self._send_youtube_notification(results)
            
            logger.info("=" * 80)
            logger.info(f"✅ YouTube Video Check Completed")
            logger.info(f"   - Analyzed: {len(results)} video(s)")
            logger.info(f"   - Success: {success_count}, Errors: {error_count}")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"❌ Error in YouTube check worker: {e}")
            logger.exception(e)

    def run_youtube_check_now(self):
        """테스트용: YouTube 체크 즉시 실행"""
        logger.info("⚡ Manual YouTube check triggered")
        self.check_youtube_new_videos()

    def _send_youtube_notification(self, results: list):
        """새로 분석된 YouTube 영상을 Discord에 알림"""
        try:
            # 성공한 결과만 필터링
            success_results = [r for r in results if r.get('summary') and not r.get('error')]
            
            if not success_results:
                return
            
            discord = DiscordWebhook(channel="private")
            
            for result in success_results:
                title = result.get('title', 'Unknown Title')
                video_id = result.get('video_id', '')
                channel_title = result.get('channel_title', '')
                
                # 영상 링크 생성
                video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
                
                message = f"🎬 **새 영상 분석 완료**\n"
                if channel_title:
                    message += f"📺 {channel_title}\n"
                message += f"📌 [{title}]({video_url})"
                
                discord.send_message(message)
                logger.info(f"📤 Discord notification sent: {title}")
                
        except Exception as e:
            logger.error(f"❌ Error sending YouTube notification: {e}")


# 글로벌 스케줄러 인스턴스
strategy_scheduler = StrategyScheduler()
