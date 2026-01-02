from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class BaseBroker(ABC):
    """
    Abstract Base Class for Broker API.
    All broker implementations (KIS, etc.) must inherit from this.
    """
    
    @abstractmethod
    def get_balance(self) -> Dict[str, Any]:
        """Get account balance."""
        pass

    @abstractmethod
    def get_price(self, ticker: str) -> Dict[str, Any]:
        """Get current price of a ticker."""
        pass

    @abstractmethod
    def buy_order(self, ticker: str, quantity: int, price: float, order_type: str = "00") -> Dict[str, Any]:
        """Place a buy order."""
        pass

    @abstractmethod
    def sell_order(self, ticker: str, quantity: int, price: float, order_type: str = "00") -> Dict[str, Any]:
        """Place a sell order."""
        pass

    @abstractmethod
    def get_transaction_history(self, ticker: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Get transaction history."""
        pass
    @abstractmethod
    def parse_order_response(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw order response from broker into standardized format."""
        pass
    @abstractmethod
    def parse_balance_response(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw balance response from broker into standardized format."""
        pass
    @abstractmethod
    def parse_price_response(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw price response from broker into standardized format."""
        pass
    @abstractmethod
    def parse_history_response(self, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse raw transaction history response from broker into standardized format."""
        pass
    @abstractmethod
    def cancel_order_response(self, order_id: str) -> Dict[str, Any]:
        """Cancel an existing order."""
        pass