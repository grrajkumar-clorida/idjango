"""
Integration tests for Phase 1 components
"""
import unittest
from unittest.mock import Mock, patch
import pandas as pd
from decimal import Decimal
from django.test import TestCase

from stocks.strategies.base_strategy import BaseStrategy
from stocks.engine.strategy_executor import StrategyExecutor
from stocks.engine.signal_processor import SignalProcessor
from stocks.engine.order_manager import OrderManager
from stocks.risk.risk_manager import RiskManager
from stocks.positions.position_tracker import PositionTracker
from stocks.positions.exit_manager import ExitManager
from stocks.models import Stock, StockPrice, LiveTrade, RiskLimits


class MockStrategy(BaseStrategy):
    """Mock strategy for integration testing"""
    
    def generate_signal(self, data, **kwargs):
        return {
            'action': 'BUY',
            'strength': 0.8,
            'price': data['close'].iloc[-1] if len(data) > 0 else 100.0,
            'stop_loss': data['close'].iloc[-1] * 0.95 if len(data) > 0 else 95.0,
            'take_profit': data['close'].iloc[-1] * 1.10 if len(data) > 0 else 110.0,
            'reason': 'Integration test signal'
        }
    
    def validate_signal(self, signal):
        return signal.get('strength', 0) > 0.5


class IntegrationTestCase(TestCase):
    """Integration tests for Phase 1"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create risk limits (get_or_create to avoid duplicate key error)
        RiskLimits.objects.get_or_create(
            id=1,
            defaults={
                'max_position_size': Decimal('100000'),
                'max_portfolio_exposure': Decimal('50.0'),
                'max_daily_loss': Decimal('5000'),
                'max_drawdown': Decimal('10.0')
            }
        )
        
        # Create test stock
        self.stock = Stock.objects.create(
            stock_code="TEST",
            script="TEST",
            company_name="Test Company"
        )
        
        # Create test price data
        StockPrice.objects.create(
            stock=self.stock,
            script="TEST",
            date=pd.Timestamp.now().date(),
            open_price=100.0,
            high_price=105.0,
            low_price=95.0,
            close_price=102.0,
            volume=1000
        )
    
    @patch('stocks.engine.order_manager.BreezeAPI')
    @patch('stocks.engine.strategy_executor.BreezeAPI')
    def test_full_trading_flow(self, mock_breeze_executor, mock_breeze_order):
        """Test complete trading flow: Strategy -> Signal -> Order -> Position"""
        # Setup
        executor = StrategyExecutor()
        processor = SignalProcessor()
        order_manager = OrderManager()
        tracker = PositionTracker()
        exit_manager = ExitManager()
        
        # Mock Breeze API for order manager
        mock_breeze_order_instance = Mock()
        mock_breeze_order_instance.place_order.return_value = {
            "Status": "Success",
            "order_id": "INTEGRATION123"
        }
        order_manager.breeze = mock_breeze_order_instance
        
        # Mock Breeze API for executor (for market data)
        mock_breeze_executor_instance = Mock()
        mock_breeze_executor_instance.get_historical_data.return_value = None
        executor.breeze = mock_breeze_executor_instance
        
        # 1. Register strategy
        strategy = MockStrategy(name="IntegrationStrategy", enabled=True)
        executor.register_strategy(strategy)
        
        # 2. Execute strategy
        signal = executor.execute_strategy("IntegrationStrategy", "TEST", "NSE")
        self.assertIsNotNone(signal)
        
        # 3. Process signal
        processed_signal = processor.process_signal(signal, "TEST", "IntegrationStrategy")
        self.assertIsNotNone(processed_signal)
        
        # 4. Execute order
        order_result = order_manager.execute_signal(processed_signal, "TEST", "NSE")
        self.assertTrue(order_result['success'])
        
        # 5. Verify position created
        position = tracker.get_position("TEST")
        self.assertIsNotNone(position)
        
        # 6. Update P/L
        tracker.update_position_pnl(position, 110.0)
        position.refresh_from_db()
        self.assertGreater(float(position.profit_loss), 0)
        
        # 7. Check exit conditions (if take_profit is set)
        if position.take_profit:
            exit_result = exit_manager.monitor_exits(position, float(position.take_profit) + 1)
            # Should trigger take-profit
            self.assertIsNotNone(exit_result)
    
    def test_risk_validation_integration(self):
        """Test risk validation in order execution"""
        risk_manager = RiskManager()
        
        # Create signal that exceeds limits
        signal = {
            'action': 'BUY',
            'price': 1000.0,
            'quantity': 200  # 200,000 > 100,000 limit
        }
        
        # Risk validation should fail
        is_valid, reason = risk_manager.validate_trade(
            "TEST", signal['quantity'], signal['price'], signal['action']
        )
        
        self.assertFalse(is_valid)
        self.assertIn("exceeds", reason.lower())
    
    def test_signal_aggregation_integration(self):
        """Test signal aggregation with multiple strategies"""
        processor = SignalProcessor()
        
        signals = [
            {'stock_code': 'TEST', 'action': 'BUY', 'strength': 0.8, 'price': 100, 'strategy_name': 'S1'},
            {'stock_code': 'TEST', 'action': 'BUY', 'strength': 0.6, 'price': 101, 'strategy_name': 'S2'},
            {'stock_code': 'TEST', 'action': 'SELL', 'strength': 0.7, 'price': 102, 'strategy_name': 'S3'},
        ]
        
        aggregated = processor.aggregate_signals(signals)
        
        self.assertEqual(len(aggregated), 1)
        test_signal = aggregated[0]
        self.assertEqual(test_signal['stock_code'], 'TEST')
        self.assertEqual(test_signal['buy_signals'], 2)
        self.assertEqual(test_signal['sell_signals'], 1)
    
    def test_position_tracking_integration(self):
        """Test position tracking and P/L calculation"""
        tracker = PositionTracker()
        
        # Create multiple positions
        LiveTrade.objects.create(
            stock_code="TEST1",
            exchange="NSE",
            quantity=10,
            price=Decimal('100.0'),
            action="BUY",
            status="Executed",
            profit_loss=Decimal('50.0')
        )
        
        LiveTrade.objects.create(
            stock_code="TEST2",
            exchange="NSE",
            quantity=5,
            price=Decimal('200.0'),
            action="BUY",
            status="Executed",
            profit_loss=Decimal('-20.0')
        )
        
        summary = tracker.get_position_summary()
        
        self.assertEqual(summary['total_positions'], 2)
        self.assertEqual(summary['winning_positions'], 1)
        self.assertEqual(summary['losing_positions'], 1)
        self.assertGreater(summary['total_pnl'], 0)


if __name__ == '__main__':
    unittest.main()
