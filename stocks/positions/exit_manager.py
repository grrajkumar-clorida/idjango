"""
Exit Manager
Manages position exits (stop-loss, take-profit, trailing stops)
"""
import logging
from typing import Dict, Optional
from decimal import Decimal

from stocks.models import LiveTrade
from infra.utils.breeze_client import BreezeAPI

logger = logging.getLogger(__name__)


class ExitManager:
    """Manages position exits"""
    
    def __init__(self):
        self.breeze = BreezeAPI()
    
    def check_stop_loss(self, position: LiveTrade, current_price: float) -> bool:
        """
        Check if stop-loss should be triggered
        
        Args:
            position: LiveTrade object
            current_price: Current market price
        
        Returns:
            True if stop-loss should be triggered
        """
        if not position.stop_loss:
            return False
        
        entry_price = float(position.price)
        stop_loss = float(position.stop_loss)
        
        if position.action == "BUY":
            return current_price <= stop_loss
        else:  # SELL
            return current_price >= stop_loss
    
    def check_take_profit(self, position: LiveTrade, current_price: float) -> bool:
        """
        Check if take-profit should be triggered
        
        Args:
            position: LiveTrade object
            current_price: Current market price
        
        Returns:
            True if take-profit should be triggered
        """
        if not position.take_profit:
            return False
        
        entry_price = float(position.price)
        take_profit = float(position.take_profit)
        
        if position.action == "BUY":
            return current_price >= take_profit
        else:  # SELL
            return current_price <= take_profit
    
    def check_trailing_stop_loss(self, position: LiveTrade, current_price: float) -> Dict:
        """
        Check and update trailing stop-loss
        
        Args:
            position: LiveTrade object
            current_price: Current market price
        
        Returns:
            Dict with update information
        """
        if not position.trailing_stop_loss or not position.tsl_percentage:
            return {'updated': False}
        
        entry_price = float(position.price)
        current_tsl = float(position.trailing_stop_loss)
        tsl_percent = float(position.tsl_percentage)
        
        updated = False
        new_tsl = current_tsl
        
        if position.action == "BUY":
            # Calculate new TSL
            new_tsl_value = current_price - (current_price * (tsl_percent / 100))
            
            # TSL can only move up
            if new_tsl_value > current_tsl:
                new_tsl = new_tsl_value
                updated = True
        
        else:  # SELL
            # Calculate new TSL
            new_tsl_value = current_price + (current_price * (tsl_percent / 100))
            
            # TSL can only move down
            if new_tsl_value < current_tsl:
                new_tsl = new_tsl_value
                updated = True
        
        if updated:
            position.trailing_stop_loss = Decimal(str(new_tsl))
            position.save()
            logger.info(f"Updated TSL for {position.stock_code}: {new_tsl:.2f}")
        
        return {
            'updated': updated,
            'new_tsl': new_tsl,
            'should_exit': self._check_tsl_exit(position, current_price, new_tsl)
        }
    
    def _check_tsl_exit(self, position: LiveTrade, current_price: float, tsl: float) -> bool:
        """Check if TSL exit should be triggered"""
        if position.action == "BUY":
            return current_price <= tsl
        else:  # SELL
            return current_price >= tsl
    
    def execute_exit(self, position: LiveTrade, exit_reason: str, 
                    quantity: Optional[int] = None) -> Dict:
        """
        Execute exit for a position
        
        Args:
            position: LiveTrade object
            exit_reason: Reason for exit
            quantity: Quantity to exit (None for full exit)
        
        Returns:
            Dict with exit result
        """
        if quantity is None:
            quantity = position.quantity
        
        exit_action = "SELL" if position.action == "BUY" else "BUY"
        
        try:
            response = self.breeze.place_order(
                stock_code=position.stock_code,
                exchange=position.exchange,
                quantity=quantity,
                order_type="MARKET",
                price=0,
                product="cash",
                action=exit_action
            )
            
            if response.get("Status") == "Success" or response.get("Status") == 200:
                order_id = response.get("order_id") or response.get("Success", {}).get("order_id", "")
                
                # Update position
                if quantity >= position.quantity:
                    position.status = "Closed"
                else:
                    position.quantity -= quantity
                
                position.save()
                
                logger.info(f"Exit executed for {position.stock_code}: {exit_reason}")
                
                return {
                    'success': True,
                    'order_id': order_id,
                    'quantity': quantity,
                    'exit_reason': exit_reason
                }
            else:
                error_msg = response.get("ErrorMessage", "Unknown error")
                logger.error(f"Exit order failed for {position.stock_code}: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except Exception as e:
            logger.error(f"Exception executing exit for {position.stock_code}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def check_profit_range(self, position: LiveTrade, current_price: float, 
                          min_profit: float = 6.0, max_profit: float = 12.0) -> Dict:
        """
        Check if profit is in specified range (for 50MA strategy: 6-12%)
        
        Args:
            position: LiveTrade object
            current_price: Current market price
            min_profit: Minimum profit percentage (default: 6.0)
            max_profit: Maximum profit percentage (default: 12.0)
        
        Returns:
            Dict with 'in_range': bool, 'profit_percent': float, 'should_exit': bool
        """
        entry_price = float(position.price)
        
        if position.action == "BUY":
            profit_percent = ((current_price - entry_price) / entry_price) * 100
        else:  # SELL
            profit_percent = ((entry_price - current_price) / entry_price) * 100
        
        in_range = min_profit <= profit_percent <= max_profit
        
        return {
            'in_range': in_range,
            'profit_percent': profit_percent,
            'should_exit': in_range,
            'exit_type': 'full' if in_range else None
        }
    
    def check_bottom_value(self, position: LiveTrade, current_price: float, 
                          ma50_value: Optional[float] = None) -> Dict:
        """
        Check if stock is at bottom value (for 50MA strategy)
        Bottom value: Price is close to 50MA (within 1-2% above 50MA)
        
        Args:
            position: LiveTrade object
            current_price: Current market price
            ma50_value: 50MA value (optional)
        
        Returns:
            Dict with 'is_bottom': bool, 'should_partial_exit': bool
        """
        if not ma50_value:
            return {'is_bottom': False, 'should_partial_exit': False}
        
        # Calculate how close price is to 50MA
        distance_from_ma50 = ((current_price - ma50_value) / ma50_value) * 100
        
        # Bottom value: Price is 1-2% above 50MA
        is_bottom = 1.0 <= distance_from_ma50 <= 2.0
        
        # Check if we have profit (need profit to book)
        entry_price = float(position.price)
        if position.action == "BUY":
            profit_percent = ((current_price - entry_price) / entry_price) * 100
        else:
            profit_percent = ((entry_price - current_price) / entry_price) * 100
        
        # Partial exit if at bottom AND has profit
        should_partial_exit = is_bottom and profit_percent > 0
        
        return {
            'is_bottom': is_bottom,
            'should_partial_exit': should_partial_exit,
            'distance_from_ma50': distance_from_ma50,
            'profit_percent': profit_percent,
            'exit_type': 'partial' if should_partial_exit else None,
            'exit_percent': 50.0 if should_partial_exit else 0.0
        }
    
    def execute_partial_exit(self, position: LiveTrade, exit_reason: str, 
                            exit_percent: float = 50.0) -> Dict:
        """
        Execute partial exit (e.g., 50% of position)
        
        Args:
            position: LiveTrade object
            exit_reason: Reason for exit
            exit_percent: Percentage of position to exit (default: 50%)
        
        Returns:
            Dict with exit result
        """
        # Calculate quantity to exit
        exit_quantity = int((position.quantity * exit_percent) / 100)
        
        # Minimum 1 share
        exit_quantity = max(1, exit_quantity)
        
        # Don't exit more than available
        exit_quantity = min(exit_quantity, position.quantity)
        
        return self.execute_exit(position, exit_reason, quantity=exit_quantity)
    
    def monitor_exits(self, position: LiveTrade, current_price: float, 
                     strategy_name: Optional[str] = None, **kwargs) -> Optional[Dict]:
        """
        Monitor position for exit conditions
        
        Args:
            position: LiveTrade object
            current_price: Current market price
            strategy_name: Strategy name (for strategy-specific exits)
            **kwargs: Additional parameters (e.g., ma50_value for 50MA strategy)
        
        Returns:
            Exit dict if exit should be executed, None otherwise
        """
        # Strategy-specific exit logic
        if strategy_name == "50MA_Strategy":
            # Check 6-12% profit range (full exit)
            profit_check = self.check_profit_range(position, current_price, 6.0, 12.0)
            if profit_check['should_exit']:
                return self.execute_exit(
                    position, 
                    f"Profit {profit_check['profit_percent']:.2f}% in range 6-12%"
                )
            
            # Check bottom value (50% partial exit)
            ma50_value = kwargs.get('ma50_value')
            if ma50_value:
                bottom_check = self.check_bottom_value(position, current_price, ma50_value)
                if bottom_check['should_partial_exit']:
                    return self.execute_partial_exit(
                        position,
                        f"Bottom value exit: {bottom_check['profit_percent']:.2f}% profit, {bottom_check['distance_from_ma50']:.2f}% above 50MA",
                        exit_percent=50.0
                    )
        
        # Standard exit checks
        # Check stop-loss
        if self.check_stop_loss(position, current_price):
            return self.execute_exit(position, "Stop-loss triggered")
        
        # Check take-profit
        if self.check_take_profit(position, current_price):
            return self.execute_exit(position, "Take-profit triggered")
        
        # Check trailing stop-loss
        tsl_result = self.check_trailing_stop_loss(position, current_price)
        if tsl_result.get('should_exit'):
            return self.execute_exit(position, "Trailing stop-loss triggered")
        
        return None
