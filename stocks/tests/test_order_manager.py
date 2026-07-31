"""
Unit tests for OrderManager
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from django.test import TestCase

from stocks.engine.order_manager import OrderManager
from stocks.models import LiveTrade, Orders
from stocks.risk.risk_manager import RiskManager


class OrderManagerTestCase(TestCase):
    """Test cases for OrderManager"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create RiskLimits first
        from stocks.models import RiskLimits
        from decimal import Decimal
        RiskLimits.objects.get_or_create(
            id=1,
            defaults={
                'max_position_size': Decimal('100000'),
                'max_portfolio_exposure': Decimal('50.0'),
                'max_daily_loss': Decimal('5000'),
                'max_drawdown': Decimal('10.0')
            }
        )
        
        self.order_manager = OrderManager()
    
    @patch('stocks.engine.order_manager.BreezeAPI')
    def test_place_order_success(self, mock_breeze_class):
        """Test successful order placement"""
        # Mock Breeze API
        mock_breeze = Mock()
        mock_breeze.place_order.return_value = {
            "Status": "Success",
            "order_id": "TEST123"
        }
        self.order_manager.breeze = mock_breeze
        
        result = self.order_manager.place_order(
            stock_code="TEST",
            exchange="NSE",
            quantity=10,
            order_type="MARKET",
            price=100.0,
            action="BUY",
            stop_loss=95.0,
            take_profit=110.0
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['order_id'], "TEST123")
        self.assertIn('trade_id', result)
    
    @patch('stocks.engine.order_manager.BreezeAPI')
    def test_place_order_api_failure(self, mock_breeze_class):
        """Test order placement with API failure"""
        mock_breeze = Mock()
        mock_breeze.place_order.return_value = {
            "Status": "Error",
            "ErrorMessage": "API Error"
        }
        self.order_manager.breeze = mock_breeze
        
        result = self.order_manager.place_order(
            stock_code="TEST",
            exchange="NSE",
            quantity=10,
            order_type="MARKET",
            price=100.0,
            action="BUY"
        )
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
    
    @patch('stocks.engine.order_manager.BreezeAPI')
    def test_execute_signal_success(self, mock_breeze_class):
        """Test executing a signal successfully"""
        # Mock Breeze API
        mock_breeze = Mock()
        mock_breeze.place_order.return_value = {
            "Status": "Success",
            "order_id": "TEST123"
        }
        self.order_manager.breeze = mock_breeze
        
        signal = {
            'action': 'BUY',
            'price': 100.0,
            'stop_loss': 95.0,
            'take_profit': 110.0,
            'strategy_name': 'TestStrategy',
            'quantity': 10  # Specify quantity
        }
        
        result = self.order_manager.execute_signal(signal, "TEST", "NSE")
        
        self.assertTrue(result['success'])
    
    def test_execute_signal_risk_validation_fails(self):
        """Test signal execution fails risk validation"""
        # Update RiskLimits with very low limits
        from stocks.models import RiskLimits
        from decimal import Decimal
        limits = RiskLimits.objects.get(id=1)
        limits.max_position_size = Decimal('100')  # Very low limit
        limits.save()
        
        # Reinitialize risk manager with new limits
        from stocks.risk.risk_manager import RiskManager
        self.order_manager.risk_manager = RiskManager()
        
        signal = {
            'action': 'BUY',
            'price': 100.0,
            'quantity': 10  # 1000 value > 100 limit
        }
        
        result = self.order_manager.execute_signal(signal, "TEST", "NSE")
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
    
    def test_execute_signal_invalid_action(self):
        """Test executing signal with invalid action"""
        signal = {
            'action': 'HOLD',  # Invalid for trading
            'price': 100.0
        }
        
        result = self.order_manager.execute_signal(signal, "TEST", "NSE")
        
        self.assertFalse(result['success'])
        self.assertIn('Invalid action', result['error'])
    
    @patch('stocks.engine.order_manager.BreezeAPI')
    def test_modify_order_success(self, mock_breeze_class):
        """Test successful order modification"""
        mock_breeze = Mock()
        mock_breeze.modify_order.return_value = {
            "Status": "Success"
        }
        self.order_manager.breeze = mock_breeze
        
        # Create test trade
        trade = LiveTrade.objects.create(
            stock_code="TEST",
            exchange="NSE",
            quantity=10,
            order_type="LIMIT",
            price=Decimal('100.0'),
            action="BUY",
            status="Executed",
            order_id="TEST123"
        )
        
        result = self.order_manager.modify_order("TEST123", 105.0)
        
        self.assertTrue(result['success'])
        trade.refresh_from_db()
        self.assertEqual(float(trade.price), 105.0)
    
    @patch('stocks.engine.order_manager.BreezeAPI')
    def test_cancel_order_success(self, mock_breeze_class):
        """Test successful order cancellation"""
        mock_breeze = Mock()
        mock_breeze.cancel_order.return_value = {
            "Status": "Success"
        }
        self.order_manager.breeze = mock_breeze
        
        # Create test trade and order
        trade = LiveTrade.objects.create(
            stock_code="TEST",
            exchange="NSE",
            quantity=10,
            order_type="MARKET",
            price=Decimal('100.0'),
            action="BUY",
            status="Executed",
            order_id="TEST123"
        )
        
        Orders.objects.create(
            ticker="TEST",
            script="TEST",
            order_id="TEST123",
            position="BUY",
            stop_loss=95.0,
            qty="10",
            price=100.0,
            invested_value=1000.0,
            current_value=1000.0,
            day_pl=0.0,
            overall_pl=0.0,
            status=1
        )
        
        result = self.order_manager.cancel_order("TEST123")
        
        self.assertTrue(result['success'])
        trade.refresh_from_db()
        self.assertEqual(trade.status, "Canceled")


if __name__ == '__main__':
    unittest.main()
