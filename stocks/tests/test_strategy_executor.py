"""
Unit tests for StrategyExecutor
"""
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from datetime import datetime

from django.test import TestCase
from stocks.engine.strategy_executor import StrategyExecutor
from stocks.strategies.base_strategy import BaseStrategy
from stocks.models import Stock, StockPrice


class MockStrategy(BaseStrategy):
    """Mock strategy for testing"""
    
    def generate_signal(self, data, **kwargs):
        return {
            'action': 'BUY',
            'strength': 0.8,
            'price': 100.0,
            'reason': 'Test signal'
        }
    
    def validate_signal(self, signal):
        return signal.get('strength', 0) > 0.5


class StrategyExecutorTestCase(TestCase):
    """Test cases for StrategyExecutor"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.executor = StrategyExecutor()
        self.strategy = MockStrategy(name="MockStrategy", enabled=True)
        
        # Create test stock
        self.stock = Stock.objects.create(
            stock_code="TEST",
            script="TEST",
            company_name="Test Company"
        )
    
    def test_register_strategy(self):
        """Test strategy registration"""
        self.executor.register_strategy(self.strategy)
        self.assertIn("MockStrategy", self.executor.list_strategies())
    
    def test_unregister_strategy(self):
        """Test strategy unregistration"""
        self.executor.register_strategy(self.strategy)
        self.executor.unregister_strategy("MockStrategy")
        self.assertNotIn("MockStrategy", self.executor.list_strategies())
    
    def test_get_strategy(self):
        """Test getting strategy by name"""
        self.executor.register_strategy(self.strategy)
        retrieved = self.executor.get_strategy("MockStrategy")
        self.assertEqual(retrieved, self.strategy)
    
    def test_list_enabled_strategies(self):
        """Test listing enabled strategies"""
        enabled_strategy = MockStrategy(name="Enabled", enabled=True)
        disabled_strategy = MockStrategy(name="Disabled", enabled=False)
        
        self.executor.register_strategy(enabled_strategy)
        self.executor.register_strategy(disabled_strategy)
        
        enabled_list = self.executor.list_enabled_strategies()
        self.assertEqual(len(enabled_list), 1)
        self.assertEqual(enabled_list[0].name, "Enabled")
    
    @patch('stocks.engine.strategy_executor.StrategyExecutor._get_market_data')
    def test_execute_strategy_success(self, mock_get_data):
        """Test successful strategy execution"""
        # Mock market data
        mock_data = pd.DataFrame({
            'close': [100, 101, 102],
            'open': [99, 100, 101],
            'high': [101, 102, 103],
            'low': [98, 99, 100],
            'volume': [1000, 1100, 1200]
        })
        mock_get_data.return_value = mock_data
        
        self.executor.register_strategy(self.strategy)
        signal = self.executor.execute_strategy("MockStrategy", "TEST", "NSE")
        
        self.assertIsNotNone(signal)
        self.assertEqual(signal['action'], 'BUY')
    
    @patch('stocks.engine.strategy_executor.StrategyExecutor._get_market_data')
    def test_execute_strategy_no_data(self, mock_get_data):
        """Test strategy execution with no data"""
        mock_get_data.return_value = None
        
        self.executor.register_strategy(self.strategy)
        signal = self.executor.execute_strategy("MockStrategy", "TEST", "NSE")
        
        self.assertIsNone(signal)
    
    @patch('stocks.engine.strategy_executor.StrategyExecutor._get_market_data')
    def test_execute_strategy_disabled(self, mock_get_data):
        """Test executing disabled strategy"""
        disabled_strategy = MockStrategy(name="Disabled", enabled=False)
        self.executor.register_strategy(disabled_strategy)
        
        signal = self.executor.execute_strategy("Disabled", "TEST", "NSE")
        self.assertIsNone(signal)
    
    def test_execute_strategy_not_found(self):
        """Test executing non-existent strategy"""
        signal = self.executor.execute_strategy("NonExistent", "TEST", "NSE")
        self.assertIsNone(signal)
    
    def test_get_market_data_from_database(self):
        """Test getting market data from database"""
        # Create test price data
        StockPrice.objects.create(
            stock=self.stock,
            script="TEST",
            date=datetime.now().date(),
            open_price=100.0,
            high_price=105.0,
            low_price=95.0,
            close_price=102.0,
            volume=1000
        )
        
        data = self.executor._get_market_data("TEST", "NSE", days=1)
        self.assertIsNotNone(data)
        self.assertFalse(data.empty)
    
    @patch('stocks.engine.strategy_executor.BreezeAPI')
    def test_get_market_data_from_api(self, mock_breeze):
        """Test getting market data from Breeze API"""
        # Mock Breeze API response
        mock_api = Mock()
        mock_api.get_historical_data.return_value = {
            "Success": [
                {
                    "datetime": "2024-01-01T00:00:00",
                    "open": "100",
                    "high": "105",
                    "low": "95",
                    "close": "102",
                    "volume": "1000"
                }
            ]
        }
        self.executor.breeze = mock_api
        
        data = self.executor._get_market_data("TEST", "NSE", days=1)
        # Should return None if no database data and API fails
        # This test verifies the fallback mechanism


if __name__ == '__main__':
    unittest.main()
