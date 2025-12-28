from enum import Enum
import enum

class StrategyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    TERMINATED = "TERMINATED"

class OrderStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    UNFILLED = "UNFILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

class OrderType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class RequestOutcome(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"

class SnapshotStatus(str, Enum):
    INIT = "INIT"
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"