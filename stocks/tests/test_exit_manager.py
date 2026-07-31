"""
Unit tests for ExitManager
"""
import unittest
from unittest.mock import Mock, patch
from decimal import Decimal
from django.test import TestCase

from stocks.positions.exit_manager import ExitManager
from stocks.models import LiveTrade


class ExitManagerTestCase(TestCase):
    """Test cases for ExitManager"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.exit_manager = ExitManager()
    
    def test_check_stop_loss_buy(self):
        """Test stop-loss check for BUY position"""
        trade = LiveTrade.objects.create(
            stock_code="TEST",
            exchange="NSE",
            quantity=10,
            price=Decimal('100.0'),
            action="BUY",
            status="Executed",
            stop_loss=Decimal('95.0')
        )
        
        # Price below stop-loss
        should_exit = self.exit_manager.check_stop_loss(trade, 94.0)
        self.assertTrue(should_exit)
        
        # Price above stop-loss
        should_exit = self.exit_manager.check_stop_loss(trade, 96.0)
        self.assertFalse(should_exit)
    
    def test_check_stop_loss_sell(self):
        """Test stop-loss check for SELL position"""
        trade = LiveTrade.objects.create(
            stock_code="TEST",
            exchange="NSE",
            quantity=10,
            price=Decimal('100.0'),
            action="SELL",
            status="Executed",
            stop_loss=Decimal('105.0')
        )
        
        # Price above stop-loss
        should_exit = self.exit_manager.check_stop_loss(trade, 106.0)
        self.assertTrue(should_exit)
        
        # Price below stop-loss
        should_exit = self.exit_manager.check_stop_loss(trade, 104.0)
        self.assertFalse(should_exit)
    
    def test_check_take_profit_buy(self):
        """Test take-profit check for BUY position"""
        trade = LiveTrade.objects.create(
            stock_code="TEST",
            exchange="NSE",
            quantity=10,
            price=Decimal('100.0'),
            action="BUY",
            status="Executed",
            take_profit=Decimal('110.0')
        )
        
        # Price above take-profit
        should_exit = self.exit_manager.check_take_profit(trade, 111.0)
        self.assertTrue(should_exit)
        
        # Price below take-profit
        should_exit = self.exit_manager.check_take_profit(trade, 109.0)
        self.assertFalse(should_exit)
    
    def test_check_trailing_stop_loss_buy(self):
        """Test trailing stop-loss for BUY position"""
        trade = LiveTrade.objects.create(
            stock_code="TEST",
            exchange="NSE",
            quantity=10,
            price=Decimal('100.0'),
            action="BUY",
            status="Executed",
            trailing_stop_loss=Decimal('95.0'),
            tsl_percentage=5.0
        )
        
        # Price moves up - TSL should move up
        result = self.exit_manager.check_trailing_stop_loss(trade, 110.0)
        self.assertTrue(result['updated'])
        self.assertGreater(result['new_tsl'], 95.0)
        
        # Price moves down - TSL should not move down
        trade.refresh_from_db()
        old_tsl = float(trade.trailing_stop_loss)
        result = self.exit_manager.check_trailing_stop_loss(trade, 105.0)
        self.assertFalse(result['updated'])
    
    @patch('stocks.positions.exit_manager.BreezeAPI')
    def test_execute_exit_full(self, mock_breeze_class):
        """Test full exit execution"""
        mock_breeze = Mock()
        mock_breeze.place_order.return_value = {
            "Status": "Success",
            "order_id": "EXIT123"
        }
        self.exit_manager.breeze = mock_breeze
        
        trade = LiveTrade.objects.create(
            stock_code="TEST",
            exchange="NSE",
            quantity=10,
            price=Decimal('100.0'),
            action="BUY",
            status="Executed"
        )
        
        result = self.exit_manager.execute_exit(trade, "Full exit", None)
        
        self.assertTrue(result['success'])
        trade.refresh_from_db()
        self.assertEqual(trade.status, "Closed")
    
    @patch('stocks.positions.exit_manager.BreezeAPI')
    def test_execute_exit_partial(self, mock_breeze_class):
        """Test partial exit execution"""
        mock_breeze = Mock()
        mock_breeze.place_order.return_value = {
            "Status": "Success",
            "order_id": "EXIT123"
        }
        self.exit_manager.breeze = mock_breeze
        
        trade = LiveTrade.objects.create(
            stock_code="TEST",
            exchange="NSE",
            quantity=10,
            price=Decimal('100.0'),
            action="BUY",
            status="Executed"
        )
        
        # Partial exit: 5 shares (50%)
        result = self.exit_manager.execute_exit(trade, "Partial exit", 5)
        
        self.assertTrue(result['success'])
        trade.refresh_from_db()
        self.assertEqual(trade.quantity, 5)  # 50% remaining
    
    @patch('stocks.positions.exit_manager.BreezeAPI')
    def test_monitor_exits_stop_loss(self, mock_breeze_class):
        """Test monitoring exits - stop-loss triggered"""
        mock_breeze = Mock()
        mock_breeze.place_order.return_value = {
            "Status": "Success",
            "order_id": "EXIT123"
        }
        self.exit_manager.breeze = mock_breeze
        
        trade = LiveTrade.objects.create(
            stock_code="TEST",
            exchange="NSE",
            quantity=10,
            price=Decimal('100.0'),
            action="BUY",
            status="Executed",
            stop_loss=Decimal('95.0')
        )
        
        result = self.exit_manager.monitor_exits(trade, 94.0)
        
        self.assertIsNotNone(result)
        self.assertTrue(result['success'])
        trade.refresh_from_db()
        self.assertEqual(trade.status, "Closed")


if __name__ == '__main__':
    unittest.main()
