import math
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import time
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import desc
from app.models.schema import Strategy, StrategySnapshot, Order
from app.models.enums import OrderStatus, OrderType, RequestOutcome
from app.services.broker.base import BaseBroker
import pytz

logger = logging.getLogger(__name__)


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
    def _calculate_next_state(self, last_snapshot: StrategySnapshot, current_price) -> Dict[str, Any]:
        """Calculate next state based on last snapshot."""
        pass

    @abstractmethod
    def generate_daily_summary(self) -> Dict[str, Any]:
        """Generate daily summary for Discord notification."""
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

        logger.info(f"Syncing {len(orders)} orders from snapshot...")
        
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
        
        logger.debug(f"Transaction history lookup range: {start_date} ~ {end_date}")
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
                logger.warning(f"Order {order.order_id} Not Found in History")
    
        # Check if all orders are finalized (no more SUBMITTED/PENDING)
        self.db.commit()  # ← 추가!
        logger.info(f"  💾 {len(orders)} orders synced and committed")
            
        all_finalized = all(
            order.order_status != OrderStatus.SUBMITTED
            for order in orders
        )
        return all_finalized

    def _place_orders(self, snapshot: StrategySnapshot, current_price) -> Dict[str, Any]:
        result = {
        "success": False, 
        "submitted_orders": 0, 
        "accepted_orders": 0, 
        "is_holiday": False, 
        "error_msg": None
        }
            
        error_list = []            
        
        try:
            self.db.refresh(snapshot)
            # 1. Generate Orders
            orders = self._generate_orders(snapshot.progress, current_price)
            result['submitted_orders'] = len(orders)
            
            if not orders:
                logger.info("No orders to place")
                result["success"] = True
                result['error_msg'] = None
                return result
            
            # 2. Place all orders
            logger.info(f"Placing {len(orders)} orders...")
                     
            for order_data in orders:
                try:
                    logger.info(f"[{order_data['side']}] {order_data['qty']} @ {order_data['price']}")
                    if order_data.get('qty', 0) <= 0:
                        logger.warning("Skipping order with zero quantity")
                        continue
                    res = self._place_single_order(order_data)
                    
                    if not res:
                        error_list.append('No response from broker')
                        logger.warning("  ⚠️ No response from broker")
                        continue
                    
                    # Check if market is closed first
                    if res.get('is_holiday', False):
                        msg = res.get('error_msg', 'Market closed')
                        error_code = res.get('error_code', '')
                        logger.info(f"📅 Market closed ({error_code}: {msg}). Keeping snapshot as PENDING.")
                        result['is_holiday'] = True
                        break
                    
                    # Handle accepted orders
                    if res.get('outcome') == RequestOutcome.ACCEPTED:
                        logger.info(f"  ✅ Order Accepted: {res['order_id']}")
                        result['accepted_orders'] += 1
                    else:
                        # Handle rejected orders
                        msg = res.get('error_msg', 'Unknown error')
                        error_code = res.get('error_code', '')
                        error_list.append(f"{error_code}: {msg}")
                        logger.warning(f"  ⚠️ Order Rejected: Price {order_data['price']} ({error_code} - {msg})")
                    
                    # Save order (both accepted and rejected)
                    self._save_order(res, snapshot, order_data)
                    logger.info(f"  💾 Order Saved: {res.get('order_id', 'N/A')}")                    
                    
                except Exception as e:
                    error_list.append(f"Order exception: {str(e)}")
                    logger.info(f"  ❌ Exception: {e}")
                    
                time.sleep(0.1)  # To avoid hitting rate limits
            if result['accepted_orders'] > 0:
                result["success"] = True

            if result['accepted_orders'] == result['submitted_orders']:
                result['error_msg'] = None
            else:
                result['error_msg'] = error_list
            return result
            
        except Exception as e:
            print(f"❌ Error placing orders: {e}")
            import traceback
            traceback.print_exc()
            result['success'] = False
            result['error_msg'] = str(e)
            return result

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
