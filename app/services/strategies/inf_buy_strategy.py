import math
from datetime import datetime, timedelta
import time
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import desc
from app.models.schema import Strategy, StrategySnapshot, Order
from app.models.enums import OrderStatus, OrderType
from app.services.broker.base import BaseBroker
from app.services.strategies.base import BaseStrategy
from enum import Enum
import pytz
from app.models.enums import RequestOutcome, SnapshotStatus



class OrderSubType(str, Enum):
    """Order generation type"""
    INIT = "Init"
    INIT_DROP = "InitDrop"
    AVG_BUY = "AvgBuy"
    STAR_BUY = "StarBuy"
    STAR_SELL = "StarSell"
    ALL_SELL = "AllSell"
    QTR_SELL = "QtrSell"

class InfBuyStrategy(BaseStrategy):
    def debug_last_order_sync(self):
        """마지막 스냅샷의 orders와 _sync_snapshot_orders 결과를 출력"""
        last_snapshot = self._get_last_snapshot()
        if not last_snapshot:
            print("No snapshot found.")
            return

        orders = self.db.query(Order).filter(Order.snapshot_id == last_snapshot.id).all()
        print(f"[DEBUG] Last Snapshot ID: {last_snapshot.id}, Orders:")
        for o in orders:
            print(f"  OrderID: {o.order_id}, Status: {o.order_status}, Qty: {o.order_qty}, Price: {o.order_price}")

        print("\n[DEBUG] Running _sync_snapshot_orders...")
        self._sync_snapshot_orders(last_snapshot)
    """
    Infinite Buy Strategy Implementation (V2).
    Uses new Strategy/Snapshot/Order schema.
    """
    
    def __init__(self, strategy: Strategy, broker: BaseBroker, db: Session):
        super().__init__(strategy, broker, db)
        
        # Config
        self.ticker = self.params.get('ticker')
        self.division = int(self.params.get('division', 20))
        self.sell_gain = float(self.params.get('sell_gain', 20)) / 100.0
        self.initial_investment = float(self.params.get('initial_investment', 10000.0))
        self.reinvestment_rate = float(self.params.get('reinvestment_rate', 50)) / 100.0  # New param

    def execute_daily_routine(self):
        
        print(f"🚀 Starting InfBuy Routine for {self.strategy.name} ({self.ticker})")
        
        # 0. Get Current Price
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

        # 1. Get Last Snapshot
        last_snapshot = self._get_last_snapshot()
        
        # 2. Check Last Snapshot Status

        if not last_snapshot:
            # First time
            print("No previous snapshot found. Initializing new strategy.")
            last_snapshot = self._create_initial_snapshot()
            self.db.refresh(last_snapshot)
            # snapshot is COMPLETED. Proceed to create new snapshot below.
        else:
            print(f"Found previous snapshot (Cycle {last_snapshot.cycle}, Created: {last_snapshot.created_at})")
        # 3. Handle based on status
        # if FAILED, log and exit
        # else
            # Steps:
                # Step1: if IN_PROGRESS -> sync orders -> if all finalized mark completed
                # Step2: if COMPLETED -> calculate next state -> place orders -> create new snapshot and set pending
                # Step3: if PENDING -> try placing orders and set IN_PROGRESS if any success
        if last_snapshot.status == SnapshotStatus.FAILED:
            print("❌ Last snapshot failed. Manual intervention may be needed.")
            return
        
        else:
            # Step 1: If IN_PROGRESS, sync orders
            if last_snapshot.status == SnapshotStatus.IN_PROGRESS:
                all_finalized = self._sync_snapshot_orders(last_snapshot)
                if all_finalized and last_snapshot.status == SnapshotStatus.IN_PROGRESS:
                    last_snapshot.status = SnapshotStatus.COMPLETED
                    print(f"  ✅ All orders finalized. Snapshot marked as COMPLETED")
                else:
                    print(f"  ⚠️  Some orders are still pending. Snapshot remains IN_PROGRESS")                    
                self.db.commit()
            # Step 2: If COMPLETED, calculate next state and create new PENDING snapshot
            if last_snapshot.status == SnapshotStatus.COMPLETED:
                print("✅ Last snapshot orders are completed.")
                new_state = self._calculate_next_state(last_snapshot)
                cycle = new_state.get('cycle', last_snapshot.cycle)   
                new_snapshot = StrategySnapshot(
                strategy_id=self.strategy.id,
                status=SnapshotStatus.PENDING,
                cycle=cycle,
                progress=new_state
                )
                print(f"📸 Created New Snapshot (ID: {new_snapshot.id}, Status: PENDING)")
                self.db.add(new_snapshot)     
                last_snapshot = new_snapshot  # Update reference for Step 3
                self.db.commit()
            # Step 3: If PENDING, try placing orders
            if last_snapshot.status == SnapshotStatus.PENDING:
                print(f"⏸️  Found PENDING snapshot. Retrying order placement...")
                order_result = self._place_orders(last_snapshot, current_price)
                success = order_result.get('success', False)
                if success:
                    last_snapshot.status = SnapshotStatus.IN_PROGRESS
                    kst = pytz.timezone('Asia/Seoul')
                    last_snapshot.executed_at = datetime.now(tz=pytz.UTC).astimezone(kst)
                    print(f"  ✅ Orders placed successfully. executed_at set.")
                else:
                    last_snapshot.executed_at = None
                    if order_result.get('is_holiday', False):
                        print(f"  📅 Market closed. Keeping snapshot as PENDING.")
                    else:                           
                        last_snapshot.status = SnapshotStatus.FAILED
                        last_snapshot.progress['error_msg'] = order_result.get('error_msg', 'Unknown error during order placement')
                        flag_modified(last_snapshot, 'progress')
                        print(f"  ❌ No orders were placed successfully. executed_at cleared.")
            self.db.commit()                
            return

        
        
        # case completed or or completed sync after in_progress orders





        # # 3. Place order and Create New Snapshot if needed
        # if last_snapshot and last_snapshot.status == "PENDING":
        #     print(f"📸 Used Existing Snapshot (ID: {last_snapshot.id}, Status: PENDING)")
        #     success = self._place_orders(last_snapshot)
            
        # else:            
        #     new_snapshot = StrategySnapshot(
        #         strategy_id=self.strategy.id,
        #         status="PENDING",
        #         cycle=cycle,
        #         progress=current_state
        #     )
        #     print(f"📸 Created New Snapshot (ID: {new_snapshot.id}, Status: PENDING)")
        #     self.db.add(new_snapshot)
        #     self.db.commit()
        #     success = self._place_orders(new_snapshot)
            
        

        
        # if success:
        #     print("✅ Routine Completed")
        # else:
        #     print(f"⏸️  Routine Pending (will retry on next execution)")

    def _create_initial_snapshot(self) -> StrategySnapshot:
        initial_state = {
            "current_t": 0,
            "star": self.sell_gain,
            "investment": self.initial_investment,
            "unit_investment": self.initial_investment / self.division if self.initial_investment else 0,
            "avg_price": 0,
            "quantity": 0,
            "balance": self.initial_investment, 
            "equity": self.initial_investment,
            "daily_profit": 0,
            "cycle": 0
        }
        cycle = 0
        new_snapshot = StrategySnapshot(
            strategy_id=self.strategy.id,
            status=SnapshotStatus.COMPLETED,
            cycle=cycle,
            progress=initial_state
        )
        print(f"📸 Created New Snapshot (ID: {new_snapshot.id}, Status: COMPLETED)")
        self.db.add(new_snapshot)
        self.db.commit()
        return new_snapshot
        

    def _calculate_next_state(self, last_snapshot: StrategySnapshot, current_price) -> Dict[str, Any]:
        """Calculate new state based on last snapshot and its filled orders."""
        state = last_snapshot.progress.copy()
        orders = self.db.query(Order).filter(Order.snapshot_id == last_snapshot.id).all()
        
        # Calculate filled orders summary
        buy_sum = {"qty": 0, "value": 0}
        sell_sum = {"qty": 0, "value": 0, "daily_profit": 0}
        
        old_avg = state.get('avg_price', 0)
        old_qty = state.get('quantity', 0)
        
        # Update state based on FILLED orders
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
                    sell_sum["daily_profit"] += ((filled_price - old_avg) * qty)
        
        # Calculate new values
        temp_qty = old_qty - sell_sum["qty"]
        temp_amount = temp_qty * old_avg
        new_qty = temp_qty + buy_sum["qty"]
        new_amount = temp_amount + buy_sum["value"]
        
        if new_qty <= 0.0001:
            new_avg = 0
        else:
            new_avg = round(new_amount / new_qty, 2)
        
        # Update investment: add half of sell profit
        new_investment = round(state.get('investment', 0) + self.reinvestment_rate * sell_sum["daily_profit"], 2)
        unit_investment = round(new_investment / self.division, 2) if self.division > 0 else 0
        
        # Update profit: add half of sell profit
        # new_profit = round(state.get('profit', 0) + self.reinvestment_rate * sell_sum["profit"], 2)
        
        # Update balance
        new_balance = round(
            state.get('balance', 0) 
            + sell_sum["value"] 
            - buy_sum["value"], 
            2
        )
        
        # Calculate T and Star
        if unit_investment > 0 and new_qty > 0:
            new_t = round(new_avg * new_qty / unit_investment, 2)
        else:
            new_t = 0
        
        new_star = round(
            (self.sell_gain - new_t * self.sell_gain / self.division * 2), 
            2
        )

        # Update state
        state['current_t'] = new_t
        state['star'] = new_star
        state['investment'] = new_investment
        state['unit_investment'] = unit_investment
        state['daily_profit'] = sell_sum["daily_profit"]    
        state['quantity'] = new_qty
        state['avg_price'] = new_avg
        state['balance'] = new_balance
        state['equity'] = new_balance + new_qty * current_price
        
        # Check for Cycle Reset (if all sold)
        if new_qty <= 0.0001:  # Float safety
            state['current_t'] = 0
            state['star'] = self.sell_gain
            state['investment'] = new_investment  # Keep investment
            state['unit_investment'] = new_investment / self.division if new_investment else 0
            state['daily_profit'] = 0
            state['quantity'] = 0
            state['avg_price'] = 0
            state['balance'] = new_balance
            state['equity'] = new_balance
            # Increment cycle
            state['cycle'] = last_snapshot.cycle + 1
        else:
            state['cycle'] = last_snapshot.cycle 
        
        print(f"  State Update - T: {state['current_t']}, Qty: {state['quantity']}, "
            f"Avg: {state['avg_price']}, Daily Profit: {state['daily_profit']}, Balance: {state['balance']}, Equity: {state['equity']}")
        
        return state

    def _generate_orders(self, state: Dict[str, Any], current_price) -> List[Dict[str, Any]]:
        """Generate list of orders based on current state."""
        try:
            print(f"\n📊 _generate_orders called with state: {state}")
            
            # 1. Get Current Price
            
            # 2. Extract State Variables
            try:
                avg_price = state.get('avg_price', None)
                current_t = state.get('current_t', 0)
                if avg_price is None and current_t > 0:
                    print("❌ avg_price is None despite T>0")
                    raise ValueError("avg_price is None despite T>0")
                star = state.get('star', 0)
                investment = state.get('investment', 0)
                
                quantity = state.get('quantity', 0)
                
                print(f"  State vars - T: {current_t}, Qty: {quantity}, Avg: {avg_price}, Star: {star}")
                
                # Calculate Star Price
                if avg_price > 0.001:
                    star_price = round(avg_price * (1 + star), 2)
                else:
                    star_price = round(current_price * (1 + star), 2)
                # Adjust Star Buy Price if too high to avoid broker rejections
                star_buy_price = min(star_price, round(current_price * 1.19, 2))
                avg_buy_price = min(avg_price, round(current_price * 1.19, 2))
                    
                print(f"  Price calc - star_price: {star_price}, star_buy_price: {star_buy_price}, avg_buy_price: {avg_buy_price}")
                
            except Exception as e:
                print(f"❌ [Error] Failed to extract state variables: {e}")
                raise
            
            # 3. Calculate Investment Amount
            try:
                unit_investment = investment / self.division if investment > 0 else self.initial_investment / self.division
                if unit_investment is None or unit_investment <= 0:
                    print(f"⚠️  Warning: unit_investment is {unit_investment}, using fallback")
                    unit_investment = self.initial_investment / self.division
                    
                print(f"  Unit Investment: {unit_investment}")
                
                if unit_investment <= 0:
                    print("❌ Invalid unit investment amount - must be > 0")
                    raise ValueError("Invalid unit investment amount: must be > 0")
                    
            except Exception as e:
                print(f"❌ [Error] Failed to calculate unit investment: {e}")
                raise
            
            orders = []
            
            # 4. Generate Orders by T Phase
            try:
                if current_t == 0:
                    print(f"  [Phase] Initial Buy (T=0)")
                    # Initial Buy Orders Starting from 20% above current price
                    target_price = round(current_price * 1.2, 2)
                    qty = int(unit_investment / target_price) if target_price > 0 else 0
                    print(f"    Initial order: qty={qty}, price={target_price}")
                    if qty > 0:
                        orders.append({"side": "BUY", "type": OrderSubType.INIT, "price": target_price, "qty": qty})
                    
                    # Drop orders
                    while target_price > current_price * 0.8:
                        qty += 1
                        target_price = round(unit_investment / qty, 2)
                        print(f"    Drop order: qty={qty}, price={target_price}")
                        orders.append({"side": "BUY", "type": OrderSubType.INIT_DROP, "price": target_price, "qty": 1})
                        
                elif current_t <= self.division / 2:
                    print(f"  [Phase] First Half (T={current_t})")
                    # BuyAvg
                    qty_buy_avg = int(round(unit_investment / 2 / avg_buy_price, 0)) if avg_buy_price > 0 else 0
                    print(f"    BuyAvg: qty={qty_buy_avg}, price={avg_buy_price}")
                    orders.append({"side": "BUY", "type": OrderSubType.AVG_BUY, "price": avg_buy_price, "qty": qty_buy_avg})
                    
                    # BuyStar
                    remaining = unit_investment - (avg_buy_price * qty_buy_avg)
                    qty_buy_star = int(round(remaining / star_buy_price, 0)) if star_buy_price > 0 else 0
                    print(f"    BuyStar: qty={qty_buy_star}, price={star_buy_price} (remaining={remaining})")
                    orders.append({"side": "BUY", "type": OrderSubType.STAR_BUY, "price": star_buy_price, "qty": qty_buy_star})
                    
                    # SellStar
                    qty_sell_star = int(round(quantity / 4, 0)) if quantity > 0 else 0
                    print(f"    SellStar: qty={qty_sell_star}, price={star_buy_price + 0.01}")
                    orders.append({"side": "SELL", "type": OrderSubType.STAR_SELL, "price": star_buy_price + 0.01, "qty": qty_sell_star})
                    
                    # SellAll
                    sell_price = round(avg_price * (1 + self.sell_gain), 2) if avg_price > 0 else 0
                    sell_qty = max(0, quantity - qty_sell_star)
                    print(f"    SellAll: qty={sell_qty}, price={sell_price}")
                    orders.append({"side": "SELL", "type": OrderSubType.ALL_SELL, "price": sell_price, "qty": sell_qty})
                    
                elif self.division / 2 < current_t <= self.division - 1:
                    print(f"  [Phase] Second Half (T={current_t})")
                    # BuyStar
                    qty_buy_star = int(round(unit_investment / star_buy_price, 0)) if star_buy_price > 0 else 0
                    print(f"    BuyStar: qty={qty_buy_star}, price={star_buy_price}")
                    orders.append({"side": "BUY", "type": OrderSubType.STAR_BUY, "price": star_buy_price, "qty": qty_buy_star})
                    
                    # SellStar
                    qty_sell_star = int(round(quantity / 4, 0)) if quantity > 0 else 0
                    print(f"    SellStar: qty={qty_sell_star}, price={star_buy_price + 0.01}")
                    orders.append({"side": "SELL", "type": OrderSubType.STAR_SELL, "price": star_buy_price + 0.01, "qty": qty_sell_star})
                    
                    # SellAll
                    sell_price = round(avg_price * (1 + self.sell_gain), 2) if avg_price > 0 else 0
                    sell_qty = max(0, quantity - qty_sell_star)
                    print(f"    SellAll: qty={sell_qty}, price={sell_price}")
                    orders.append({"side": "SELL", "type": OrderSubType.ALL_SELL, "price": sell_price, "qty": sell_qty})
                    
                elif current_t > self.division - 1:
                    print(f"  [Phase] Quarter Loss Cut Mode (T={current_t})")
                    # Quarter Loss Cut
                    qty_cut = int(round(quantity / 4, 0)) if quantity > 0 else 0
                    print(f"    QtrSell: qty={qty_cut}, price=MARKET")
                    orders.append({"side": "SELL", "type": OrderSubType.QTR_SELL, "price": 0, "qty": qty_cut})
                
            except Exception as e:
                print(f"❌ [Error] Failed to generate orders for phase T={current_t}: {e}")
                import traceback
                traceback.print_exc()
                raise
            
            print(f"  ✓ Generated {len(orders)} orders: {orders}")
            return orders
            
        except Exception as e:
            print(f"❌ [CRITICAL] _generate_orders failed: {e}")
            import traceback
            traceback.print_exc()
            raise


    def _place_single_order(self, order_data: Dict) -> Optional[Dict]:
        """Place a single order via broker (Override for QTR_SELL special handling)"""
        # Special handling for QTR_SELL: use MOC order type
        if order_data.get('type') == OrderSubType.QTR_SELL:
            order_data['order_type'] = 'MOC'
            order_data['price'] = 0  # MOC orders don't need price
        
        return super()._place_single_order(order_data)  # call parent method


    # def _is_snapshot_from_today(self, snapshot: StrategySnapshot) -> bool:
    #     """Check if snapshot is from today (KST)"""
    #     if not snapshot:
    #         return False
        
    #     kst = pytz.timezone('Asia/Seoul')
    #     snapshot_kst = snapshot.created_at.replace(tzinfo=pytz.UTC).astimezone(kst)
    #     today_kst = datetime.now(kst)
    #     print(f"  Snapshot date (KST): {snapshot_kst.date()}, Today (KST): {today_kst.date()}") 
    #     return snapshot_kst.date() == today_kst.date()