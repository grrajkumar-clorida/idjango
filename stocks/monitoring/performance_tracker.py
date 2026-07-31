"""
Performance Tracker
Tracks strategy performance metrics and analytics
Always uses Indian timezone (Asia/Kolkata)
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
import pytz
from django.db.models import Sum, Count, Avg, Q
from decimal import Decimal

from stocks.models import LiveTrade, StrategySignal, Strategy, BacktestResult
from stocks.positions.pnl_calculator import PnLCalculator

logger = logging.getLogger(__name__)

# Indian timezone
INDIAN_TZ = pytz.timezone('Asia/Kolkata')


class PerformanceTracker:
    """Tracks strategy performance"""
    
    def __init__(self):
        self.pnl_calculator = PnLCalculator()
    
    def get_strategy_performance(self, strategy_name: str, days: int = 30) -> Dict:
        """
        Get performance metrics for a specific strategy
        
        Args:
            strategy_name: Name of the strategy
            days: Number of days to analyze
        
        Returns:
            Dictionary with performance metrics
        """
        try:
            strategy = Strategy.objects.get(name=strategy_name)
        except Strategy.DoesNotExist:
            return {'error': f'Strategy {strategy_name} not found'}
        
        # Always use Indian timezone
        now_indian = timezone.now().astimezone(INDIAN_TZ)
        since = now_indian - timedelta(days=days)
        
        # Get signals for this strategy
        signals = StrategySignal.objects.filter(
            strategy=strategy,
            timestamp__gte=since,
            executed=True
        )
        
        # Get trades linked to signals
        trades = LiveTrade.objects.filter(
            signals__strategy=strategy,
            timestamp__gte=since
        ).distinct()
        
        total_trades = trades.count()
        executed_trades = trades.filter(status='Executed').count()
        
        # Calculate P/L
        total_pl = sum(float(trade.profit_loss) for trade in trades if trade.profit_loss)
        
        winning_trades = trades.filter(profit_loss__gt=0).count()
        losing_trades = trades.filter(profit_loss__lt=0).count()
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Calculate average profit/loss
        avg_profit = trades.filter(profit_loss__gt=0).aggregate(
            avg=Avg('profit_loss')
        )['avg'] or Decimal('0')
        
        avg_loss = trades.filter(profit_loss__lt=0).aggregate(
            avg=Avg('profit_loss')
        )['avg'] or Decimal('0')
        
        # Calculate profit factor
        total_profit = sum(float(trade.profit_loss) for trade in trades.filter(profit_loss__gt=0))
        total_loss = abs(sum(float(trade.profit_loss) for trade in trades.filter(profit_loss__lt=0)))
        profit_factor = (total_profit / total_loss) if total_loss > 0 else 0
        
        # Calculate max drawdown (simplified)
        cumulative_pl = 0
        peak = 0
        max_drawdown = 0
        
        for trade in trades.order_by('timestamp'):
            cumulative_pl += float(trade.profit_loss) if trade.profit_loss else 0
            if cumulative_pl > peak:
                peak = cumulative_pl
            drawdown = peak - cumulative_pl
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return {
            'strategy_name': strategy_name,
            'period_days': days,
            'total_trades': total_trades,
            'executed_trades': executed_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': round(win_rate, 2),
            'total_pl': round(total_pl, 2),
            'avg_profit': float(avg_profit),
            'avg_loss': float(avg_loss),
            'profit_factor': round(profit_factor, 2),
            'max_drawdown': round(max_drawdown, 2),
            'signals_generated': signals.count(),
            'signals_executed': signals.filter(executed=True).count(),
        }
    
    def get_all_strategies_performance(self, days: int = 30) -> List[Dict]:
        """
        Get performance for all strategies
        
        Args:
            days: Number of days to analyze
        
        Returns:
            List of performance dictionaries for each strategy
        """
        strategies = Strategy.objects.all()
        results = []
        
        for strategy in strategies:
            perf = self.get_strategy_performance(strategy.name, days)
            if 'error' not in perf:
                results.append(perf)
        
        return results
    
    def get_daily_performance(self, date: Optional[datetime] = None) -> Dict:
        """
        Get performance for a specific day (Indian timezone)
        
        Args:
            date: Date to analyze (defaults to today in Indian timezone)
        
        Returns:
            Dictionary with daily performance metrics
        """
        # Always use Indian timezone
        now_indian = timezone.now().astimezone(INDIAN_TZ)
        if date is None:
            date = now_indian.date()
        
        # Create start and end of day in Indian timezone
        start_naive = datetime.combine(date, datetime.min.time())
        end_naive = datetime.combine(date, datetime.max.time())
        start = INDIAN_TZ.localize(start_naive)
        end = INDIAN_TZ.localize(end_naive)
        
        trades = LiveTrade.objects.filter(timestamp__range=[start, end])
        
        total_trades = trades.count()
        total_pl = sum(float(trade.profit_loss) for trade in trades if trade.profit_loss)
        
        winning_trades = trades.filter(profit_loss__gt=0).count()
        losing_trades = trades.filter(profit_loss__lt=0).count()
        
        return {
            'date': date,
            'total_trades': total_trades,
            'total_pl': round(total_pl, 2),
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': round((winning_trades / total_trades * 100) if total_trades > 0 else 0, 2),
        }
    
    def get_performance_summary(self, days: int = 30) -> Dict:
        """
        Get overall performance summary
        
        Args:
            days: Number of days to analyze
        
        Returns:
            Dictionary with overall performance summary
        """
        # Always use Indian timezone
        now_indian = timezone.now().astimezone(INDIAN_TZ)
        since = now_indian - timedelta(days=days)
        trades = LiveTrade.objects.filter(timestamp__gte=since)
        
        total_trades = trades.count()
        executed_trades = trades.filter(status='Executed').count()
        
        total_pl = sum(float(trade.profit_loss) for trade in trades if trade.profit_loss)
        
        winning_trades = trades.filter(profit_loss__gt=0).count()
        losing_trades = trades.filter(profit_loss__lt=0).count()
        
        # Calculate daily P/L
        daily_pl = {}
        for trade in trades:
            day = trade.timestamp.date()
            if day not in daily_pl:
                daily_pl[day] = 0
            daily_pl[day] += float(trade.profit_loss) if trade.profit_loss else 0
        
        best_day = max(daily_pl.items(), key=lambda x: x[1]) if daily_pl else (None, 0)
        worst_day = min(daily_pl.items(), key=lambda x: x[1]) if daily_pl else (None, 0)
        
        return {
            'period_days': days,
            'total_trades': total_trades,
            'executed_trades': executed_trades,
            'total_pl': round(total_pl, 2),
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': round((winning_trades / total_trades * 100) if total_trades > 0 else 0, 2),
            'best_day': {
                'date': best_day[0],
                'pl': round(best_day[1], 2),
            },
            'worst_day': {
                'date': worst_day[0],
                'pl': round(worst_day[1], 2),
            },
            'avg_daily_pl': round(total_pl / days, 2) if days > 0 else 0,
        }
    
    def compare_with_backtest(self, strategy_name: str) -> Dict:
        """
        Compare live performance with backtest results
        
        Args:
            strategy_name: Name of the strategy
        
        Returns:
            Dictionary with comparison metrics
        """
        # Get live performance
        live_perf = self.get_strategy_performance(strategy_name, days=30)
        
        # Get latest backtest result
        try:
            backtest = BacktestResult.objects.filter(
                strategy_name=strategy_name
            ).order_by('-timestamp').first()
        except BacktestResult.DoesNotExist:
            return {
                'strategy_name': strategy_name,
                'live_performance': live_perf,
                'backtest_available': False,
            }
        
        if not backtest:
            return {
                'strategy_name': strategy_name,
                'live_performance': live_perf,
                'backtest_available': False,
            }
        
        return {
            'strategy_name': strategy_name,
            'live_performance': live_perf,
            'backtest_performance': {
                'win_rate': backtest.win_rate,
                'profit_factor': backtest.profit_factor,
                'max_drawdown': backtest.max_drawdown,
                'total_trades': backtest.total_trades,
            },
            'comparison': {
                'win_rate_diff': round(live_perf.get('win_rate', 0) - backtest.win_rate, 2),
                'profit_factor_diff': round(live_perf.get('profit_factor', 0) - backtest.profit_factor, 2),
            },
        }
