"""
Management command to enable/disable strategies and monitor signals
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from stocks.models import Strategy, StrategySignal
from stocks.engine.strategy_executor import StrategyExecutor
from stocks.monitoring.trade_monitor import TradeMonitor
from stocks.monitoring.performance_tracker import PerformanceTracker


class Command(BaseCommand):
    help = 'Manage strategies and monitor signals'

    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            choices=['list', 'enable', 'disable', 'status', 'signals', 'performance'],
            default='list',
            help='Action to perform'
        )
        parser.add_argument(
            '--strategy',
            type=str,
            help='Strategy name (required for enable/disable)'
        )
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Hours to look back for signals/performance (default: 24)'
        )

    def handle(self, *args, **options):
        action = options['action']
        strategy_name = options.get('strategy')
        hours = options['hours']
        
        if action == 'list':
            self.list_strategies()
        elif action == 'enable':
            if not strategy_name:
                self.stdout.write(self.style.ERROR('--strategy is required for enable action'))
                return
            self.enable_strategy(strategy_name)
        elif action == 'disable':
            if not strategy_name:
                self.stdout.write(self.style.ERROR('--strategy is required for disable action'))
                return
            self.disable_strategy(strategy_name)
        elif action == 'status':
            self.show_status()
        elif action == 'signals':
            self.show_signals(hours)
        elif action == 'performance':
            self.show_performance(hours)

    def list_strategies(self):
        """List all strategies"""
        self.stdout.write(self.style.SUCCESS('\n📊 Available Strategies:\n'))
        strategies = Strategy.objects.all()
        
        if not strategies.exists():
            self.stdout.write(self.style.WARNING('No strategies found in database.'))
            self.stdout.write('Create strategies using Django admin or management commands.')
            return
        
        for strategy in strategies:
            status = '✅ Enabled' if strategy.enabled else '❌ Disabled'
            self.stdout.write(f'  • {strategy.name} ({strategy.code}) - {status}')
            if strategy.description:
                self.stdout.write(f'    Description: {strategy.description}')
            self.stdout.write('')

    def enable_strategy(self, strategy_name):
        """Enable a strategy"""
        try:
            strategy = Strategy.objects.get(name=strategy_name)
            strategy.enabled = True
            strategy.save()
            self.stdout.write(self.style.SUCCESS(f'✅ Strategy "{strategy_name}" enabled'))
        except Strategy.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Strategy "{strategy_name}" not found'))
            self.stdout.write('Available strategies:')
            for s in Strategy.objects.all():
                self.stdout.write(f'  • {s.name}')

    def disable_strategy(self, strategy_name):
        """Disable a strategy"""
        try:
            strategy = Strategy.objects.get(name=strategy_name)
            strategy.enabled = False
            strategy.save()
            self.stdout.write(self.style.SUCCESS(f'✅ Strategy "{strategy_name}" disabled'))
        except Strategy.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Strategy "{strategy_name}" not found'))

    def show_status(self):
        """Show system status"""
        monitor = TradeMonitor()
        health = monitor.get_system_health()
        
        self.stdout.write(self.style.SUCCESS('\n📈 System Status:\n'))
        self.stdout.write(f'  Breeze API Status: {"✅ Active" if health["breeze_api_status"] else "❌ Inactive"}')
        self.stdout.write(f'  Active Trades: {health["active_trades"]}')
        self.stdout.write(f'  Pending Signals: {health["pending_signals"]}')
        self.stdout.write(f'  Last Update: {health["last_update"]}')
        
        # Show enabled strategies
        enabled = Strategy.objects.filter(enabled=True)
        self.stdout.write(f'\n  Enabled Strategies: {enabled.count()}')
        for strategy in enabled:
            self.stdout.write(f'    • {strategy.name}')

    def show_signals(self, hours):
        """Show recent signals"""
        monitor = TradeMonitor()
        signals = monitor.get_pending_signals()
        
        self.stdout.write(self.style.SUCCESS(f'\n📡 Signals (Last {hours} hours):\n'))
        
        if not signals:
            self.stdout.write(self.style.WARNING('No pending signals found.'))
            return
        
        for signal in signals[:10]:  # Show first 10
            status = '✅ Executed' if signal.get('executed') else '⏳ Pending'
            self.stdout.write(f'  • {signal["strategy"]} - {signal["stock_code"]}')
            self.stdout.write(f'    Type: {signal["signal_type"]} | Strength: {signal["strength"]:.2f}')
            self.stdout.write(f'    Price: {signal.get("price", "N/A")} | Status: {status}')
            self.stdout.write(f'    Time: {signal["timestamp"]}')
            self.stdout.write('')
        
        if len(signals) > 10:
            self.stdout.write(f'  ... and {len(signals) - 10} more signals')

    def show_performance(self, hours):
        """Show performance metrics"""
        tracker = PerformanceTracker()
        
        self.stdout.write(self.style.SUCCESS(f'\n📊 Performance Metrics (Last {hours} hours):\n'))
        
        # Overall performance
        summary = tracker.get_performance_summary(days=hours // 24 if hours >= 24 else 1)
        
        self.stdout.write('Overall Performance:')
        self.stdout.write(f'  Total Trades: {summary["total_trades"]}')
        self.stdout.write(f'  Executed Trades: {summary["executed_trades"]}')
        self.stdout.write(f'  Total P/L: ₹{summary["total_pl"]:.2f}')
        self.stdout.write(f'  Win Rate: {summary["win_rate"]}%')
        self.stdout.write(f'  Winning Trades: {summary["winning_trades"]}')
        self.stdout.write(f'  Losing Trades: {summary["losing_trades"]}')
        self.stdout.write('')
        
        # Strategy-wise performance
        strategies_perf = tracker.get_all_strategies_performance(days=hours // 24 if hours >= 24 else 1)
        
        if strategies_perf:
            self.stdout.write('Strategy-wise Performance:')
            for perf in strategies_perf:
                self.stdout.write(f'\n  {perf["strategy_name"]}:')
                self.stdout.write(f'    Total Trades: {perf["total_trades"]}')
                self.stdout.write(f'    Win Rate: {perf["win_rate"]}%')
                self.stdout.write(f'    Total P/L: ₹{perf["total_pl"]:.2f}')
                self.stdout.write(f'    Profit Factor: {perf["profit_factor"]:.2f}')
