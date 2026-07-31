"""
Base Strategy Class
All trading strategies should inherit from this base class
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
import pandas as pd
from datetime import datetime


class BaseStrategy(ABC):
    """Base class for all trading strategies"""
    
    def __init__(self, name: str, enabled: bool = False, **params):
        """
        Initialize strategy
        
        Args:
            name: Strategy name
            enabled: Whether strategy is enabled
            **params: Strategy-specific parameters
        """
        self.name = name
        self.enabled = enabled
        self.params = params
        self.signals = []
        self.created_at = datetime.now()
    
    @abstractmethod
    def generate_signal(self, data: pd.DataFrame, **kwargs) -> Dict[str, Any]:
        """
        Generate trading signal from market data
        
        Args:
            data: DataFrame with OHLCV data
            **kwargs: Additional parameters
        
        Returns:
            Dict with keys:
                - 'action': 'BUY' | 'SELL' | 'HOLD'
                - 'strength': float (0-1, signal strength)
                - 'price': float (entry/exit price)
                - 'stop_loss': float (optional)
                - 'take_profit': float (optional)
                - 'reason': str (reason for signal)
        """
        pass
    
    @abstractmethod
    def validate_signal(self, signal: Dict[str, Any]) -> bool:
        """
        Validate signal before execution
        
        Args:
            signal: Signal dictionary from generate_signal
        
        Returns:
            bool: True if signal is valid
        """
        pass
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get strategy parameters"""
        return self.params
    
    def update_parameters(self, **params):
        """Update strategy parameters"""
        self.params.update(params)
    
    def enable(self):
        """Enable strategy"""
        self.enabled = True
    
    def disable(self):
        """Disable strategy"""
        self.enabled = False
    
    def is_enabled(self) -> bool:
        """Check if strategy is enabled"""
        return self.enabled
    
    def get_signal_history(self) -> list:
        """Get signal history"""
        return self.signals
    
    def add_signal(self, signal: Dict[str, Any]):
        """Add signal to history"""
        signal['timestamp'] = datetime.now()
        signal['strategy'] = self.name
        self.signals.append(signal)
    
    def __str__(self):
        return f"{self.name} ({'Enabled' if self.enabled else 'Disabled'})"
