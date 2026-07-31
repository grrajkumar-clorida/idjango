"""
Position Sizer
Calculates optimal position sizes based on various methods
"""
import logging
from typing import Dict, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class PositionSizer:
    """Calculates position sizes using different methods"""
    
    @staticmethod
    def fixed_size(price: float, fixed_amount: float) -> int:
        """
        Fixed position size
        
        Args:
            price: Entry price
            fixed_amount: Fixed amount to invest
        
        Returns:
            Quantity
        """
        return int(fixed_amount / price)
    
    @staticmethod
    def risk_percent(price: float, capital: float, risk_percent: float = 1.0) -> int:
        """
        Position size based on risk percentage
        
        Args:
            price: Entry price
            capital: Available capital
            risk_percent: Risk percentage (default 1%)
        
        Returns:
            Quantity
        """
        risk_amount = capital * (risk_percent / 100)
        return int(risk_amount / price)
    
    @staticmethod
    def volatility_based(price: float, capital: float, atr: float, 
                        risk_percent: float = 1.0) -> int:
        """
        Position size based on volatility (ATR)
        
        Args:
            price: Entry price
            capital: Available capital
            atr: Average True Range
            risk_percent: Risk percentage
        
        Returns:
            Quantity
        """
        if atr <= 0:
            return PositionSizer.risk_percent(price, capital, risk_percent)
        
        risk_amount = capital * (risk_percent / 100)
        # Position size = Risk Amount / ATR
        quantity = int(risk_amount / atr)
        
        # Convert to shares (notional value)
        notional_value = quantity * price
        
        # Ensure we don't exceed capital
        if notional_value > capital:
            quantity = int(capital / price)
        
        return max(1, quantity)
    
    @staticmethod
    def kelly_criterion(win_rate: float, avg_win: float, avg_loss: float, 
                       capital: float, price: float) -> int:
        """
        Position size using Kelly Criterion
        
        Args:
            win_rate: Win rate (0-1)
            avg_win: Average winning trade amount
            avg_loss: Average losing trade amount (positive value)
            capital: Available capital
            price: Entry price
        
        Returns:
            Quantity
        """
        if avg_loss <= 0:
            return 1
        
        # Kelly percentage
        kelly_pct = win_rate - ((1 - win_rate) / (avg_win / avg_loss))
        
        # Limit to 25% max (fractional Kelly)
        kelly_pct = min(kelly_pct, 0.25)
        
        if kelly_pct <= 0:
            return 1
        
        position_value = capital * kelly_pct
        return int(position_value / price)
    
    @staticmethod
    def calculate_atr(data: pd.DataFrame, period: int = 14) -> float:
        """
        Calculate Average True Range
        
        Args:
            data: DataFrame with OHLC data
            period: Period for ATR calculation
        
        Returns:
            ATR value
        """
        try:
            high = data['high']
            low = data['low']
            close = data['close']
            
            # True Range
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            # ATR
            atr = tr.rolling(window=period).mean().iloc[-1]
            
            return float(atr) if pd.notna(atr) else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating ATR: {str(e)}")
            return 0.0
