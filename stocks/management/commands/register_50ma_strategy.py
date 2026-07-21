"""
Management command to register 50MA strategy with Phase 2 system
"""
from django.core.management.base import BaseCommand
from stocks.models import Strategy
from stocks.strategies.ma50_strategy_adapter import MA50StrategyAdapter
from stocks.engine.strategy_executor import StrategyExecutor


class Command(BaseCommand):
    help = 'Register 50MA strategy with Phase 2 system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--enable',
            action='store_true',
            help='Enable the strategy after registration',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Registering 50MA Strategy...'))
        
        # Create or update strategy in database
        strategy, created = Strategy.objects.get_or_create(
            name="50MA_Strategy",
            defaults={
                'code': 'ma50',
                'enabled': options.get('enable', False),
                'description': '50-day Moving Average Crossover Strategy - Entry after crossing above 50MA',
                'parameters': {
                    'price_change_min': 1.0,  # Minimum 1% price change
                    'price_change_max': 5.0,  # Maximum 5% price change
                }
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'✅ Strategy "{strategy.name}" created'))
        else:
            self.stdout.write(self.style.SUCCESS(f'✅ Strategy "{strategy.name}" already exists'))
            # Update parameters if needed
            strategy.parameters = {
                'price_change_min': 1.0,  # Minimum 1% price change
                'price_change_max': 5.0,  # Maximum 5% price change
            }
            strategy.save()
        
        # Register with StrategyExecutor
        try:
            executor = StrategyExecutor()
            strategy_instance = MA50StrategyAdapter(
                enabled=strategy.enabled,
                **strategy.parameters
            )
            executor.register_strategy(strategy_instance)
            self.stdout.write(self.style.SUCCESS('✅ Strategy registered with StrategyExecutor'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error registering strategy: {e}'))
            return
        
        # Show strategy info
        info = strategy_instance.get_strategy_info()
        self.stdout.write('\n📊 Strategy Information:')
        self.stdout.write(f'  Name: {info["name"]}')
        self.stdout.write(f'  Description: {info["description"]}')
        self.stdout.write('\n  Entry Conditions:')
        for condition in info['entry_conditions']:
            self.stdout.write(f'    • {condition}')
        self.stdout.write('\n  Exit Conditions:')
        for condition in info['exit_conditions']:
            self.stdout.write(f'    • {condition}')
        
        # Show stocks to check
        stocks_to_check = strategy_instance.get_stocks_to_check()
        self.stdout.write(f'\n📈 Stocks Ready for Entry (Status 7/8): {len(stocks_to_check)}')
        if stocks_to_check:
            self.stdout.write(f'  Examples: {", ".join(stocks_to_check[:10])}')
            if len(stocks_to_check) > 10:
                self.stdout.write(f'  ... and {len(stocks_to_check) - 10} more')
        
        self.stdout.write('\n' + self.style.SUCCESS('✅ 50MA Strategy registration complete!'))
        
        if strategy.enabled:
            self.stdout.write(self.style.SUCCESS('✅ Strategy is ENABLED and will generate signals'))
        else:
            self.stdout.write(self.style.WARNING('⚠️  Strategy is DISABLED. Enable it to generate signals:'))
            self.stdout.write(f'   python manage.py manage_strategies --action=enable --strategy={strategy.name}')
