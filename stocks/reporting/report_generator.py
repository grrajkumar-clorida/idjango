"""
Report Generator Module
Generates comprehensive trading reports (daily, weekly, monthly)
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
import pytz

from stocks.models import TradeJournal, Strategy, Orders, StrategySignal
from stocks.analytics.performance_analytics import PerformanceAnalytics
from stocks.utils.timezone_utils import INDIAN_TZ, now_indian, today_indian, get_day_start_end, days_ago_indian


class ReportGenerator:
    """Generate trading reports"""
    
    def __init__(self, strategy_id: Optional[int] = None):
        """
        Initialize report generator
        
        Args:
            strategy_id: Optional strategy ID to filter reports. If None, includes all strategies.
        """
        self.strategy_id = strategy_id
        self.analytics = PerformanceAnalytics(strategy_id)
    
    def generate_daily_report(self, date=None) -> Dict:
        """
        Generate daily trading report
        
        Args:
            date: Date for report (defaults to today in Indian timezone)
        
        Returns:
            Dictionary with daily report data
        """
        if date is None:
            date = today_indian()
        
        start, end = get_day_start_end(date)
        
        # Get trades for the day
        trades = TradeJournal.objects.filter(
            entry_date__gte=start,
            entry_date__lte=end
        )
        
        if self.strategy_id:
            trades = trades.filter(strategy_id=self.strategy_id)
        
        # Basic statistics
        total_trades = trades.count()
        winning_trades = trades.filter(win_loss='WIN').count()
        losing_trades = trades.filter(win_loss='LOSS').count()
        
        # P/L statistics
        total_pnl = trades.aggregate(total=Sum('net_pnl'))['total'] or Decimal('0.00')
        winning_pnl = trades.filter(win_loss='WIN').aggregate(total=Sum('net_pnl'))['total'] or Decimal('0.00')
        losing_pnl = trades.filter(win_loss='LOSS').aggregate(total=Sum('net_pnl'))['total'] or Decimal('0.00')
        
        # Volume statistics
        total_volume = trades.aggregate(total=Sum('quantity'))['total'] or 0
        total_value = trades.aggregate(
            total=Sum('entry_price') * Sum('quantity')
        )['total'] or Decimal('0.00')
        
        # Strategy breakdown
        strategy_breakdown = {}
        for trade in trades.select_related('strategy'):
            strategy_name = trade.strategy.name if trade.strategy else 'Unknown'
            if strategy_name not in strategy_breakdown:
                strategy_breakdown[strategy_name] = {
                    'trades': 0,
                    'pnl': Decimal('0.00'),
                    'win_rate': 0.0,
                }
            strategy_breakdown[strategy_name]['trades'] += 1
            strategy_breakdown[strategy_name]['pnl'] += trade.net_pnl
        
        # Calculate win rates for each strategy
        for strategy_name in strategy_breakdown:
            strategy_trades = trades.filter(strategy__name=strategy_name)
            wins = strategy_trades.filter(win_loss='WIN').count()
            total = strategy_trades.count()
            strategy_breakdown[strategy_name]['win_rate'] = (wins / total * 100) if total > 0 else 0.0
            strategy_breakdown[strategy_name]['pnl'] = float(strategy_breakdown[strategy_name]['pnl'])
        
        # Stock breakdown
        stock_breakdown = {}
        for trade in trades:
            if trade.stock_code not in stock_breakdown:
                stock_breakdown[trade.stock_code] = {
                    'trades': 0,
                    'pnl': Decimal('0.00'),
                }
            stock_breakdown[trade.stock_code]['trades'] += 1
            stock_breakdown[trade.stock_code]['pnl'] += trade.net_pnl
        
        for stock_code in stock_breakdown:
            stock_breakdown[stock_code]['pnl'] = float(stock_breakdown[stock_code]['pnl'])
        
        # Performance metrics
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        profit_factor = self.analytics.calculate_profit_factor(start, end)
        
        # Get signals generated
        signals = StrategySignal.objects.filter(
            timestamp__gte=start,
            timestamp__lte=end
        )
        if self.strategy_id:
            signals = signals.filter(strategy_id=self.strategy_id)
        
        total_signals = signals.count()
        executed_signals = signals.filter(executed=True).count()
        
        return {
            'report_type': 'daily',
            'date': date,
            'period': {
                'start': start,
                'end': end,
            },
            'summary': {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': round(win_rate, 2),
                'total_pnl': float(total_pnl),
                'winning_pnl': float(winning_pnl),
                'losing_pnl': float(losing_pnl),
                'profit_factor': profit_factor,
                'total_volume': total_volume,
                'total_value': float(total_value),
            },
            'signals': {
                'total': total_signals,
                'executed': executed_signals,
                'execution_rate': (executed_signals / total_signals * 100) if total_signals > 0 else 0.0,
            },
            'strategy_breakdown': strategy_breakdown,
            'stock_breakdown': stock_breakdown,
            'trades': list(trades.values(
                'stock_code', 'direction', 'entry_price', 'exit_price',
                'quantity', 'net_pnl', 'win_loss', 'entry_date'
            )),
        }
    
    def generate_weekly_report(self, week_start_date=None) -> Dict:
        """
        Generate weekly trading report
        
        Args:
            week_start_date: Start date of the week (defaults to Monday of current week)
        
        Returns:
            Dictionary with weekly report data
        """
        if week_start_date is None:
            today = today_indian()
            # Get Monday of current week
            days_since_monday = today.weekday()
            week_start_date = today - timedelta(days=days_since_monday)
        
        week_end_date = week_start_date + timedelta(days=6)
        start, _ = get_day_start_end(week_start_date)
        _, end = get_day_start_end(week_end_date)
        
        # Get daily reports for the week
        daily_reports = []
        current_date = week_start_date
        while current_date <= week_end_date:
            daily_report = self.generate_daily_report(current_date)
            daily_reports.append(daily_report)
            current_date += timedelta(days=1)
        
        # Aggregate weekly statistics
        total_trades = sum(r['summary']['total_trades'] for r in daily_reports)
        total_pnl = sum(r['summary']['total_pnl'] for r in daily_reports)
        total_volume = sum(r['summary']['total_volume'] for r in daily_reports)
        
        # Calculate average daily metrics
        avg_daily_trades = total_trades / 7 if len(daily_reports) > 0 else 0
        avg_daily_pnl = total_pnl / 7 if len(daily_reports) > 0 else 0
        
        # Performance analytics for the week
        weekly_analytics = self.analytics.get_comprehensive_metrics(start, end)
        
        return {
            'report_type': 'weekly',
            'week_start': week_start_date,
            'week_end': week_end_date,
            'period': {
                'start': start,
                'end': end,
            },
            'summary': {
                'total_trades': total_trades,
                'total_pnl': round(total_pnl, 2),
                'total_volume': total_volume,
                'avg_daily_trades': round(avg_daily_trades, 2),
                'avg_daily_pnl': round(avg_daily_pnl, 2),
            },
            'daily_reports': daily_reports,
            'performance_metrics': weekly_analytics,
        }
    
    def generate_monthly_report(self, year=None, month=None) -> Dict:
        """
        Generate monthly trading report
        
        Args:
            year: Year (defaults to current year)
            month: Month (1-12, defaults to current month)
        
        Returns:
            Dictionary with monthly report data
        """
        now = now_indian()
        if year is None:
            year = now.year
        if month is None:
            month = now.month
        
        # Get first and last day of month
        month_start = datetime(year, month, 1, tzinfo=INDIAN_TZ)
        if month == 12:
            month_end = datetime(year + 1, 1, 1, tzinfo=INDIAN_TZ) - timedelta(days=1)
        else:
            month_end = datetime(year, month + 1, 1, tzinfo=INDIAN_TZ) - timedelta(days=1)
        
        start, _ = get_day_start_end(month_start.date())
        _, end = get_day_start_end(month_end.date())
        
        # Get trades for the month
        trades = TradeJournal.objects.filter(
            entry_date__gte=start,
            entry_date__lte=end
        )
        
        if self.strategy_id:
            trades = trades.filter(strategy_id=self.strategy_id)
        
        # Aggregate statistics
        total_trades = trades.count()
        total_pnl = trades.aggregate(total=Sum('net_pnl'))['total'] or Decimal('0.00')
        total_volume = trades.aggregate(total=Sum('quantity'))['total'] or 0
        
        # Performance analytics
        monthly_analytics = self.analytics.get_comprehensive_metrics(start, end)
        
        # Weekly breakdown
        weekly_reports = []
        current_date = month_start.date()
        while current_date <= month_end.date():
            if current_date.weekday() == 0:  # Monday
                weekly_report = self.generate_weekly_report(current_date)
                weekly_reports.append(weekly_report)
            current_date += timedelta(days=1)
        
        # Best and worst days
        daily_pnl = {}
        for trade in trades:
            trade_date = trade.entry_date.date()
            if trade_date not in daily_pnl:
                daily_pnl[trade_date] = Decimal('0.00')
            daily_pnl[trade_date] += trade.net_pnl
        
        if daily_pnl:
            best_day = max(daily_pnl.items(), key=lambda x: x[1])
            worst_day = min(daily_pnl.items(), key=lambda x: x[1])
        else:
            best_day = (None, Decimal('0.00'))
            worst_day = (None, Decimal('0.00'))
        
        return {
            'report_type': 'monthly',
            'year': year,
            'month': month,
            'period': {
                'start': start,
                'end': end,
            },
            'summary': {
                'total_trades': total_trades,
                'total_pnl': float(total_pnl),
                'total_volume': total_volume,
                'avg_daily_trades': round(total_trades / month_end.day, 2) if month_end.day > 0 else 0,
                'avg_daily_pnl': round(float(total_pnl) / month_end.day, 2) if month_end.day > 0 else 0,
            },
            'performance_metrics': monthly_analytics,
            'weekly_reports': weekly_reports,
            'best_day': {
                'date': best_day[0],
                'pnl': float(best_day[1]),
            },
            'worst_day': {
                'date': worst_day[0],
                'pnl': float(worst_day[1]),
            },
        }
    
    def generate_custom_report(self, start_date, end_date) -> Dict:
        """
        Generate custom date range report
        
        Args:
            start_date: Start date
            end_date: End date
        
        Returns:
            Dictionary with custom report data
        """
        start, _ = get_day_start_end(start_date)
        _, end = get_day_start_end(end_date)
        
        # Get trades for the period
        trades = TradeJournal.objects.filter(
            entry_date__gte=start,
            entry_date__lte=end
        )
        
        if self.strategy_id:
            trades = trades.filter(strategy_id=self.strategy_id)
        
        # Aggregate statistics
        total_trades = trades.count()
        total_pnl = trades.aggregate(total=Sum('net_pnl'))['total'] or Decimal('0.00')
        
        # Performance analytics
        custom_analytics = self.analytics.get_comprehensive_metrics(start, end)
        
        return {
            'report_type': 'custom',
            'period': {
                'start': start,
                'end': end,
            },
            'summary': {
                'total_trades': total_trades,
                'total_pnl': float(total_pnl),
            },
            'performance_metrics': custom_analytics,
        }
