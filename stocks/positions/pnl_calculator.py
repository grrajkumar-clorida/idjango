"""
P/L Calculator
Calculates profit and loss for positions
"""
import logging
from typing import Dict, List
from decimal import Decimal

from stocks.models import LiveTrade

logger = logging.getLogger(__name__)


class PnLCalculator:
    """Calculates profit and loss"""
    
    @staticmethod
    def calculate_pnl(entry_price: float, current_price: float, 
                     quantity: int, action: str) -> float:
        """
        Calculate P/L for a position
        
        Args:
            entry_price: Entry price
            current_price: Current price
            quantity: Quantity
            action: BUY or SELL
        
        Returns:
            P/L amount
        """
        if action == "BUY":
            return (current_price - entry_price) * quantity
        else:  # SELL
            return (entry_price - current_price) * quantity
    
    @staticmethod
    def calculate_pnl_percent(entry_price: float, current_price: float, 
                            action: str) -> float:
        """
        Calculate P/L percentage
        
        Args:
            entry_price: Entry price
            current_price: Current price
            action: BUY or SELL
        
        Returns:
            P/L percentage
        """
        if entry_price == 0:
            return 0.0
        
        if action == "BUY":
            return ((current_price - entry_price) / entry_price) * 100
        else:  # SELL
            return ((entry_price - current_price) / entry_price) * 100
    
    @staticmethod
    def calculate_total_pnl(positions: List[LiveTrade]) -> Dict:
        """
        Calculate total P/L for multiple positions
        
        Args:
            positions: List of LiveTrade objects
        
        Returns:
            Dict with P/L summary
        """
        total_pnl = 0.0
        total_invested = 0.0
        winning_trades = 0
        losing_trades = 0
        
        for position in positions:
            invested = float(position.price) * position.quantity
            total_invested += invested
            
            pnl = float(position.profit_loss) if position.profit_loss else 0.0
            total_pnl += pnl
            
            if pnl > 0:
                winning_trades += 1
            elif pnl < 0:
                losing_trades += 1
        
        win_rate = (winning_trades / len(positions) * 100) if positions else 0
        
        return {
            'total_pnl': total_pnl,
            'total_invested': total_invested,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'roi': (total_pnl / total_invested * 100) if total_invested > 0 else 0
        }
    
    @staticmethod
    def calculate_daily_pnl(date=None) -> Dict:
        """
        Calculate daily P/L
        
        Args:
            date: Date to calculate for (default: today)
        
        Returns:
            Dict with daily P/L summary
        """
        from datetime import date as date_class
        
        if date is None:
            date = date_class.today()
        
        trades = LiveTrade.objects.filter(
            timestamp__date=date,
            status__in=["Executed", "Closed"]
        )
        
        return PnLCalculator.calculate_total_pnl(list(trades))
