"""
Management command to test Celery tasks manually
"""
from django.core.management.base import BaseCommand
from stocks.tasks import (
    process_strategy_signals,
    execute_pending_signals,
    monitor_positions,
    update_trailing_stops,
    reconcile_positions,
    check_risk_limits,
    calculate_performance_metrics
)


class Command(BaseCommand):
    help = 'Test Celery tasks manually'

    def add_arguments(self, parser):
        parser.add_argument(
            '--task',
            type=str,
            choices=[
                'process_signals',
                'execute_signals',
                'monitor',
                'trailing_stops',
                'reconcile',
                'risk_limits',
                'performance',
                'all'
            ],
            default='all',
            help='Which task to run'
        )

    def handle(self, *args, **options):
        task_name = options['task']
        
        self.stdout.write(self.style.SUCCESS(f'Testing Celery task: {task_name}'))
        
        if task_name == 'process_signals' or task_name == 'all':
            self.stdout.write('\n1. Testing process_strategy_signals...')
            try:
                result = process_strategy_signals()
                self.stdout.write(self.style.SUCCESS(f'   Result: {result}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   Error: {e}'))
        
        if task_name == 'execute_signals' or task_name == 'all':
            self.stdout.write('\n2. Testing execute_pending_signals...')
            try:
                result = execute_pending_signals()
                self.stdout.write(self.style.SUCCESS(f'   Result: {result}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   Error: {e}'))
        
        if task_name == 'monitor' or task_name == 'all':
            self.stdout.write('\n3. Testing monitor_positions...')
            try:
                result = monitor_positions()
                self.stdout.write(self.style.SUCCESS(f'   Result: {result}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   Error: {e}'))
        
        if task_name == 'trailing_stops' or task_name == 'all':
            self.stdout.write('\n4. Testing update_trailing_stops...')
            try:
                result = update_trailing_stops()
                self.stdout.write(self.style.SUCCESS(f'   Result: {result}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   Error: {e}'))
        
        if task_name == 'reconcile' or task_name == 'all':
            self.stdout.write('\n5. Testing reconcile_positions...')
            try:
                result = reconcile_positions()
                self.stdout.write(self.style.SUCCESS(f'   Result: {result}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   Error: {e}'))
        
        if task_name == 'risk_limits' or task_name == 'all':
            self.stdout.write('\n6. Testing check_risk_limits...')
            try:
                result = check_risk_limits()
                self.stdout.write(self.style.SUCCESS(f'   Result: {result}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   Error: {e}'))
        
        if task_name == 'performance' or task_name == 'all':
            self.stdout.write('\n7. Testing calculate_performance_metrics...')
            try:
                result = calculate_performance_metrics()
                self.stdout.write(self.style.SUCCESS(f'   Result: {result}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   Error: {e}'))
        
        self.stdout.write(self.style.SUCCESS('\n✅ Task testing completed!'))
