import math
import logging
logger = logging.getLogger(__name__)
from datetime import datetime, timedelta
import time
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import desc
from app.models.schema import Strategy, StrategySnapshot, Order
from app.models.enums import OrderStatus, OrderType, RequestOutcome, SnapshotStatus
from app.services.broker.base import BaseBroker
from app.services.strategies.base import BaseStrategy
from enum import Enum
from copy import deepcopy
import pytz

class VRStrategy(BaseStrategy):
    """
    Value Rebalancing (VR) Strategy Implementation (V2).
    Uses new Strategy/Snapshot/Order schema.
    """
    
    def __init__(self, strategy: Strategy, broker: BaseBroker, db: Session):
        super().__init__(strategy, broker, db)
        
        # Config
        self.ticker = self.params.get('ticker')
        self.initial_investment = float(self.params.get('initial_investment', 10000))
        self.periodic_investment = float(self.params.get('periodic_investment', 400))
        self.buy_limit_rate = float(self.params.get('buy_limit_rate', 1))/100   # e.g., 1% -> 0.01
        self.sell_limit_rate = float(self.params.get('sell_limit_rate', 1))/100   # e.g., 1% -> 0.01
        self.g_factor = float(self.params.get('g_factor', 13))
        self.u_band = float(self.params.get('u_band', 15))/100 # e.g., 15% -> 0.15
        self.l_band = float(self.params.get('l_band', 15))/100 # e.g., 15% -> 0.15
        self.is_advanced = self.params.get('is_advanced', False)
    
    def execute_daily_routine(self):
        logger.info(f"🚀 Starting VR Routine for {self.strategy.name} ({self.ticker})")
        #0. Get Current Price
        try:
            raw_price = self.broker.get_price(self.ticker)
            price_info = self.broker.parse_price_response(raw_price)
            if price_info['price'] is None:
                logger.error(f"❌ Failed to get price for {self.ticker}. Response: {price_info}")
                raise ValueError(f"Failed to get current price. Response: {price_info}")
            current_price = price_info['price']
            logger.info(f"  ✓ Current Price: {current_price}")
        except Exception as e:
            logger.error(f"❌ [Error] Failed to get current price: {e}")
            raise
        # 1. Get Last Snapshot
        last_snapshot = self._get_last_snapshot()
        
        # 2. Handle no previous snapshot
        if not last_snapshot:
            logger.info("No previous snapshot found. Initializing new strategy.")
            initial_snapshot = self._create_initial_snapshot()
            self.db.add(initial_snapshot)
            self.db.commit()            
            self.db.refresh(initial_snapshot)
            last_snapshot = initial_snapshot
        
        else:
            logger.info(f"Found previous snapshot (Cycle {last_snapshot.cycle}, Created: {last_snapshot.created_at})")

        # now last_snapshot is guaranteed to be not None
        # Firstly check failed 
        if last_snapshot.status == SnapshotStatus.FAILED:
            logger.info("❌ Last snapshot failed. Manual intervention may be needed.")
            return
        # Sync last snapshot orders
        all_finalized = self._sync_snapshot_orders(last_snapshot)
        self.db.refresh(last_snapshot)
        # check new snapshot creation condition

        kst = pytz.timezone('Asia/Seoul')
        now_kst = datetime.now(kst)
        snapshot_date = last_snapshot.created_at.replace(tzinfo=pytz.UTC).astimezone(kst)
        days_passed = (now_kst.date() - snapshot_date.date()).days

        if days_passed >= 14 and all_finalized:
            logger.info(f"✅ Days passed: {days_passed}. Creating new snapshot.")
            last_snapshot.status = SnapshotStatus.COMPLETED

            # Calculate next state
            new_state = self._calculate_next_state(last_snapshot, current_price)
            cycle = last_snapshot.cycle + 1
            new_snapshot = StrategySnapshot(
            strategy_id=self.strategy.id,
            status=SnapshotStatus.PENDING,
            cycle=cycle,
            progress=new_state
            )
            logger.info(f"📸 Created New Snapshot (ID: {new_snapshot.id}, Status: PENDING)")
            self.db.add(new_snapshot)
            self.db.commit()
            self.db.refresh(new_snapshot)
            last_snapshot = new_snapshot  # Update reference for Step 3
            # Continue routine on the newly created snapshot
            

        # Place orders for new or continued snapshot        
        if last_snapshot.status in [SnapshotStatus.PENDING, SnapshotStatus.IN_PROGRESS]:            
            
            order_result = self._place_orders(last_snapshot, current_price)
            success = order_result.get('success', False) 
            if success:
                logger.info("✅ New orders placed. Updating snapshot status to IN_PROGRESS.")
                last_snapshot.status = SnapshotStatus.IN_PROGRESS
                kst = pytz.timezone('Asia/Seoul')
                last_snapshot.executed_at = datetime.now(tz=pytz.UTC).astimezone(kst)
                logger.info(f"  📅 executed_at set to: {last_snapshot.executed_at}")
            else:            
                if order_result.get('is_holiday', False):
                    logger.info(f"  📅 Market closed. Keeping snapshot as PENDING.")
                else:                           
                    last_snapshot.status = SnapshotStatus.FAILED
                    logger.error(f"❌ No orders were placed successfully. executed_at cleared.")
            last_snapshot.progress['error_msg'] = order_result.get('error_msg', 'Unknown error during order placement')            
            flag_modified(last_snapshot, 'progress')
            self.db.commit()
            logger.info(f"  💾 Snapshot committed. executed_at: {last_snapshot.executed_at}")
        logger.info("✅ VR Routine Completed.")
   

    def _create_initial_snapshot(self) -> StrategySnapshot:
        initial_state = {
            "total_investment": self.initial_investment,
            "v": self.initial_investment,
            "qty": 0,
            "pool": self.initial_investment,
            "avg_price": 0,
            "equity": self.initial_investment,
            "cycle_profit": 0
        }
        cycle = 1
        initial_snapshot = StrategySnapshot(
            strategy_id=self.strategy.id,
            status="PENDING",
            cycle=cycle,
            progress=initial_state
        )
        logger.info(f"📸 Created New Snapshot (ID: {initial_snapshot.id}, Status: PENDING)")
        self.db.add(initial_snapshot)
        self.db.commit()
        return initial_snapshot
    def _snapshot_trade_results(self, snapshot: StrategySnapshot) -> Dict[str, Any]:
        """Update snapshot with trade results from its orders."""
        
        orders = self.db.query(Order).filter(Order.snapshot_id == snapshot.id).all()
        # Update state based on filled orders
        buy_sum = {"qty": 0, "value": 0}
        sell_sum = {"qty": 0, "value": 0}

        for order in orders:
            if order.order_status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]:
                qty = order.filled_qty
                filled_price = float(order.filled_price)
                if order.order_type == OrderType.BUY:
                    buy_sum["qty"] += qty
                    buy_sum["value"] += (filled_price * qty)
                else:
                    sell_sum["qty"] += qty
                    sell_sum["value"] += (filled_price * qty)
        snapshot.progress['cycle_trade'] = {"buy":buy_sum, "sell":sell_sum}
        self.db.commit()
        return {"buy": buy_sum, "sell": sell_sum}
        state['cycle_trade'] = {"buy": buy_sum, "sell": sell_sum}
        snapshot.progress = state
    def _calculate_next_state(self, last_snapshot: StrategySnapshot, current_price) -> Dict[str, Any]:
        """Calculate new state based on last snapshot and its filled orders."""
        last_state = deepcopy(last_snapshot.progress)
        # orders = self.db.query(Order).filter(Order.snapshot_id == last_snapshot.id).all()
        # Update state based on filled orders
        last_pool = last_state.get('pool', 0)
        # 1. Get trade results from last snapshot
        trade_results = self._snapshot_trade_results(last_snapshot)
        buy_sum = trade_results["buy"]
        sell_sum = trade_results["sell"]

        # 2. Update average price and quantity
        last_avg = last_state.get('avg_price', 0)
        last_qty = last_state.get('qty', 0)
        cycle_profit=sell_sum["value"] - (sell_sum["qty"] * last_avg)                    
        temp_qty = last_qty - sell_sum["qty"]
        temp_amount = temp_qty * last_avg
        temp_qty = temp_qty + buy_sum["qty"]
        temp_amount = temp_amount + buy_sum["value"]
        if temp_qty == 0:
            new_avg = 0
        else:
            new_avg = temp_amount / temp_qty
        # 3. Update quantity and pool
        new_qty = temp_qty
        temp_pool = last_pool - buy_sum["value"] + sell_sum["value"] 
        # 4. calculate new V
        if last_state.get('v'):
            r_inc = 1 + last_pool / last_state['v'] / self.g_factor
            r_inc_advanced = 0
            if self.is_advanced:
                r_inc_advanced = (new_qty * current_price / last_state['v'] - 1) / (2 * math.sqrt(self.g_factor))
                r_inc = r_inc + r_inc_advanced
        else:
            logger.info("❌ [Error] V is not defined in state.")
            raise ValueError("V is not defined in state.")
        new_v = last_state['v'] * r_inc + self.periodic_investment
        new_pool = temp_pool + self.periodic_investment
        equity = new_qty * current_price + new_pool
        logger.info(f"\n📊 _calculate_next_state called:")
        new_state = {}
        new_state['total_investment'] = last_state.get('total_investment', 0) + self.periodic_investment
        new_state['v'] = new_v  
        new_state['qty'] = new_qty
        new_state['pool'] = new_pool    
        new_state['avg_price'] = new_avg
        new_state['equity'] = equity
        new_state['cycle_profit'] = cycle_profit
        
        logger.info(f"  Calculated New State:")
        for key, value in new_state.items():    
            logger.info(f"    {key}: {value}")
        return new_state

    def _generate_orders(self, state: Dict[str, Any], current_price) -> List[Dict[str, Any]]:
        """Generate list of orders based on current state."""
        try:
            logger.info(f"\n📊 _generate_orders called with state: {state}")
            
            # 1. Get Current Price
            # current_price = float(self.broker.get_price(self.ticker))
            
            # 2. Extract State Variables
            trade_results = state.get('cycle_trade', {'buy': {}, 'sell': {}})
            cycle_pool = state.get('pool', 0)        # cash pool at the beginning of the cycle   
            
            # cycle_buy_amt = trade_results.get('buy', {}).get('value', 0)
            # cycle_sell_amt = trade_results.get('sell', {}).get('value', 0)
            cycle_buy_qty = trade_results.get('buy', {}).get('qty', 0)
            cycle_sell_qty = trade_results.get('sell', {}).get('qty', 0)
            current_qty = state.get('qty', 0) + cycle_buy_qty - cycle_sell_qty
            # current_pool = cycle_pool + cycle_sell_amt - cycle_buy_amt

            v = state.get('v', 0)
            u_band_value = (1+self.u_band) * v
            l_band_value = (1-self.l_band) * v
            buy_limit = self.buy_limit_rate * cycle_pool # max trade per day as rate of pool value
            sell_limit = self.sell_limit_rate * current_qty # max trade per day as rate of quantity                       
 
            # 3. Calculate orders
            # 3.1 Buy orders
            # The first buy order
            max_daily_orders = 5 # To prevent too many orders in one day (buy/sell separately)
            buy_qty=1
            
            temp_target_price = float( round(l_band_value/(current_qty+buy_qty ), 2) ) if current_qty+buy_qty >0 else 0
            target_price = min(current_price*1.2,temp_target_price)
            daily_buy_sum = target_price
            buy_orders = []
            # Buy orders until limit reached
            while daily_buy_sum <= buy_limit:
                buy_orders.append( {"side": "BUY", "price": target_price, "qty": 1, "order_type": "LOC"} )
                buy_qty += 1
                temp_target_price = float( round(l_band_value/(current_qty+buy_qty ), 2) )
                target_price = min(current_price*1.2,temp_target_price)
                daily_buy_sum += target_price
                
            # 3.2 Sell orders
            sell_qty=1
            target_price = float( round(u_band_value/(current_qty - sell_qty ), 2) ) if current_qty - sell_qty >0 else 0
            daily_sell_sum = 0
            sell_orders = []
            # Sell orders until limit reached
            while sell_qty <= sell_limit:
                sell_orders.append( {"side": "SELL", "price": target_price, "qty": 1, "order_type": "LOC"} )

            # merge and return
            if len(buy_orders) > max_daily_orders:
                merge_orders_unit= math.ceil( len(buy_orders) / max_daily_orders )
                merged_buy_orders = []
                for i in range(0, len(buy_orders), merge_orders_unit):
                    chunk = buy_orders[i:i+merge_orders_unit]
                    total_qty = sum(o['qty'] for o in chunk)
                    merged_buy_orders.append( {"side": "BUY", "price": chunk[0]['price'], "qty": total_qty, "order_type": "LOC"} )
                buy_orders = merged_buy_orders
            if len(sell_orders) > max_daily_orders:
                merge_orders_unit= math.ceil( len(sell_orders) / max_daily_orders )
                merged_sell_orders = []
                for i in range(0, len(sell_orders), merge_orders_unit):
                    chunk = sell_orders[i:i+merge_orders_unit]
                    total_qty = sum(o['qty'] for o in chunk)
                    merged_sell_orders.append( {"side": "SELL", "price": chunk[0]['price'], "qty": total_qty, "order_type": "LOC"} )
                sell_orders = merged_sell_orders
            orders = buy_orders + sell_orders
            if not buy_orders and not sell_orders:
                logger.info("  ⚠️  No orders generated based on current state and limits.")
            logger.info(f"  ✓ Generated {len(buy_orders)} buy orders and {len(sell_orders)} sell orders")
            return orders
            
        except Exception as e:
            logger.error(f"❌ [CRITICAL] _generate_orders failed: {e}")
            import traceback
            traceback.print_exc()
            raise
    def generate_daily_summary(self) -> Dict[str, Any]:
        """
        VR 전략의 일일 요약 생성
        - 최신 스냅샷 로드
        - 스냅샷 주문 동기화
        - 전날 주문과 현재 스냅샷 주문 Summary
        """
        try:
            # 최신 스냅샷 로드
            last_snapshot = self._get_last_snapshot()
            if not last_snapshot:
                return {
                    "success": False,
                    "error": "No snapshot found"
                }
            
            # 스냅샷 주문 동기화
            self._sync_snapshot_orders(last_snapshot)
            
            # 현재 스냅샷의 모든 주문 조회 (Snapshot Orders)
            snapshot_orders = self.db.query(Order).filter(Order.snapshot_id == last_snapshot.id).all()
            
            # 어제 생성된 주문만 필터링 (Last Orders)
            kst = pytz.timezone('Asia/Seoul')
            now_kst = datetime.now(kst)
            yesterday_start = (now_kst - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday_end = yesterday_start + timedelta(days=1)
            
            last_orders = [
                order for order in snapshot_orders 
                if order.ordered_at and yesterday_start <= order.ordered_at.replace(tzinfo=kst) < yesterday_end
            ]
            
            # Last Orders 집계 - Submitted & Filled
            last_buy_submitted = 0
            last_sell_submitted = 0
            last_buy_qty = 0
            last_buy_value = 0.0
            last_sell_qty = 0
            last_sell_value = 0.0
            
            for order in last_orders:
                if order.order_type == OrderType.BUY:
                    last_buy_submitted += 1
                    if order.order_status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]:
                        last_buy_qty += order.filled_qty
                        last_buy_value += float(order.filled_price * order.filled_qty)
                else:
                    last_sell_submitted += 1
                    if order.order_status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]:
                        last_sell_qty += order.filled_qty
                        last_sell_value += float(order.filled_price * order.filled_qty)
            
            # Snapshot Orders 집계 (현재 스냅샷의 모든 주문)
            snapshot_buy_qty = 0
            snapshot_buy_value = 0.0
            snapshot_sell_qty = 0
            snapshot_sell_value = 0.0
            
            for order in snapshot_orders:
                if order.order_status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]:
                    if order.order_type == OrderType.BUY:
                        snapshot_buy_qty += order.filled_qty
                        snapshot_buy_value += float(order.filled_price * order.filled_qty)
                    else:
                        snapshot_sell_qty += order.filled_qty
                        snapshot_sell_value += float(order.filled_price * order.filled_qty)
            
            # 평균 가격 계산
            last_buy_avg = last_buy_value / last_buy_qty if last_buy_qty > 0 else 0
            last_sell_avg = last_sell_value / last_sell_qty if last_sell_qty > 0 else 0
            snapshot_buy_avg = snapshot_buy_value / snapshot_buy_qty if snapshot_buy_qty > 0 else 0
            snapshot_sell_avg = snapshot_sell_value / snapshot_sell_qty if snapshot_sell_qty > 0 else 0
            
            # 현재 상태
            state = last_snapshot.progress
            
            return {
                "success": True,
                "strategy_name": self.strategy.name,
                "strategy_code": self.strategy.strategy_code,
                "ticker": self.ticker,
                "cycle": last_snapshot.cycle,
                "current_state": {
                    "qty": state.get('qty', 0),
                    "avg_price": state.get('avg_price', 0),
                    "pool": state.get('pool', 0),
                    "equity": state.get('equity', 0),
                    "v": state.get('v', 0),
                    "cycle_profit": state.get('cycle_profit', 0),
                },
                "last_orders": {
                    "snapshot_id": last_snapshot.id,
                    "total": len(last_orders),
                    "buy": {
                        "submitted": last_buy_submitted,
                        "filled_qty": last_buy_qty,
                        "filled_value": round(last_buy_value, 2),
                        "avg_price": round(last_buy_avg, 2),
                    },
                    "sell": {
                        "submitted": last_sell_submitted,
                        "filled_qty": last_sell_qty,
                        "filled_value": round(last_sell_value, 2),
                        "avg_price": round(last_sell_avg, 2),
                    }
                },
                "snapshot_orders": {
                    "snapshot_id": last_snapshot.id,
                    "total": len(snapshot_orders),
                    "buy": {
                        "filled_qty": snapshot_buy_qty,
                        "filled_value": round(snapshot_buy_value, 2),
                        "avg_price": round(snapshot_buy_avg, 2),
                    },
                    "sell": {
                        "filled_qty": snapshot_sell_qty,
                        "filled_value": round(snapshot_sell_value, 2),
                        "avg_price": round(snapshot_sell_avg, 2),
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error generating daily summary: {e}")
            return {
                "success": False,
                "error": str(e)
            }