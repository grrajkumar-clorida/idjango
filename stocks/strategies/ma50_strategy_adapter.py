"""
50MA Strategy Adapter for Phase 2
Implements the correct 50MA crossover strategy:
Step 1: Stock should be below 50MA line initially
Step 2: Stock crosses 50MA and closes above 50MA → shortlisted
Step 3: Next day closes above yesterday's close → entry signal
Step 4: Price difference 1-5% → place order
"""
import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from stocks.strategies.base_strategy import BaseStrategy
from data.models import Stocks50MA, StockPriceData
from django.db.models import Q


class MA50StrategyAdapter(BaseStrategy):
    """
    50MA Crossover Strategy Adapter
    """
    
    def __init__(self, enabled: bool = False, **params):
        """
        Initialize 50MA Strategy Adapter
        
        Args:
            enabled: Whether strategy is enabled
            **params: Strategy parameters
                - price_change_min: Minimum price change % (default: 1.0)
                - price_change_max: Maximum price change % (default: 5.0)
        """
        super().__init__(
            name="50MA_Strategy",
            enabled=enabled,
            **params
        )
        self.price_change_min = params.get('price_change_min', 1.0)
        self.price_change_max = params.get('price_change_max', 5.0)
    
    def generate_signal(self, data: pd.DataFrame = None, stock_code: str = None, 
                       exchange: str = "NSE", **kwargs) -> Dict[str, Any]:
        """
        Generate signal for 50MA crossover strategy
        
        Strategy Logic:
        Step 1: Stock should be below 50MA line initially
        Step 2: Stock crosses 50MA and closes above 50MA → shortlisted
        Step 3: Next day closes above yesterday's close → entry signal
        Step 4: Price difference 1-5% → place order
        """
        if not stock_code:
            return {
                'action': 'HOLD',
                'strength': 0.0,
                'reason': 'No stock code provided'
            }
        
        try:
            # Get latest price data (today and yesterday)
            price_data = StockPriceData.objects.filter(
                stock_code=stock_code
            ).order_by('-date')[:2]  # Get last 2 days
            
            if len(price_data) < 2:
                return {
                    'action': 'HOLD',
                    'strength': 0.0,
                    'reason': f'Insufficient price data for {stock_code} (need at least 2 days)'
                }
            
            today_data = price_data[0]  # Most recent
            yesterday_data = price_data[1]  # Previous day
            
            # Get 50MA value (from today's data)
            ma50_value = today_data.live50ma
            if not ma50_value:
                return {
                    'action': 'HOLD',
                    'strength': 0.0,
                    'reason': f'No 50MA value available for {stock_code}'
                }
            
            today_close = today_data.close_price
            yesterday_close = yesterday_data.close_price
            yesterday_ma50 = yesterday_data.live50ma or ma50_value  # Use today's if yesterday's not available
            
            # Step 1: Check if stock was below 50MA previously (need to check 2-3 days back)
            price_history = StockPriceData.objects.filter(
                stock_code=stock_code,
                date__lt=yesterday_data.date
            ).order_by('-date')[:3]
            
            was_below_ma50 = False
            if price_history.exists():
                # Check if any previous day was below 50MA
                for hist in price_history:
                    hist_ma50 = hist.live50ma or ma50_value
                    if hist.close_price < hist_ma50:
                        was_below_ma50 = True
                        break
            
            # Step 2: Check if stock crossed and closed above 50MA
            crossed_above = False
            if yesterday_close > yesterday_ma50:
                # Check if previous day was below 50MA
                if price_history.exists():
                    prev_day = price_history[0]
                    prev_ma50 = prev_day.live50ma or ma50_value
                    if prev_day.close_price < prev_ma50:
                        crossed_above = True
                else:
                    # If no history, assume it crossed if was_below_ma50
                    crossed_above = was_below_ma50
            
            # Step 3: Check if today closes above yesterday's close
            closes_above_yesterday = today_close > yesterday_close
            
            # Step 4: Check price difference percentage
            price_change_percent = ((today_close - yesterday_close) / yesterday_close) * 100
            
            # Validate all conditions
            conditions_met = []
            reasons = []
            
            if not was_below_ma50 and not crossed_above:
                reasons.append("Stock was not below 50MA initially")
            else:
                conditions_met.append("Was below 50MA")
            
            if not crossed_above:
                reasons.append(f"Stock did not cross above 50MA (yesterday: {yesterday_close:.2f} vs MA50: {yesterday_ma50:.2f})")
            else:
                conditions_met.append("Crossed above 50MA")
            
            if not closes_above_yesterday:
                reasons.append(f"Today's close ({today_close:.2f}) not above yesterday's close ({yesterday_close:.2f})")
            else:
                conditions_met.append("Today closes above yesterday")
            
            if price_change_percent < self.price_change_min:
                reasons.append(f"Price change {price_change_percent:.2f}% is below minimum {self.price_change_min}%")
            elif price_change_percent > self.price_change_max:
                reasons.append(f"Price change {price_change_percent:.2f}% exceeds maximum {self.price_change_max}%")
            else:
                conditions_met.append(f"Price change {price_change_percent:.2f}% is in range {self.price_change_min}-{self.price_change_max}%")
            
            # Generate signal if all conditions met
            if len(conditions_met) == 4:
                # Calculate stop loss (1% below 50MA)
                stop_loss = ma50_value * 0.99
                
                # Calculate take profit (10% above entry)
                take_profit = today_close * 1.10
                
                # Signal strength based on price change (closer to middle = stronger)
                middle_range = (self.price_change_min + self.price_change_max) / 2
                strength = 1.0 - abs(price_change_percent - middle_range) / (self.price_change_max - self.price_change_min)
                strength = max(0.6, min(1.0, strength))
                
                return {
                    'action': 'BUY',
                    'strength': strength,
                    'price': today_close,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'reason': f"50MA Entry: Crossed above 50MA ({ma50_value:.2f}), Today close {today_close:.2f} > Yesterday {yesterday_close:.2f}, Change {price_change_percent:.2f}%",
                    'strategy_name': '50MA_Strategy',
                    'metadata': {
                        'stock_code': stock_code,
                        '50ma_value': ma50_value,
                        'today_close': today_close,
                        'yesterday_close': yesterday_close,
                        'price_change_percent': price_change_percent,
                        'conditions_met': conditions_met
                    }
                }
            
            # Return HOLD with reason
            return {
                'action': 'HOLD',
                'strength': 0.3 if len(conditions_met) >= 2 else 0.0,
                'reason': '; '.join(reasons) if reasons else 'Entry conditions not met',
                'metadata': {
                    'stock_code': stock_code,
                    'today_close': today_close,
                    'yesterday_close': yesterday_close,
                    '50ma_value': ma50_value,
                    'price_change_percent': price_change_percent,
                    'conditions_met': conditions_met,
                    'conditions_failed': reasons
                }
            }
            
        except Exception as e:
            import traceback
            return {
                'action': 'HOLD',
                'strength': 0.0,
                'reason': f'Error generating signal: {str(e)}',
                'metadata': {'error': traceback.format_exc()}
            }
    
    def validate_signal(self, signal: Dict[str, Any]) -> bool:
        """
        Validate 50MA crossover signal
        
        Valid signals must:
        1. Have action BUY
        2. Have strength > 0.5
        3. Have valid price
        4. Have metadata with stock_code
        5. Have price_change_percent in valid range (1-5%)
        """
        if signal.get('action') != 'BUY':
            return False
        
        if signal.get('strength', 0) < 0.5:
            return False
        
        if not signal.get('price') or signal.get('price') <= 0:
            return False
        
        metadata = signal.get('metadata', {})
        if not metadata.get('stock_code'):
            return False
        
        # Check price change percentage is in valid range
        price_change_percent = metadata.get('price_change_percent')
        if price_change_percent:
            if price_change_percent < self.price_change_min or price_change_percent > self.price_change_max:
                return False
        
        # Check all conditions were met
        conditions_met = metadata.get('conditions_met', [])
        if len(conditions_met) < 4:
            return False
        
        return True
    
    def get_stocks_to_check(self) -> list:
        """
        Get list of stock codes to check for signals
        Returns stocks that have crossed above 50MA (status 6, 7, or 8)
        """
        stocks = Stocks50MA.objects.filter(
            status__gte=6  # Status 6+ means crossed above 50MA
        ).values_list('stock_code', flat=True).distinct()
        
        return list(stocks)
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Get strategy information"""
        return {
            'name': self.name,
            'description': '50-day Moving Average Crossover Strategy - Entry after crossing above 50MA',
            'entry_conditions': [
                'Step 1: Stock should be below 50MA line initially',
                'Step 2: Stock crosses 50MA and closes above 50MA → shortlisted',
                'Step 3: Next day closes above yesterday\'s close → entry signal',
                f'Step 4: Price difference {self.price_change_min}-{self.price_change_max}% → place order'
            ],
            'exit_conditions': [
                'Profit 8-10%: Full exit',
                'Stop loss: 1% below 50MA'
            ],
            'parameters': {
                'price_change_min': self.price_change_min,
                'price_change_max': self.price_change_max,
            }
        }
