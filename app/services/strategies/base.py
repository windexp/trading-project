import math
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import time
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import desc
from app.models.schema import Strategy, StrategySnapshot, Order
from app.models.enums import OrderStatus, OrderType, RequestOutcome
from app.services.broker.base import BaseBroker
import pytz


class BaseStrategy(ABC):
    """
    Abstract Base Class for Trading Strategies.
    Common logic shared between all strategies.
    """
    
    def __init__(self, strategy: Strategy, broker: BaseBroker, db: Session):
        self.strategy = strategy
        self.broker = broker
        self.db = db
        self.params = strategy.base_params
        self.ticker = self.params.get('ticker')

    @abstractmethod
    def execute_daily_routine(self):
        """Execute the strategy's daily routine."""
        pass

    @abstractmethod
    def _generate_orders(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate orders based on current state."""
        pass

    @abstractmethod
    def _calculate_next_state(self, last_snapshot: StrategySnapshot) -> Dict[str, Any]:
        """Calculate next state based on last snapshot."""
        pass

    def _get_last_snapshot(self) -> Optional[StrategySnapshot]:
        """Get the last snapshot for this strategy."""
        return self.db.query(StrategySnapshot)\
            .filter(StrategySnapshot.strategy_id == self.strategy.id)\
            .order_by(desc(StrategySnapshot.created_at))\
            .first()

    def _sync_snapshot_orders(self, snapshot: StrategySnapshot, start_offset: int = 1) -> None:
        """Check status of orders in the snapshot and update DB."""
        orders = self.db.query(Order).filter(Order.snapshot_id == snapshot.id).all()
        if not orders:
            return

        print(f"Syncing {len(orders)} orders from snapshot...")
        
        kst = pytz.timezone('Asia/Seoul')
        # Get date range based on snapshot type
        snapshot_date = snapshot.created_at.replace(tzinfo=pytz.UTC).astimezone(kst) - timedelta(days=start_offset)
        now_kst = datetime.now(kst)
        
        # Get min/max dates from orders for more accurate range
        min_dt = min(order.updated_at for order in orders)
        max_dt = max(order.updated_at for order in orders)
        min_kst = min_dt.replace(tzinfo=pytz.UTC).astimezone(kst) 
        max_kst = max_dt.replace(tzinfo=pytz.UTC).astimezone(kst) 
        
        start_date = min(snapshot_date, min_kst).strftime("%Y%m%d")
        end_date = max_kst.strftime("%Y%m%d")
        
        print(f"[DEBUG] Transaction history lookup range: {start_date} ~ {end_date}")
        raw_history = self.broker.get_transaction_history(self.ticker, start_date, end_date)
        history_list = self.broker.parse_history_response(raw_history)
        history_map = {h['order_id']: h for h in history_list}
        
        for order in orders:
            if order.order_id in history_map:
                info = history_map[order.order_id]
                order.order_status = info.get('status', order.order_status)
                order.filled_qty = info.get('filled_qty', 0)
                order.filled_price = float(info.get('filled_amt', 0.0))/order.filled_qty if order.filled_qty else 0.0
            else:
                print(f"  Order {order.order_id} Not Found in History")
    
        # Check if all orders are finalized (no more SUBMITTED/PENDING)
        self.db.commit()
        all_finalized = all(
            order.order_status != OrderStatus.SUBMITTED
            for order in orders
        )
        return all_finalized
        # if all_finalized and snapshot.status == "IN_PROGRESS":
        #     snapshot.status = "COMPLETED"
        #     print(f"  ✅ All orders finalized. Snapshot marked as COMPLETED")
        
        # self.db.commit()

    def _place_orders(self, snapshot: StrategySnapshot, current_price) -> Dict[str, Any]:
        """
        Place orders for the given snapshot.
        Returns a dict with results {"success": False, "submitted_orders": 0, "accepted_orders": 0, "is_holiday": False}
        
        """
        result = {"success": False, "submitted_orders": 0, "accepted_orders": 0, "is_holiday": False, "error_msg": None}
        try:
            # 1. Generate Orders
            orders = self._generate_orders(snapshot.progress, current_price)
            result['submitted_orders'] = len(orders)
            if not orders:
                print("  No orders to place")
                snapshot.executed_at = None
                self.db.commit()
                result["success"] = True
                return result
            
            # 2. Place all orders
            print(f"  Placing {len(orders)} orders...")
            msg = []
            
            for order_data in orders:
                try:
                    print(f"  [{order_data['side']}] {order_data['qty']} @ {order_data['price']}")
                    if order_data['qty'] <= 0:
                        print("    ⚠️  Skipping order with zero quantity")
                        continue
                    
                    res = self._place_single_order(order_data)
                    
                    if res and res.get('outcome') == RequestOutcome.ACCEPTED:
                        print(f"    ✅ Order Accepted: {res['order_id']}")
                        snapshot.progress['msg'] = None
                        result['accepted_orders'] += 1
                        flag_modified(snapshot, 'progress')
                        
                    else:
                        error_msg = res.get('error_msg', 'Unknown error') if res else 'No response'
                        result['error_msg'] = error_msg
                        error_code = res.get('error_code', '') if res else ''
                        msg.append(f"{error_code} - {error_msg}")
                        snapshot.progress['msg'] = msg
                        flag_modified(snapshot, 'progress')
                        if res.get('is_holiday', False):
                            print(f"  📅 Market closed ({error_code}: {error_msg}). Keeping snapshot as PENDING.")
                            snapshot.executed_at = None
                            result['is_holiday'] = True
                            break
                        else:
                            print(f"    ⚠️ Order Rejected: {error_code} - {error_msg}")
                            continue

                    # Order succeeded
                    self._save_order(res, snapshot, order_data)
                    print(f"    ✅ Order Placed: {res['order_id']}")
                    
                    
                except Exception as e:
                    print(f"    ❌ Exception: {e}")
                    
                time.sleep(0.1)  # To avoid hitting rate limits
            if result['accepted_orders'] > 0:
                result["success"] = True
            self.db.commit()
                        
            return result
            
        except Exception as e:
            print(f"❌ Error placing orders: {e}")
            import traceback
            traceback.print_exc()
            snapshot.status = "FAILED"
            snapshot.progress['error'] = str(e)
            flag_modified(snapshot, 'progress')
            snapshot.executed_at = None
            self.db.commit()
            return False

    def _place_single_order(self, order_data: Dict) -> Optional[Dict]:
        """Place a single order via broker"""
        if order_data['side'] == "BUY":
            raw = self.broker.buy_order(
                self.ticker, 
                order_data['qty'], 
                order_data['price'], 
                order_type=order_data.get('order_type', "LOC")
            )
        else:
            raw = self.broker.sell_order(
                self.ticker, 
                order_data['qty'], 
                order_data['price'], 
                order_type=order_data.get('order_type', "LOC")
            )
        return self.broker.parse_order_response(raw)

    def _save_order(self, response: Dict, snapshot: StrategySnapshot, order_data: Dict):
        """Save order to database using standardized response"""
        db_order = Order(
            order_id=response.get('order_id'),
            snapshot_id=snapshot.id,
            order_status=OrderStatus.SUBMITTED if response.get('outcome') == RequestOutcome.ACCEPTED else OrderStatus.REJECTED,
            order_type=OrderType.BUY if order_data['side'] == "BUY" else OrderType.SELL,
            symbol=self.ticker,
            order_qty=order_data['qty'],
            order_price=order_data['price'],
            extra={"desc": order_data.get('type', 'Order'), "broker": response}
        )
        self.db.add(db_order)
