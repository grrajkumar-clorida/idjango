"""
Unit tests for RiskManager
"""
import unittest
from decimal import Decimal
from datetime import date
from django.test import TestCase

from stocks.risk.risk_manager import RiskManager
from stocks.models import RiskLimits, LiveTrade


class RiskManagerTestCase(TestCase):
    """Test cases for RiskManager"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create risk limits (get_or_create to avoid duplicate key error)
        self.risk_limits, _ = RiskLimits.objects.get_or_create(
            id=1,
            defaults={
                'max_position_size': Decimal('100000'),
                'max_portfolio_exposure': Decimal('50.0'),
                'max_daily_loss': Decimal('5000'),
                'max_drawdown': Decimal('10.0')
            }
        )
        
        self.risk_manager = RiskManager()
    
    def test_load_limits(self):
        """Test loading risk limits"""
        limits = self.risk_manager.limits
        self.assertIsNotNone(limits)
        self.assertEqual(float(limits.max_position_size), 100000.0)
    
    def test_validate_trade_within_limits(self):
        """Test validating trade within limits"""
        is_valid, reason = self.risk_manager.validate_trade(
            stock_code="TEST",
            quantity=10,
            price=1000.0,
            action="BUY"
        )
        
        self.assertTrue(is_valid)
        self.assertEqual(reason, "Trade validated")
    
    def test_validate_trade_exceeds_position_size(self):
        """Test validating trade exceeding position size"""
        is_valid, reason = self.risk_manager.validate_trade(
            stock_code="TEST",
            quantity=200,
            price=1000.0,  # 200,000 > 100,000 limit
            action="BUY"
        )
        
        self.assertFalse(is_valid)
        self.assertIn("exceeds max position size", reason)
    
    def test_calculate_position_size(self):
        """Test calculating position size"""
        quantity = self.risk_manager.calculate_position_size(
            stock_code="TEST",
            price=100.0,
            risk_percent=1.0,
            capital=100000.0
        )
        
        # 1% of 100,000 = 1,000 / 100 = 10 shares
        self.assertEqual(quantity, 10)
    
    def test_calculate_position_size_respects_max(self):
        """Test position size respects maximum"""
        quantity = self.risk_manager.calculate_position_size(
            stock_code="TEST",
            price=10.0,
            risk_percent=10.0,  # Would be 1000 shares
            capital=100000.0
        )
        
        # Should be limited by max position size (100,000 / 10 = 10,000 max)
        # But risk calculation gives 1,000, so should be 1,000
        self.assertGreater(quantity, 0)
        self.assertLessEqual(quantity * 10.0, 100000.0)
    
    def test_calculate_portfolio_exposure(self):
        """Test calculating portfolio exposure"""
        # Create test trades
        LiveTrade.objects.create(
            stock_code="TEST1",
            exchange="NSE",
            quantity=10,
            price=Decimal('1000.0'),
            action="BUY",
            status="Executed"
        )
        
        exposure = self.risk_manager._calculate_portfolio_exposure()
        self.assertGreaterEqual(exposure, 0)
    
    def test_calculate_daily_loss(self):
        """Test calculating daily loss"""
        # Create losing trade
        LiveTrade.objects.create(
            stock_code="TEST",
            exchange="NSE",
            quantity=10,
            price=Decimal('1000.0'),
            action="BUY",
            status="Executed",
            profit_loss=Decimal('-1000.0'),
            timestamp=date.today()
        )
        
        daily_loss = self.risk_manager._calculate_daily_loss()
        self.assertGreaterEqual(daily_loss, 0)
    
    def test_calculate_drawdown(self):
        """Test calculating drawdown"""
        # Create trades with varying P/L
        LiveTrade.objects.create(
            stock_code="TEST1",
            exchange="NSE",
            quantity=10,
            price=Decimal('1000.0'),
            action="BUY",
            status="Executed",
            profit_loss=Decimal('500.0')
        )
        
        LiveTrade.objects.create(
            stock_code="TEST2",
            exchange="NSE",
            quantity=10,
            price=Decimal('1000.0'),
            action="BUY",
            status="Executed",
            profit_loss=Decimal('-200.0')
        )
        
        drawdown = self.risk_manager._calculate_drawdown()
        self.assertGreaterEqual(drawdown, 0)
    
    def test_update_limits(self):
        """Test updating risk limits"""
        self.risk_manager.update_limits(max_position_size=150000)
        
        updated_limits = RiskLimits.objects.get(id=1)
        self.assertEqual(float(updated_limits.max_position_size), 150000.0)
    
    def test_validate_trade_daily_loss_limit(self):
        """Test validation fails when daily loss limit reached"""
        # Create trades that exceed daily loss
        for i in range(6):
            LiveTrade.objects.create(
                stock_code=f"TEST{i}",
                exchange="NSE",
                quantity=10,
                price=Decimal('1000.0'),
                action="BUY",
                status="Executed",
                profit_loss=Decimal('-1000.0'),  # -1000 each
                timestamp=date.today()
            )
        
        is_valid, reason = self.risk_manager.validate_trade(
            stock_code="NEW",
            quantity=10,
            price=1000.0,
            action="BUY"
        )
        
        # Should fail if daily loss >= 5000
        # With 6 trades at -1000 each = -6000, should fail
        self.assertFalse(is_valid)
        self.assertIn("Daily loss limit", reason)


if __name__ == '__main__':
    unittest.main()
