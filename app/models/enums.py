import enum

class StrategyStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    TERMINATED = "TERMINATED"

class OrderStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    UNFILLED = "UNFILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

class OrderType(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"

class RequestOutcome(str, enum.Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"

class SnapshotStatus(str, enum.Enum):
    INIT = "INIT"
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"