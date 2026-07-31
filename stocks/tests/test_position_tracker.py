"""
Unit tests for PositionTracker
"""
import unittest
from unittest.mock import Mock, patch
from decimal import Decimal
from django.test import TestCase

from stocks.positions.position_tracker import PositionTracker
from stocks.models import LiveTrade


class PositionTrackerTestCase(TestCase):
    """Test cases for PositionTracker"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tracker = PositionTracker()
    
    def test_get_all_positions(self):
        """Test getting all positions"""
        # Create test positions
        LiveTrade.objects.create(
            stock_code="TEST1",
            exchange="NSE",
            quantity=10,
            price=Decimal('100.0'),
            action="BUY",
            status="Executed"
        )
        
        LiveTrade.objects.create(
            stock_code="TEST2",
            exchange="NSE",
            quantity=5,
            price=Decimal('200.0'),
            action="BUY",
            status="Executed"
        )
        
        positions = self.tracker.get_all_positions()
        self.assertEqual(len(positions), 2)
    
    def test_get_position(self):
        """Test getting position for specific stock"""
        LiveTrade.objects.create(
            stock_code="TEST",
            exchange="NSE",
            quantity=10,
            price=Decimal('100.0'),
            action="BUY",
            status="Executed"
        )
        
        position = self.tracker.get_position("TEST")
        self.assertIsNotNone(position)
        self.assertEqual(position.stock_code, "TEST")
    
    def test_get_position_not_found(self):
        """Test getting position that doesn't exist"""
        position = self.tracker.get_position("NONEXISTENT")
        self.assertIsNone(position)
    
    def test_update_position_pnl(self):
        """Test updating position P/L"""
        trade = LiveTrade.objects.create(
            stock_code="TEST",
            exchange="NSE",
            quantity=10,
            price=Decimal('100.0'),
            action="BUY",
            status="Executed"
        )
        
        self.tracker.update_position_pnl(trade, 110.0)
        
        trade.refresh_from_db()
        # P/L = (110 - 100) * 10 = 100
        self.assertEqual(float(trade.profit_loss), 100.0)
    
    def test_update_position_pnl_sell(self):
        """Test updating P/L for SELL position"""
        trade = LiveTrade.objects.create(
            stock_code="TEST",
            exchange="NSE",
            quantity=10,
            price=Decimal('100.0'),
            action="SELL",
            status="Executed"
        )
        
        self.tracker.update_position_pnl(trade, 90.0)
        
        trade.refresh_from_db()
        # P/L = (100 - 90) * 10 = 100
        self.assertEqual(float(trade.profit_loss), 100.0)
    
    @patch('stocks.positions.position_tracker.BreezeAPI')
    def test_update_all_positions_pnl(self, mock_breeze_class):
        """Test updating P/L for all positions"""
        mock_breeze = Mock()
        mock_breeze.get_live_price.return_value = {
            "Success": [{"ltp": "110.0"}]
        }
        self.tracker.breeze = mock_breeze
        
        LiveTrade.objects.create(
            stock_code="TEST",
            exchange="NSE",
            quantity=10,
            price=Decimal('100.0'),
            action="BUY",
            status="Executed"
        )
        
        self.tracker.update_all_positions_pnl()
        
        trade = LiveTrade.objects.get(stock_code="TEST")
        self.assertIsNotNone(trade.profit_loss)
    
    def test_get_position_summary(self):
        """Test getting position summary"""
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
        
        summary = self.tracker.get_position_summary()
        
        self.assertEqual(summary['total_positions'], 2)
        self.assertEqual(summary['winning_positions'], 1)
        self.assertEqual(summary['losing_positions'], 1)
        self.assertIn('total_invested', summary)
        self.assertIn('total_pnl', summary)


if __name__ == '__main__':
    unittest.main()
