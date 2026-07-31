"""
Exposure Limiter
Manages portfolio exposure limits
"""
import logging
from typing import Dict, List
from decimal import Decimal

from stocks.models import LiveTrade

logger = logging.getLogger(__name__)


class ExposureLimiter:
    """Manages portfolio exposure limits"""
    
    def __init__(self, max_exposure_percent: float = 50.0):
        """
        Initialize exposure limiter
        
        Args:
            max_exposure_percent: Maximum portfolio exposure percentage
        """
        self.max_exposure_percent = max_exposure_percent
    
    def check_exposure(self, portfolio_value: float, 
                     new_trade_value: float = 0) -> Dict:
        """
        Check current portfolio exposure
        
        Args:
            portfolio_value: Total portfolio value
            new_trade_value: Value of new trade to add
        
        Returns:
            Dict with exposure information
        """
        try:
            open_trades = LiveTrade.objects.filter(status="Executed")
            
            current_exposure = sum(
                float(trade.price) * trade.quantity 
                for trade in open_trades
            )
            
            total_exposure = current_exposure + new_trade_value
            
            exposure_percent = (total_exposure / portfolio_value * 100) if portfolio_value > 0 else 0
            
            is_within_limit = exposure_percent <= self.max_exposure_percent
            
            return {
                'current_exposure': current_exposure,
                'total_exposure': total_exposure,
                'exposure_percent': exposure_percent,
                'max_exposure_percent': self.max_exposure_percent,
                'is_within_limit': is_within_limit,
                'available_exposure': (self.max_exposure_percent / 100) * portfolio_value - current_exposure
            }
            
        except Exception as e:
            logger.error(f"Error checking exposure: {str(e)}")
            return {
                'current_exposure': 0,
                'total_exposure': 0,
                'exposure_percent': 0,
                'max_exposure_percent': self.max_exposure_percent,
                'is_within_limit': False,
                'available_exposure': 0
            }
    
    def can_add_position(self, portfolio_value: float, 
                        trade_value: float) -> bool:
        """
        Check if new position can be added
        
        Args:
            portfolio_value: Total portfolio value
            trade_value: Value of new trade
        
        Returns:
            True if position can be added
        """
        exposure_info = self.check_exposure(portfolio_value, trade_value)
        return exposure_info['is_within_limit']
    
    def get_max_trade_value(self, portfolio_value: float) -> float:
        """
        Get maximum trade value allowed
        
        Args:
            portfolio_value: Total portfolio value
        
        Returns:
            Maximum trade value
        """
        exposure_info = self.check_exposure(portfolio_value)
        return max(0, exposure_info['available_exposure'])
