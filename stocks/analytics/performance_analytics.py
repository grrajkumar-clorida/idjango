"""
Performance Analytics Module
Calculates advanced performance metrics including Sharpe ratio, win rate, max drawdown, etc.
"""
import math
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from django.db.models import Q, Sum, Count, Avg, Max, Min
from django.utils import timezone
import pytz
import logging

from stocks.models import TradeJournal, Strategy, Orders
from stocks.utils.timezone_utils import INDIAN_TZ, now_indian, today_indian, get_day_start_end

logger = logging.getLogger(__name__)


class PerformanceAnalytics:
    """Advanced performance analytics and metrics calculation"""
    
    def __init__(self, strategy_id: Optional[int] = None):
        """
        Initialize analytics
        
        Args:
            strategy_id: Optional strategy ID to filter trades. If None, analyzes all trades.
        """
        self.strategy_id = strategy_id
        self.strategy = None
        if strategy_id:
            try:
                self.strategy = Strategy.objects.get(id=strategy_id)
            except Strategy.DoesNotExist:
                logger.warning(f"Strategy {strategy_id} not found")
    
    def get_trades_queryset(self, start_date=None, end_date=None):
        """Get filtered trades queryset"""
        qs = TradeJournal.objects.all()
        
        if self.strategy_id:
            qs = qs.filter(strategy_id=self.strategy_id)
        
        if start_date:
            qs = qs.filter(entry_date__gte=start_date)
        if end_date:
            qs = qs.filter(entry_date__lte=end_date)
        
        return qs
    
    def calculate_win_rate(self, start_date=None, end_date=None) -> Dict:
        """
        Calculate win rate statistics
        
        Returns:
            Dictionary with win_rate, total_trades, winning_trades, losing_trades
        """
        trades = self.get_trades_queryset(start_date, end_date).exclude(win_loss__isnull=True)
        
        total_trades = trades.count()
        if total_trades == 0:
            return {
                'win_rate': 0.0,
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'breakeven_trades': 0,
            }
        
        winning_trades = trades.filter(win_loss='WIN').count()
        losing_trades = trades.filter(win_loss='LOSS').count()
        breakeven_trades = trades.filter(win_loss='BREAKEVEN').count()
        
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0.0
        
        return {
            'win_rate': round(win_rate, 2),
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'breakeven_trades': breakeven_trades,
        }
    
    def calculate_profit_factor(self, start_date=None, end_date=None) -> float:
        """
        Calculate profit factor (gross profit / gross loss)
        
        Returns:
            Profit factor value
        """
        trades = self.get_trades_queryset(start_date, end_date)
        
        gross_profit = trades.filter(win_loss='WIN').aggregate(
            total=Sum('net_pnl')
        )['total'] or Decimal('0.00')
        
        gross_loss = abs(trades.filter(win_loss='LOSS').aggregate(
            total=Sum('net_pnl')
        )['total'] or Decimal('0.00'))
        
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0
        
        profit_factor = float(gross_profit) / float(gross_loss)
        return round(profit_factor, 2)
    
    def calculate_sharpe_ratio(self, start_date=None, end_date=None, risk_free_rate: float = 0.0) -> Optional[float]:
        """
        Calculate Sharpe ratio
        
        Args:
            start_date: Start date for calculation
            end_date: End date for calculation
            risk_free_rate: Risk-free rate (default 0.0 for simplicity)
        
        Returns:
            Sharpe ratio or None if insufficient data
        """
        trades = self.get_trades_queryset(start_date, end_date).exclude(win_loss__isnull=True)
        
        if trades.count() < 2:
            return None
        
        # Get daily returns
        daily_returns = []
        current_date = None
        daily_pnl = Decimal('0.00')
        
        for trade in trades.order_by('entry_date'):
            trade_date = trade.entry_date.date()
            
            if current_date is None:
                current_date = trade_date
                daily_pnl = trade.net_pnl
            elif trade_date == current_date:
                daily_pnl += trade.net_pnl
            else:
                daily_returns.append(float(daily_pnl))
                current_date = trade_date
                daily_pnl = trade.net_pnl
        
        # Add last day
        if daily_pnl != 0:
            daily_returns.append(float(daily_pnl))
        
        if len(daily_returns) < 2:
            return None
        
        # Calculate mean and standard deviation
        mean_return = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean_return) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
        std_dev = math.sqrt(variance)
        
        if std_dev == 0:
            return None
        
        # Sharpe ratio = (mean return - risk free rate) / standard deviation
        sharpe_ratio = (mean_return - risk_free_rate) / std_dev
        return round(sharpe_ratio, 2)
    
    def calculate_max_drawdown(self, start_date=None, end_date=None) -> Dict:
        """
        Calculate maximum drawdown
        
        Returns:
            Dictionary with max_drawdown, max_drawdown_percent, peak_value, trough_value, recovery_date
        """
        trades = self.get_trades_queryset(start_date, end_date).order_by('entry_date')
        
        if trades.count() == 0:
            return {
                'max_drawdown': 0.0,
                'max_drawdown_percent': 0.0,
                'peak_value': 0.0,
                'trough_value': 0.0,
                'recovery_date': None,
            }
        
        # Calculate cumulative P/L
        cumulative_pnl = Decimal('0.00')
        peak_value = Decimal('0.00')
        max_drawdown = Decimal('0.00')
        max_drawdown_percent = 0.0
        trough_value = Decimal('0.00')
        recovery_date = None
        
        for trade in trades:
            cumulative_pnl += trade.net_pnl
            
            # Update peak
            if cumulative_pnl > peak_value:
                peak_value = cumulative_pnl
                # Reset drawdown tracking if we've recovered
                if cumulative_pnl >= Decimal('0.00'):
                    recovery_date = trade.entry_date
            
            # Calculate drawdown from peak
            drawdown = peak_value - cumulative_pnl
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                trough_value = cumulative_pnl
                if peak_value > 0:
                    max_drawdown_percent = (float(drawdown) / float(peak_value)) * 100
        
        return {
            'max_drawdown': float(max_drawdown),
            'max_drawdown_percent': round(max_drawdown_percent, 2),
            'peak_value': float(peak_value),
            'trough_value': float(trough_value),
            'recovery_date': recovery_date,
        }
    
    def calculate_average_trade(self, start_date=None, end_date=None) -> Dict:
        """
        Calculate average trade statistics
        
        Returns:
            Dictionary with average P/L, average win, average loss, etc.
        """
        trades = self.get_trades_queryset(start_date, end_date)
        
        if trades.count() == 0:
            return {
                'avg_pnl': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'largest_win': 0.0,
                'largest_loss': 0.0,
            }
        
        avg_pnl = trades.aggregate(avg=Avg('net_pnl'))['avg'] or Decimal('0.00')
        
        winning_trades = trades.filter(win_loss='WIN')
        losing_trades = trades.filter(win_loss='LOSS')
        
        avg_win = winning_trades.aggregate(avg=Avg('net_pnl'))['avg'] or Decimal('0.00')
        avg_loss = losing_trades.aggregate(avg=Avg('net_pnl'))['avg'] or Decimal('0.00')
        
        largest_win = winning_trades.aggregate(max=Max('net_pnl'))['max'] or Decimal('0.00')
        largest_loss = losing_trades.aggregate(min=Min('net_pnl'))['min'] or Decimal('0.00')
        
        return {
            'avg_pnl': float(avg_pnl),
            'avg_win': float(avg_win),
            'avg_loss': float(avg_loss),
            'largest_win': float(largest_win),
            'largest_loss': float(largest_loss),
        }
    
    def calculate_risk_adjusted_returns(self, start_date=None, end_date=None) -> Dict:
        """
        Calculate risk-adjusted return metrics
        
        Returns:
            Dictionary with various risk-adjusted metrics
        """
        trades = self.get_trades_queryset(start_date, end_date)
        
        total_trades = trades.count()
        if total_trades == 0:
            return {
                'total_return': 0.0,
                'total_return_percent': 0.0,
                'sharpe_ratio': None,
                'sortino_ratio': None,
                'calmar_ratio': None,
            }
        
        total_return = trades.aggregate(total=Sum('net_pnl'))['total'] or Decimal('0.00')
        
        # Calculate initial capital (sum of entry prices * quantities)
        initial_capital = trades.aggregate(
            total=Sum('entry_price') * Sum('quantity')
        )['total'] or Decimal('1.00')
        
        total_return_percent = (float(total_return) / float(initial_capital)) * 100 if initial_capital > 0 else 0.0
        
        sharpe_ratio = self.calculate_sharpe_ratio(start_date, end_date)
        
        # Sortino ratio (similar to Sharpe but only considers downside deviation)
        sortino_ratio = self._calculate_sortino_ratio(start_date, end_date)
        
        # Calmar ratio (annual return / max drawdown)
        max_dd = self.calculate_max_drawdown(start_date, end_date)
        calmar_ratio = None
        if max_dd['max_drawdown'] > 0:
            # Annualize return (assuming 252 trading days)
            days = (end_date - start_date).days if start_date and end_date else 252
            annual_return = (float(total_return) / days) * 252 if days > 0 else 0.0
            calmar_ratio = annual_return / max_dd['max_drawdown'] if max_dd['max_drawdown'] > 0 else None
        
        return {
            'total_return': float(total_return),
            'total_return_percent': round(total_return_percent, 2),
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'calmar_ratio': round(calmar_ratio, 2) if calmar_ratio else None,
        }
    
    def _calculate_sortino_ratio(self, start_date=None, end_date=None, risk_free_rate: float = 0.0) -> Optional[float]:
        """Calculate Sortino ratio (downside deviation only)"""
        trades = self.get_trades_queryset(start_date, end_date).exclude(win_loss__isnull=True)
        
        if trades.count() < 2:
            return None
        
        # Get daily returns
        daily_returns = []
        current_date = None
        daily_pnl = Decimal('0.00')
        
        for trade in trades.order_by('entry_date'):
            trade_date = trade.entry_date.date()
            
            if current_date is None:
                current_date = trade_date
                daily_pnl = trade.net_pnl
            elif trade_date == current_date:
                daily_pnl += trade.net_pnl
            else:
                daily_returns.append(float(daily_pnl))
                current_date = trade_date
                daily_pnl = trade.net_pnl
        
        if daily_pnl != 0:
            daily_returns.append(float(daily_pnl))
        
        if len(daily_returns) < 2:
            return None
        
        mean_return = sum(daily_returns) / len(daily_returns)
        
        # Calculate downside deviation (only negative returns)
        downside_returns = [r for r in daily_returns if r < 0]
        if len(downside_returns) == 0:
            return float('inf') if mean_return > risk_free_rate else None
        
        downside_variance = sum((r - mean_return) ** 2 for r in downside_returns) / len(downside_returns)
        downside_std_dev = math.sqrt(downside_variance)
        
        if downside_std_dev == 0:
            return None
        
        sortino_ratio = (mean_return - risk_free_rate) / downside_std_dev
        return round(sortino_ratio, 2)
    
    def get_comprehensive_metrics(self, start_date=None, end_date=None) -> Dict:
        """
        Get comprehensive performance metrics
        
        Returns:
            Dictionary with all performance metrics
        """
        win_rate_stats = self.calculate_win_rate(start_date, end_date)
        profit_factor = self.calculate_profit_factor(start_date, end_date)
        sharpe_ratio = self.calculate_sharpe_ratio(start_date, end_date)
        max_drawdown = self.calculate_max_drawdown(start_date, end_date)
        avg_trade = self.calculate_average_trade(start_date, end_date)
        risk_adjusted = self.calculate_risk_adjusted_returns(start_date, end_date)
        
        trades = self.get_trades_queryset(start_date, end_date)
        total_pnl = trades.aggregate(total=Sum('net_pnl'))['total'] or Decimal('0.00')
        
        return {
            'strategy_id': self.strategy_id,
            'strategy_name': self.strategy.name if self.strategy else 'All Strategies',
            'period': {
                'start_date': start_date,
                'end_date': end_date,
            },
            'win_rate': win_rate_stats,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'average_trade': avg_trade,
            'risk_adjusted_returns': risk_adjusted,
            'total_pnl': float(total_pnl),
            'total_trades': trades.count(),
        }
