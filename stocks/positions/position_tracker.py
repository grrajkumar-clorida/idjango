"""
Position Tracker
Tracks and manages open positions
"""
import logging
from typing import Dict, List, Optional
from decimal import Decimal

from stocks.models import LiveTrade
from infra.utils.breeze_client import BreezeAPI

logger = logging.getLogger(__name__)


class PositionTracker:
    """Tracks and manages open positions"""
    
    def __init__(self):
        self.breeze = BreezeAPI()
    
    def get_all_positions(self) -> List[LiveTrade]:
        """Get all open positions"""
        return list(LiveTrade.objects.filter(status="Executed"))
    
    def get_position(self, stock_code: str) -> Optional[LiveTrade]:
        """Get position for a specific stock"""
        return LiveTrade.objects.filter(
            stock_code=stock_code,
            status="Executed"
        ).first()
    
    def update_position_pnl(self, position: LiveTrade, current_price: float):
        """
        Update P/L for a position
        
        Args:
            position: LiveTrade object
            current_price: Current market price
        """
        try:
            entry_price = float(position.price)
            quantity = position.quantity
            
            if position.action == "BUY":
                pnl = (current_price - entry_price) * quantity
            else:  # SELL
                pnl = (entry_price - current_price) * quantity
            
            position.profit_loss = Decimal(str(pnl))
            position.save()
            
            logger.debug(f"Updated P/L for {position.stock_code}: {pnl:.2f}")
            
        except Exception as e:
            logger.error(f"Error updating P/L for {position.stock_code}: {str(e)}")
    
    def update_all_positions_pnl(self):
        """Update P/L for all open positions"""
        positions = self.get_all_positions()
        
        for position in positions:
            try:
                current_price = self._get_current_price(position.stock_code, position.exchange)
                
                if current_price:
                    self.update_position_pnl(position, current_price)
                    
            except Exception as e:
                logger.error(f"Error updating P/L for {position.stock_code}: {str(e)}")
    
    def get_position_summary(self) -> Dict:
        """
        Get summary of all positions
        
        Returns:
            Dict with position summary
        """
        positions = self.get_all_positions()
        
        total_positions = len(positions)
        total_invested = sum(float(p.price) * p.quantity for p in positions)
        total_pnl = sum(float(p.profit_loss) if p.profit_loss else 0 for p in positions)
        
        winning_positions = sum(1 for p in positions if p.profit_loss and float(p.profit_loss) > 0)
        losing_positions = sum(1 for p in positions if p.profit_loss and float(p.profit_loss) < 0)
        
        return {
            'total_positions': total_positions,
            'total_invested': total_invested,
            'total_pnl': total_pnl,
            'winning_positions': winning_positions,
            'losing_positions': losing_positions,
            'positions': [
                {
                    'stock_code': p.stock_code,
                    'quantity': p.quantity,
                    'entry_price': float(p.price),
                    'pnl': float(p.profit_loss) if p.profit_loss else 0
                }
                for p in positions
            ]
        }
    
    def get_current_price(self, stock_code: str, exchange: str) -> Optional[float]:
        """
        Get current market price (public method)
        
        Args:
            stock_code: Stock code
            exchange: Exchange code
        
        Returns:
            Current price or None
        """
        return self._get_current_price(stock_code, exchange)
    
    def _get_current_price(self, stock_code: str, exchange: str) -> Optional[float]:
        """Get current market price"""
        try:
            response = self.breeze.get_live_price(stock_code, exchange)
            
            if response and response.get("Success"):
                data = response["Success"]
                if data:
                    ltp = data[0].get("ltp")
                    if ltp:
                        return float(ltp)
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching price for {stock_code}: {str(e)}")
            return None
