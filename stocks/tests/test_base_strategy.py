"""
Unit tests for BaseStrategy class
"""
import unittest
from unittest.mock import Mock, patch
from datetime import datetime
import pandas as pd

from stocks.strategies.base_strategy import BaseStrategy


class TestStrategy(BaseStrategy):
    """Test strategy implementation"""
    
    def generate_signal(self, data, **kwargs):
        return {
            'action': 'BUY',
            'strength': 0.8,
            'price': 100.0,
            'reason': 'Test signal'
        }
    
    def validate_signal(self, signal):
        return signal.get('strength', 0) > 0.5


class BaseStrategyTestCase(unittest.TestCase):
    """Test cases for BaseStrategy"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.strategy = TestStrategy(name="TestStrategy", enabled=True)
    
    def test_strategy_initialization(self):
        """Test strategy initialization"""
        self.assertEqual(self.strategy.name, "TestStrategy")
        self.assertTrue(self.strategy.enabled)
        self.assertEqual(len(self.strategy.signals), 0)
    
    def test_get_parameters(self):
        """Test getting parameters"""
        params = self.strategy.get_parameters()
        self.assertIsInstance(params, dict)
    
    def test_update_parameters(self):
        """Test updating parameters"""
        self.strategy.update_parameters(test_param=123)
        params = self.strategy.get_parameters()
        self.assertEqual(params.get('test_param'), 123)
    
    def test_enable_disable(self):
        """Test enable/disable functionality"""
        self.strategy.disable()
        self.assertFalse(self.strategy.is_enabled())
        
        self.strategy.enable()
        self.assertTrue(self.strategy.is_enabled())
    
    def test_generate_signal(self):
        """Test signal generation"""
        data = pd.DataFrame({
            'close': [100, 101, 102],
            'open': [99, 100, 101],
            'high': [101, 102, 103],
            'low': [98, 99, 100],
            'volume': [1000, 1100, 1200]
        })
        
        signal = self.strategy.generate_signal(data)
        self.assertIsNotNone(signal)
        self.assertEqual(signal['action'], 'BUY')
        self.assertEqual(signal['strength'], 0.8)
    
    def test_validate_signal(self):
        """Test signal validation"""
        valid_signal = {'action': 'BUY', 'strength': 0.8}
        invalid_signal = {'action': 'BUY', 'strength': 0.3}
        
        self.assertTrue(self.strategy.validate_signal(valid_signal))
        self.assertFalse(self.strategy.validate_signal(invalid_signal))
    
    def test_add_signal(self):
        """Test adding signal to history"""
        signal = {'action': 'BUY', 'strength': 0.8}
        self.strategy.add_signal(signal)
        
        self.assertEqual(len(self.strategy.signals), 1)
        self.assertIn('timestamp', self.strategy.signals[0])
        self.assertIn('strategy', self.strategy.signals[0])
    
    def test_get_signal_history(self):
        """Test getting signal history"""
        signal1 = {'action': 'BUY', 'strength': 0.8}
        signal2 = {'action': 'SELL', 'strength': 0.6}
        
        self.strategy.add_signal(signal1)
        self.strategy.add_signal(signal2)
        
        history = self.strategy.get_signal_history()
        self.assertEqual(len(history), 2)
    
    def test_strategy_string_representation(self):
        """Test string representation"""
        str_repr = str(self.strategy)
        self.assertIn("TestStrategy", str_repr)
        self.assertIn("Enabled", str_repr)
        
        self.strategy.disable()
        str_repr = str(self.strategy)
        self.assertIn("Disabled", str_repr)


if __name__ == '__main__':
    unittest.main()
