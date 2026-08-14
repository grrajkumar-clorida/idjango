"""
Strategy Registry
Centralized strategy management and registration
"""
import logging
from typing import Dict, List, Optional
from django.utils import timezone

from stocks.strategies.base_strategy import BaseStrategy
from stocks.models import Strategy

logger = logging.getLogger(__name__)


class StrategyRegistry:
    """Centralized registry for all trading strategies"""
    
    def __init__(self):
        self.strategies: Dict[str, BaseStrategy] = {}
        self._load_from_database()
    
    def _load_from_database(self):
        """Load strategies from database"""
        try:
            db_strategies = Strategy.objects.filter(enabled=True)
            
            for db_strategy in db_strategies:
                try:
                    strategy_instance = self._create_strategy_instance(db_strategy)
                    if strategy_instance:
                        self.strategies[db_strategy.name] = strategy_instance
                        logger.info(f"Loaded strategy: {db_strategy.name}")
                except Exception as e:
                    logger.error(f"Error loading strategy {db_strategy.name}: {e}")
        
        except Exception as e:
            logger.error(f"Error loading strategies from database: {e}")
    
    def _create_strategy_instance(self, db_strategy: Strategy) -> Optional[BaseStrategy]:
        """
        Create strategy instance from database record
        
        Args:
            db_strategy: Strategy model instance
        
        Returns:
            Strategy instance or None
        """
        strategy_name = db_strategy.name

        # Path A (data.tasks + 5-6% MA50Strategy) owns 50MA. Do not load the
        # crossover adapter (1-5%) into Path B beat/registry.
        from data.strategies.ma50_strategy import PATH_A_STRATEGY_NAME
        if strategy_name == PATH_A_STRATEGY_NAME:
            logger.info(
                "Skipping %s in Path B registry — owned by data.tasks",
                strategy_name,
            )
            return None
        
        # Map strategy names to their classes
        # elif strategy_name == "RSI_Strategy":
        #     from stocks.strategies.rsi_strategy import RSIStrategy
        #     return RSIStrategy(enabled=True, **db_strategy.parameters)
        
        logger.warning(f"Strategy adapter not found for: {strategy_name}")
        return None
    
    def register(self, strategy: BaseStrategy):
        """
        Register a strategy instance
        
        Args:
            strategy: Strategy instance
        """
        if not isinstance(strategy, BaseStrategy):
            raise ValueError("Strategy must inherit from BaseStrategy")
        
        self.strategies[strategy.name] = strategy
        logger.info(f"Registered strategy: {strategy.name}")
    
    def unregister(self, strategy_name: str):
        """
        Unregister a strategy
        
        Args:
            strategy_name: Name of strategy to unregister
        """
        if strategy_name in self.strategies:
            del self.strategies[strategy_name]
            logger.info(f"Unregistered strategy: {strategy_name}")
    
    def get(self, strategy_name: str) -> Optional[BaseStrategy]:
        """
        Get strategy by name
        
        Args:
            strategy_name: Strategy name
        
        Returns:
            Strategy instance or None
        """
        return self.strategies.get(strategy_name)
    
    def get_all(self) -> List[BaseStrategy]:
        """
        Get all registered strategies
        
        Returns:
            List of strategy instances
        """
        return list(self.strategies.values())
    
    def get_enabled(self) -> List[BaseStrategy]:
        """
        Get all enabled strategies
        
        Returns:
            List of enabled strategy instances
        """
        return [s for s in self.strategies.values() if s.is_enabled()]
    
    def list_names(self) -> List[str]:
        """
        List all registered strategy names
        
        Returns:
            List of strategy names
        """
        return list(self.strategies.keys())
    
    def refresh(self):
        """Reload strategies from database"""
        self.strategies.clear()
        self._load_from_database()
        logger.info("Strategy registry refreshed")
    
    def get_strategy_info(self, strategy_name: str) -> Optional[Dict]:
        """
        Get information about a strategy
        
        Args:
            strategy_name: Strategy name
        
        Returns:
            Strategy info dict or None
        """
        strategy = self.get(strategy_name)
        if not strategy:
            return None
        
        # Get database record
        try:
            db_strategy = Strategy.objects.get(name=strategy_name)
            return {
                'name': strategy.name,
                'enabled': strategy.is_enabled(),
                'parameters': db_strategy.parameters,
                'description': db_strategy.description,
                'created_at': db_strategy.created_at,
                'updated_at': db_strategy.updated_at,
                'signal_count': db_strategy.signals.count(),
                'info': strategy.get_strategy_info() if hasattr(strategy, 'get_strategy_info') else {}
            }
        except Strategy.DoesNotExist:
            return {
                'name': strategy.name,
                'enabled': strategy.is_enabled(),
                'parameters': strategy.get_parameters(),
                'description': 'No database record',
                'info': strategy.get_strategy_info() if hasattr(strategy, 'get_strategy_info') else {}
            }
    
    def get_all_strategies_info(self) -> List[Dict]:
        """
        Get information about all strategies
        
        Returns:
            List of strategy info dicts
        """
        return [self.get_strategy_info(name) for name in self.list_names()]
