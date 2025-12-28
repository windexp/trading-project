import math
from datetime import datetime, timedelta
import time
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import desc
from app.models.schema import Strategy, StrategySnapshot, Order
from app.models.enums import OrderStatus, OrderType, RequestOutcome
from app.services.broker.base import BaseBroker
from app.services.strategies.base import BaseStrategy
from enum import Enum
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
        self.daily_limit_rate = float(self.params.get('daily_limit_rate', 1))/100   # e.g., 1% -> 0.01
        self.g_factor = float(self.params.get('g_factor', 13))
        self.u_band = float(self.params.get('u_band', 15))/100 # e.g., 15% -> 0.15
        self.l_band = float(self.params.get('l_band', 15))/100 # e.g., 15% -> 0.15
    
    def execute_daily_routine(self):
        print(f"🚀 Starting VR Routine for {self.strategy.name} ({self.ticker})")
        
        # 1. Get Last Snapshot
        last_snapshot = self._get_last_snapshot()
        
        # 2. Handle existing snapshot based on status
        if last_snapshot:
            print(f"Found previous snapshot (Cycle {last_snapshot.cycle}, Created: {last_snapshot.created_at})")
            
            # Check if need to create new snapshot (2 weeks = 13+ days on Saturday)
            kst = pytz.timezone('Asia/Seoul')
            now_kst = datetime.now(kst)
            snapshot_date = last_snapshot.created_at.replace(tzinfo=pytz.UTC).astimezone(kst)
            days_passed = (now_kst.date() - snapshot_date.date()).days
            is_saturday = now_kst.weekday() == 5
            
            # If not Saturday or less than 13 days, continue with current snapshot
            if not (is_saturday and days_passed >= 13):
                print(f"  Continue with current snapshot (Days: {days_passed}, Is Saturday: {is_saturday})")
                
                # case pending, in_progress, failed
                if last_snapshot.status == "PENDING":
                    print(f"⏸️  Found PENDING snapshot. Retrying order placement...")
                    success = self._place_orders(last_snapshot)
                    if success:
                        print("✅ Orders successfully placed")
                    else:
                        print("⚠️  Still unable to place orders (market may be closed)")
                    return
                
                elif last_snapshot.status in ["IN_PROGRESS"]:
                    self._sync_last_orders(last_snapshot)
                    # Continue to place more orders
                    success = self._place_orders(last_snapshot)
                    if success:
                        print("✅ Additional orders placed")
                    return
                
                elif last_snapshot.status == "FAILED":
                    print("❌ Last snapshot failed. Manual intervention may be needed.")
                    return
                
                elif last_snapshot.status == "COMPLETED":
                    print("✅ Last snapshot completed, but not time for new snapshot yet.")
                    return
            else:
                print(f"  📅 Creating new snapshot (Days: {days_passed}, Is Saturday: {is_saturday})")
                # Sync last snapshot before creating new one
                self._sync_last_orders(last_snapshot)
                
                # Mark last snapshot as completed if all orders are finalized
                if last_snapshot.status == "IN_PROGRESS":
                    orders = self.db.query(Order).filter(Order.snapshot_id == last_snapshot.id).all()
                    all_finalized = all(order.order_status != OrderStatus.SUBMITTED for order in orders)
                    if all_finalized:
                        last_snapshot.status = "COMPLETED"
                        self.db.commit()
                
                # Calculate next state
                current_state = self._calculate_next_state(last_snapshot)
                cycle = last_snapshot.cycle + 1
        else:
            # First time
            print("No previous snapshot found. Initializing new strategy.")
            current_state = {
                "total_investment": self.investment,
                "current_v": self.investment,
                "current_quantity": 0,
                "current_pool": self.investment
            }
            cycle = 1

        # 3. Create New Snapshot
        new_snapshot = StrategySnapshot(
            strategy_id=self.strategy.id,
            status="PENDING",
            cycle=cycle,
            progress=current_state
        )
        print(f"📸 Created New Snapshot (ID: {new_snapshot.id}, Status: PENDING)")
        self.db.add(new_snapshot)
        self.db.commit()
        success = self._place_orders(new_snapshot)
        
        if success:
            print("✅ Routine Completed")
        else:
            print(f"⏸️  Routine Pending (will retry on next execution)")


    def _calculate_next_state(self, last_snapshot: StrategySnapshot) -> Dict[str, Any]:
        """Calculate new state based on last snapshot and its filled orders."""
        state = last_snapshot.progress.copy()
        orders = self.db.query(Order).filter(Order.snapshot_id == last_snapshot.id).all()
        # Update state based on filled orders
        for order in orders:
            if order.order_status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]:
                qty = order.filled_qty
                price = float(order.filled_price)
                
                if order.order_type == OrderType.BUY:
                    state['current_quantity'] = state.get('current_quantity', 0) + qty
                    state['current_pool'] = state.get('current_pool', 0) - (price * qty)
                else:
                    state['current_quantity'] = state.get('current_quantity', 0) - qty
                    state['current_pool'] = state.get('current_pool', 0) + (price * qty)
        r_inc_basic = 1 + self.daily_limit_rate                    
        state['current_v'] = state.get('current_v', 0) * r_inc_basic  # V remains unchanged until new price fetch
        print(f"  State Update - Qty: {state['current_quantity']}, Pool: {state['current_pool']}, V: {state['current_v']}")
        
        return state



    def _generate_orders(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate list of orders based on current state."""
        try:
            print(f"\n📊 _generate_orders called with state: {state}")
            
            # 1. Get Current Price
            try:
                raw_price = self.broker.get_price(self.ticker)
                price_info = self.broker.parse_price_response(raw_price)
                if price_info['price'] is None:
                    print(f"❌ Failed to get price for {self.ticker}. Response: {price_info}")
                    raise ValueError(f"Failed to get current price. Response: {price_info}")
                current_price = price_info['price']
                print(f"  ✓ Current Price: {current_price}")
            except Exception as e:
                print(f"❌ [Error] Failed to get current price: {e}")
                raise
            
            # 2. Extract State Variables
            current_qty = state.get('current_quantity', 0)
            current_pool = state.get('current_pool', 0)
            current_v = (current_price * current_qty) + current_pool
            
            # Update V in state
            state['current_v'] = current_v
            
            print(f"  State vars - V: {current_v}, Qty: {current_qty}, Pool: {current_pool}")
            
            u_band = self.u_band
            l_band = self.l_band
            limit_per_day = self.investment
            
            buy_orders = []
            sell_orders = []
            
            # Buy Logic
            n = 1
            buy_sum = 0
            if current_qty + n > 0:
                target_price = current_v * (1 - l_band) / (current_qty + n)
                buy_sum = target_price
                
                while buy_sum <= current_pool and buy_sum <= limit_per_day:
                    if target_price > 0:
                        buy_orders.append({"side": "BUY", "price": round(target_price, 2), "qty": 1})
                        print(f"    Buy order: qty=1, price={round(target_price, 2)}")
                    n += 1
                    if current_qty + n > 0:
                        target_price = current_v * (1 - l_band) / (current_qty + n)
                        buy_sum += target_price
                    else:
                        break

            # Sell Logic
            n = 0
            sell_qty_sum = 0
            while sell_qty_sum < current_qty: 
                n += 1
                if current_qty - n <= 0: 
                    break
                target_price = current_v * (1 + u_band) / (current_qty - n)
                if target_price <= 0: 
                    break
                
                sell_orders.append({"side": "SELL", "price": round(target_price, 2), "qty": 1})
                print(f"    Sell order: qty=1, price={round(target_price, 2)}")
                sell_qty_sum += 1
                if sell_qty_sum > 10: 
                    break 

            print(f"  ✓ Generated {len(buy_orders)} buy orders and {len(sell_orders)} sell orders")
            return buy_orders + sell_orders
            
        except Exception as e:
            print(f"❌ [CRITICAL] _generate_orders failed: {e}")
            import traceback
            traceback.print_exc()
            raise
