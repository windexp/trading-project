from fastapi import status as http_status
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel

from app.core.database import get_db
from app.services.broker.koreainvestment import KoreaInvestmentBroker
from app.models.account import Account
from app.models.schema import Strategy, StrategySnapshot, Order
from app.models.enums import StrategyStatus

# We need to update the strategy implementations to use the new schema
from app.services.strategies.vr_strategy import VRStrategy
from app.services.strategies.inf_buy_strategy import InfBuyStrategy

router = APIRouter()


# --- Pydantic Models for Request/Response ---
class StrategyCreate(BaseModel):
    name: str
    strategy_code: str # "VR" or "InfBuy"
    account_name: str
    base_params: Dict[str, Any]
    description: Optional[str] = None

class StrategyResponse(BaseModel):

    id: int
    name: str
    strategy_code: str
    status: str
    base_params: Dict[str, Any]
    created_at: datetime
    class Config:
        from_attributes = True

# Deactivate (pause) a strategy

@router.post("/{strategy_name}/deactivate", response_model=StrategyResponse, status_code=http_status.HTTP_200_OK)
def deactivate_strategy(strategy_name: str, db: Session = Depends(get_db)):
    strategy = db.query(Strategy).filter(Strategy.name == strategy_name).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    if strategy.status == StrategyStatus.PAUSED:
        raise HTTPException(status_code=400, detail="Strategy already deactivated")
    strategy.status = StrategyStatus.PAUSED
    db.commit()
    db.refresh(strategy)
    return strategy

# Activate (resume) a strategy
@router.post("/{strategy_name}/activate", response_model=StrategyResponse, status_code=http_status.HTTP_200_OK)
def activate_strategy(strategy_name: str, db: Session = Depends(get_db)):
    strategy = db.query(Strategy).filter(Strategy.name == strategy_name).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    if strategy.status == StrategyStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Strategy already active")
    strategy.status = StrategyStatus.ACTIVE
    db.commit()
    db.refresh(strategy)
    return strategy

# --- Endpoints ---

@router.post("/", response_model=StrategyResponse)
def create_strategy(strategy: StrategyCreate, db: Session = Depends(get_db)):
    # Check if exists
    existing = db.query(Strategy).filter(Strategy.name == strategy.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Strategy with this name already exists")
    
    new_strategy = Strategy(
        name=strategy.name,
        strategy_code=strategy.strategy_code,
        account_name=strategy.account_name,
        base_params=strategy.base_params,
        description=strategy.description,
        status=StrategyStatus.ACTIVE
    )
    db.add(new_strategy)
    db.commit()
    db.refresh(new_strategy)
    
    # Create Initial Snapshot
    initial_state = {}
    if new_strategy.strategy_code == "InfBuy":
        inv = float(new_strategy.base_params.get("investment_amount", 10000) or 10000)
        div = int(new_strategy.base_params.get("division", 20) or 20)
        unit_inv = inv / div if div else 0
        initial_state = {
            "current_t": 0,
            "star": strategy.base_params.get("sell_gain", 20),
            "investment": strategy.base_params.get("investment_amount", 10000),
            "profit": 0,
            "quantity": 0,
            "balance": strategy.base_params.get("investment_amount", 10000),
            "unit_investment": unit_inv,
            "avg_price": 0,
        }
    elif new_strategy.strategy_code == "VR":
        initial_state = {
            "total_investment": 0,
            "current_v": 0,
            "current_quantity": 0,
            "current_pool": 0
        }
    
    initial_snapshot = StrategySnapshot(
        strategy_id=new_strategy.id,
        status="INIT",
        cycle=0,
        progress=initial_state
    )
    db.add(initial_snapshot)
    db.commit()
    
    return new_strategy

@router.get("/", response_model=List[StrategyResponse])
def list_strategies(db: Session = Depends(get_db)):
    return db.query(Strategy).all()

@router.get("/{strategy_name}")
def get_strategy(strategy_name: str, db: Session = Depends(get_db)):
    strategy = db.query(Strategy).filter(Strategy.name == strategy_name).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    # Get latest snapshot
    latest_snapshot = db.query(StrategySnapshot)\
        .filter(StrategySnapshot.strategy_id == strategy.id)\
        .order_by(desc(StrategySnapshot.created_at))\
        .first()
        
    return {
        "strategy": strategy,
        "latest_snapshot": latest_snapshot
    }

@router.get("/{strategy_name}/price")
def get_strategy_ticker_price(strategy_name: str, db: Session = Depends(get_db)):
    """Get current price of the strategy's ticker from broker API."""
    strategy = db.query(Strategy).filter(Strategy.name == strategy_name).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    ticker = strategy.base_params.get('ticker')
    if not ticker:
        raise HTTPException(status_code=400, detail="Strategy has no ticker configured")
    
    # Get account and initialize broker
    account = db.query(Account).filter(Account.account_no == strategy.account_name).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    broker = KoreaInvestmentBroker(
        account_no=account.account_no,
        app_key=account.app_key,
        app_secret=account.app_secret
    )
    try:
        price_data = broker.get_price(ticker)
        parsed = broker.parse_price_response(price_data)
        return parsed
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching price: {str(e)}")

class StrategyUpdate(BaseModel):
    base_params: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    status: Optional[str] = None

@router.put("/{strategy_name}", response_model=StrategyResponse)
def update_strategy(strategy_name: str, strategy_update: StrategyUpdate, db: Session = Depends(get_db)):
    strategy = db.query(Strategy).filter(Strategy.name == strategy_name).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    if strategy_update.base_params is not None:
        strategy.base_params = strategy_update.base_params
    if strategy_update.description is not None:
        strategy.description = strategy_update.description
    if strategy_update.status is not None:
        strategy.status = strategy_update.status
        
    db.commit()
    db.refresh(strategy)
    return strategy

@router.delete("/{strategy_name}")
def delete_strategy(strategy_name: str, db: Session = Depends(get_db)):
    strategy = db.query(Strategy).filter(Strategy.name == strategy_name).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    db.delete(strategy)
    db.commit()
    return {"message": "Strategy deleted"}

@router.get("/{strategy_name}/logs")
def get_strategy_logs(strategy_name: str, db: Session = Depends(get_db)):
    strategy = db.query(Strategy).filter(Strategy.name == strategy_name).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    # Join Strategy -> Snapshot -> Order
    orders = db.query(Order)\
        .join(StrategySnapshot)\
        .filter(StrategySnapshot.strategy_id == strategy.id)\
        .order_by(desc(Order.ordered_at))\
        .all()
        
    # Format for frontend
    logs = []
    for o in orders:
        logs.append({
            "executed_at": o.ordered_at,
            "trade_type": o.order_type,
            "ticker": o.symbol,
            "price": o.order_price,
            "quantity": o.order_qty,
            "total_amount": float(o.order_price) * o.order_qty # Approximate
        })
    return logs

@router.get("/{strategy_name}/snapshots")
def list_strategy_snapshots(strategy_name: str, db: Session = Depends(get_db)):
    strategy = db.query(Strategy).filter(Strategy.name == strategy_name).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    snapshots = db.query(StrategySnapshot)\
        .filter(StrategySnapshot.strategy_id == strategy.id)\
        .order_by(desc(StrategySnapshot.created_at))\
        .all()
    return snapshots

@router.get("/{strategy_name}/snapshots/{snapshot_id}")
def get_strategy_snapshot_details(strategy_name: str, snapshot_id: int, db: Session = Depends(get_db)):
    strategy = db.query(Strategy).filter(Strategy.name == strategy_name).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    snapshot = db.query(StrategySnapshot)\
        .filter(StrategySnapshot.id == snapshot_id, StrategySnapshot.strategy_id == strategy.id)\
        .first()
        
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
        
    # Get Orders
    orders = db.query(Order).filter(Order.snapshot_id == snapshot.id).all()
    
    return {
        "snapshot": snapshot,
        "orders": orders
    }


# Allow status to be updated as well
class SnapshotUpdate(BaseModel):
    progress: Dict[str, Any]
    status: Optional[str] = None

@router.put("/{strategy_name}/snapshots/{snapshot_id}")
def update_strategy_snapshot(strategy_name: str, snapshot_id: int, update: SnapshotUpdate, db: Session = Depends(get_db)):
    strategy = db.query(Strategy).filter(Strategy.name == strategy_name).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    snapshot = db.query(StrategySnapshot).filter(StrategySnapshot.id == snapshot_id, StrategySnapshot.strategy_id == strategy.id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    snapshot.progress = update.progress
    if update.status is not None:
        snapshot.status = update.status
    db.commit()
    db.refresh(snapshot)
    return snapshot

@router.delete("/{strategy_name}/snapshots/{snapshot_id}")
def delete_strategy_snapshot(strategy_name: str, snapshot_id: int, db: Session = Depends(get_db)):
    """Delete a snapshot and its related orders (cascade)."""
    strategy = db.query(Strategy).filter(Strategy.name == strategy_name).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    snapshot = db.query(StrategySnapshot)\
        .filter(StrategySnapshot.id == snapshot_id, StrategySnapshot.strategy_id == strategy.id)\
        .first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    # Orders are configured with cascade delete on the relationship
    db.delete(snapshot)
    db.commit()
    return {"message": "Snapshot deleted", "snapshot_id": snapshot_id}

class SnapshotCreate(BaseModel):
    status: Optional[str] = "MANUAL"
    cycle: Optional[int] = None
    progress: Optional[Dict[str, Any]] = None

@router.post("/{strategy_name}/snapshots")
def create_strategy_snapshot(strategy_name: str, payload: SnapshotCreate, db: Session = Depends(get_db)):
    """Manually create a snapshot for a strategy.
    If `cycle` is omitted, use latest cycle + 1. Defaults status to MANUAL.
    """
    strategy = db.query(Strategy).filter(Strategy.name == strategy_name).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Determine cycle
    if payload.cycle is None:
        latest = db.query(StrategySnapshot)\
            .filter(StrategySnapshot.strategy_id == strategy.id)\
            .order_by(desc(StrategySnapshot.created_at))\
            .first()
        next_cycle = (latest.cycle + 1) if latest and latest.cycle else 1
    else:
        next_cycle = payload.cycle

    new_snapshot = StrategySnapshot(
        strategy_id=strategy.id,
        status=payload.status or "MANUAL",
        cycle=next_cycle,
        progress=payload.progress or {}
    )
    db.add(new_snapshot)
    db.commit()
    db.refresh(new_snapshot)
    return new_snapshot

# --- Execution Logic ---

def run_strategy_task(strategy_name: str, db: Session):
    print(f"🚀 Starting Background Task for {strategy_name}")
    
    strategy = db.query(Strategy).filter(Strategy.name == strategy_name).first()
    if not strategy:
        print(f"❌ Strategy {strategy_name} not found")
        return

    # Get Account
    # In schema, account_name is stored. We assume it matches account_no for now.
    account = db.query(Account).filter(Account.account_no == strategy.account_name).first()
        
    if not account:
        print(f"❌ Account {strategy.account_name} not found")
        return

    broker = KoreaInvestmentBroker(
        account_no=account.account_no,
        app_key=account.app_key,
        app_secret=account.app_secret
    )

    if strategy.strategy_code == "InfBuy":
        try:
            strat_service = InfBuyStrategy(strategy, broker, db)
            strat_service.execute_daily_routine()
        except Exception as e:
            print(f"❌ Error executing InfBuy: {e}")
            import traceback
            traceback.print_exc()
    elif strategy.strategy_code == "VR":
        try:
            strat_service = VRStrategy(strategy, broker, db)
            strat_service.execute_daily_routine()
        except Exception as e:
            print(f"❌ Error executing VR: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"❌ Unknown strategy code: {strategy.strategy_code}")

@router.post("/start/{strategy_name}")
def start_strategy(strategy_name: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    strategy = db.query(Strategy).filter(Strategy.name == strategy_name).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    if strategy.status != StrategyStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Strategy is not active")

    background_tasks.add_task(run_strategy_task, strategy_name, db)
    
    return {"message": f"Strategy {strategy_name} execution started in background"}

# --- Order Management ---

class OrderUpdate(BaseModel):
    order_status: Optional[str] = None
    order_qty: Optional[int] = None
    order_price: Optional[float] = None
    filled_qty: Optional[int] = None
    filled_price: Optional[float] = None

@router.put("/orders/{order_id}")
def update_order(order_id: str, update: OrderUpdate, db: Session = Depends(get_db)):
    """주문 정보 수정"""
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if update.order_status is not None:
        order.order_status = update.order_status
    if update.order_qty is not None:
        order.order_qty = update.order_qty
    if update.order_price is not None:
        order.order_price = update.order_price
    if update.filled_qty is not None:
        order.filled_qty = update.filled_qty
    if update.filled_price is not None:
        order.filled_price = update.filled_price
    
    db.commit()
    db.refresh(order)
    return order

@router.delete("/orders/{order_id}")
def delete_order(order_id: str, db: Session = Depends(get_db)):
    """주문 삭제"""
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    db.delete(order)
    db.commit()
    return {"message": "Order deleted", "order_id": order_id}
