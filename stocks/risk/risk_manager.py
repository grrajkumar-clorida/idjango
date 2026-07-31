"""
Risk Manager
Manages risk limits and validations
"""
import logging
from decimal import Decimal
from typing import Dict, Tuple
from datetime import date

from stocks.models import LiveTrade, RiskLimits

logger = logging.getLogger(__name__)


class RiskManager:
    """Manages risk limits and validations"""
    
    def __init__(self):
        self.limits = self._load_limits()
    
    def _load_limits(self) -> RiskLimits:
        """Load risk limits from database"""
        limits, _ = RiskLimits.objects.get_or_create(
            id=1,
            defaults={
                'max_position_size': Decimal('100000'),
                'max_portfolio_exposure': Decimal('50.0'),
                'max_daily_loss': Decimal('5000'),
                'max_drawdown': Decimal('10.0')
            }
        )
        return limits
    
    def validate_trade(self, stock_code: str, quantity: int, price: float, 
                      action: str) -> Tuple[bool, str]:
        """
        Validate if trade meets risk criteria
        
        Args:
            stock_code: Stock code
            quantity: Quantity to trade
            price: Price per share
            action: BUY or SELL
        
        Returns:
            Tuple of (is_valid, reason)
        """
        trade_value = quantity * price
        
        # Check position size
        if trade_value > float(self.limits.max_position_size):
            return False, (
                f"Trade value {trade_value:.2f} exceeds max position size "
                f"{self.limits.max_position_size}"
            )
        
        # Check portfolio exposure
        current_exposure = self._calculate_portfolio_exposure()
        portfolio_value = self._get_portfolio_value()
        
        if portfolio_value > 0:
            exposure_percent = (trade_value / portfolio_value) * 100
            new_exposure = current_exposure + exposure_percent
            
            if new_exposure > float(self.limits.max_portfolio_exposure):
                return False, (
                    f"Portfolio exposure would be {new_exposure:.2f}%, "
                    f"exceeds limit {self.limits.max_portfolio_exposure}%"
                )
        
        # Check daily loss
        daily_loss = self._calculate_daily_loss()
        if daily_loss >= float(self.limits.max_daily_loss):
            return False, (
                f"Daily loss limit reached: {daily_loss:.2f} >= "
                f"{self.limits.max_daily_loss}"
            )
        
        # Check drawdown
        drawdown = self._calculate_drawdown()
        if drawdown > float(self.limits.max_drawdown):
            return False, (
                f"Maximum drawdown exceeded: {drawdown:.2f}% > "
                f"{self.limits.max_drawdown}%"
            )
        
        return True, "Trade validated"
    
    def calculate_position_size(self, stock_code: str, price: float, 
                               risk_percent: float = 1.0, 
                               capital: float = None) -> int:
        """
        Calculate position size based on risk
        
        Args:
            stock_code: Stock code
            price: Entry price
            risk_percent: Risk percentage per trade (default 1%)
            capital: Available capital (if None, uses portfolio value)
        
        Returns:
            Quantity to buy
        """
        if capital is None:
            capital = self._get_portfolio_value()
        
        risk_amount = capital * (risk_percent / 100)
        quantity = int(risk_amount / price)
        
        # Ensure within max position size
        max_value = float(self.limits.max_position_size)
        max_quantity = int(max_value / price)
        quantity = min(quantity, max_quantity)
        
        # Minimum 1 share
        return max(1, quantity)
    
    def _calculate_portfolio_exposure(self) -> float:
        """Calculate current portfolio exposure percentage"""
        try:
            open_trades = LiveTrade.objects.filter(status="Executed")
            
            total_exposure = sum(
                float(trade.price) * trade.quantity 
                for trade in open_trades
            )
            
            portfolio_value = self._get_portfolio_value()
            
            if portfolio_value > 0:
                return (total_exposure / portfolio_value) * 100
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating portfolio exposure: {str(e)}")
            return 0.0
    
    def _get_portfolio_value(self) -> float:
        """Get total portfolio value"""
        # This should ideally come from broker API or account balance
        # For now, return a default value
        # TODO: Integrate with broker API to get actual portfolio value
        return 100000.0  # Default value
    
    def _calculate_daily_loss(self) -> float:
        """Calculate today's total loss"""
        try:
            today_trades = LiveTrade.objects.filter(
                timestamp__date=date.today(),
                status="Executed"
            )
            
            total_loss = sum(
                abs(float(trade.profit_loss)) 
                for trade in today_trades 
                if trade.profit_loss and float(trade.profit_loss) < 0
            )
            
            return total_loss
            
        except Exception as e:
            logger.error(f"Error calculating daily loss: {str(e)}")
            return 0.0
    
    def _calculate_drawdown(self) -> float:
        """Calculate maximum drawdown percentage"""
        try:
            # Get all trades
            trades = LiveTrade.objects.filter(status="Executed").order_by('timestamp')
            
            if not trades.exists():
                return 0.0
            
            # Calculate cumulative P/L
            cumulative_pl = []
            running_total = 0.0
            peak = 0.0
            max_drawdown = 0.0
            
            for trade in trades:
                pl = float(trade.profit_loss) if trade.profit_loss else 0.0
                running_total += pl
                cumulative_pl.append(running_total)
                
                if running_total > peak:
                    peak = running_total
                
                drawdown = peak - running_total
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
            
            # Calculate drawdown percentage
            if peak > 0:
                return (max_drawdown / peak) * 100
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating drawdown: {str(e)}")
            return 0.0
    
    def get_current_exposure(self) -> Dict:
        """
        Get current exposure data
        
        Returns:
            Dictionary with exposure information
        """
        try:
            from stocks.models import Orders
            from stocks.utils.timezone_utils import today_indian
            from django.db.models import Sum
            
            # Get open positions (assuming status=0 means open)
            open_positions = Orders.objects.filter(status=0)
            
            # Calculate total exposure
            total_exposure = open_positions.aggregate(
                total=Sum('invested_value')
            )['total'] or 0
            
            # Get portfolio value (default or from settings)
            portfolio_value = self._get_portfolio_value()
            
            # Calculate exposure percentage
            exposure_percent = (float(total_exposure) / portfolio_value * 100) if portfolio_value > 0 else 0
            
            # Calculate daily P/L
            today = today_indian()
            today_trades = Orders.objects.filter(created_at__date=today)
            daily_pl = sum(float(trade.overall_pl or 0) for trade in today_trades)
            
            return {
                'total_exposure': float(total_exposure),
                'exposure_percent': round(exposure_percent, 2),
                'portfolio_value': float(portfolio_value),
                'open_positions_count': open_positions.count(),
                'daily_pl': round(daily_pl, 2),
            }
        except Exception as e:
            logger.error(f"Error getting current exposure: {str(e)}")
            return {
                'total_exposure': 0.0,
                'exposure_percent': 0.0,
                'portfolio_value': 0.0,
                'open_positions_count': 0,
                'daily_pl': 0.0,
            }
    
    def update_limits(self, **kwargs):
        """Update risk limits"""
        for key, value in kwargs.items():
            if hasattr(self.limits, key):
                setattr(self.limits, key, Decimal(str(value)))
        
        self.limits.save()
        logger.info(f"Risk limits updated: {kwargs}")
