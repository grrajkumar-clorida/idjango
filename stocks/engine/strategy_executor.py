"""
Strategy Executor
Executes strategies and generates signals
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd

from stocks.strategies.base_strategy import BaseStrategy
from stocks.models import Stock, StockPrice
from infra.utils.breeze_client import BreezeAPI

logger = logging.getLogger(__name__)


class StrategyExecutor:
    """Executes strategies and generates signals"""
    
    def __init__(self):
        self.strategies: Dict[str, BaseStrategy] = {}
        self.breeze = BreezeAPI()
    
    def register_strategy(self, strategy: BaseStrategy):
        """
        Register a strategy
        
        Args:
            strategy: Strategy instance
        """
        if not isinstance(strategy, BaseStrategy):
            raise ValueError("Strategy must inherit from BaseStrategy")
        
        self.strategies[strategy.name] = strategy
        logger.info(f"Registered strategy: {strategy.name}")
    
    def unregister_strategy(self, strategy_name: str):
        """Unregister a strategy"""
        if strategy_name in self.strategies:
            del self.strategies[strategy_name]
            logger.info(f"Unregistered strategy: {strategy_name}")
    
    def get_strategy(self, strategy_name: str) -> Optional[BaseStrategy]:
        """Get strategy by name"""
        return self.strategies.get(strategy_name)
    
    def list_strategies(self) -> List[str]:
        """List all registered strategy names"""
        return list(self.strategies.keys())
    
    def list_enabled_strategies(self) -> List[BaseStrategy]:
        """List all enabled strategies"""
        return [s for s in self.strategies.values() if s.is_enabled()]
    
    def execute_strategy(self, strategy_name: str, stock_code: str, 
                        exchange: str = "NSE", **kwargs) -> Optional[Dict]:
        """
        Execute a strategy for a given stock
        
        Args:
            strategy_name: Name of the strategy
            stock_code: Stock code/symbol
            exchange: Exchange code (default: NSE)
            **kwargs: Additional parameters for strategy
        
        Returns:
            Signal dict if generated, None otherwise
        """
        if strategy_name not in self.strategies:
            logger.warning(f"Strategy {strategy_name} not found")
            return None
        
        strategy = self.strategies[strategy_name]
        
        if not strategy.is_enabled():
            logger.debug(f"Strategy {strategy_name} is disabled")
            return None
        
        try:
            # Fetch market data
            data = self._get_market_data(stock_code, exchange, **kwargs)
            
            if data is None or data.empty:
                logger.warning(f"No data available for {stock_code}")
                return None
            
            # Generate signal
            signal = strategy.generate_signal(data, **kwargs)
            
            if not signal:
                return None
            
            # Validate signal
            if not strategy.validate_signal(signal):
                logger.debug(f"Signal validation failed for {strategy_name} - {stock_code}")
                return None
            
            # Add to signal history
            strategy.add_signal(signal)
            
            logger.info(f"Signal generated: {strategy_name} - {stock_code} - {signal.get('action')}")
            
            return signal
            
        except Exception as e:
            logger.error(f"Error executing strategy {strategy_name} for {stock_code}: {str(e)}")
            return None
    
    def execute_all_strategies(self, stock_code: str, exchange: str = "NSE", **kwargs) -> List[Dict]:
        """
        Execute all enabled strategies for a stock
        
        Args:
            stock_code: Stock code/symbol
            exchange: Exchange code
            **kwargs: Additional parameters
        
        Returns:
            List of signals from all strategies
        """
        signals = []
        
        for strategy_name in self.list_strategies():
            signal = self.execute_strategy(strategy_name, stock_code, exchange, **kwargs)
            if signal:
                signals.append(signal)
        
        return signals
    
    def _get_market_data(self, stock_code: str, exchange: str, 
                        days: int = 200, **kwargs) -> Optional[pd.DataFrame]:
        """
        Get market data for a stock
        
        Args:
            stock_code: Stock code
            exchange: Exchange code
            days: Number of days of historical data
            **kwargs: Additional parameters
        
        Returns:
            DataFrame with OHLCV data
        """
        try:
            # Try to get from database first
            stock = Stock.objects.filter(stock_code=stock_code).first()
            
            if stock:
                prices = StockPrice.objects.filter(stock=stock).order_by('-date')[:days]
                
                if prices.exists():
                    data = []
                    for price in reversed(prices):  # Oldest first
                        data.append({
                            'date': price.date,
                            'open': price.open_price,
                            'high': price.high_price,
                            'low': price.low_price,
                            'close': price.close_price,
                            'volume': price.volume
                        })
                    
                    df = pd.DataFrame(data)
                    df.set_index('date', inplace=True)
                    return df
            
            # Fallback to Breeze API if database doesn't have data
            from datetime import datetime, timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            response = self.breeze.get_historical_data(
                stock_code=stock_code,
                exchange=exchange,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d'),
                interval="1day"
            )
            
            if response and response.get("Success"):
                data = response["Success"]
                df_data = []
                for item in data:
                    df_data.append({
                        'date': pd.to_datetime(item.get('datetime')),
                        'open': float(item.get('open', 0)),
                        'high': float(item.get('high', 0)),
                        'low': float(item.get('low', 0)),
                        'close': float(item.get('close', 0)),
                        'volume': int(item.get('volume', 0))
                    })
                
                df = pd.DataFrame(df_data)
                df.set_index('date', inplace=True)
                return df
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching market data for {stock_code}: {str(e)}")
            return None
