"""
Management command to manually trigger 50MA automated trading
Usage: python manage.py auto_trade_50ma
Desc: --
"""
from django.core.management.base import BaseCommand
from data.engine.order_executor import OrderExecutor
from data.engine.position_monitor import PositionMonitor
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Execute automated 50MA trading (orders and position monitoring)"
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--orders-only',
            action='store_true',
            help='Only execute orders, skip position monitoring',
        )
        parser.add_argument(
            '--monitor-only',
            action='store_true',
            help='Only monitor positions, skip order execution',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting 50MA Automated Trading...'))
        
        orders_only = options.get('orders_only', False)
        monitor_only = options.get('monitor_only', False)
        
        # Execute orders
        if not monitor_only:
            self.stdout.write('Executing orders for status 8 stocks...')
            executor = OrderExecutor()
            order_results = executor.execute_orders_for_status_8()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Orders: {order_results['executed']} executed, "
                    f"{order_results['skipped']} skipped, "
                    f"{order_results['failed']} failed"
                )
            )
            
            # Print details
            for detail in order_results['details'][:10]:  # Show first 10
                status_style = self.style.SUCCESS if detail['status'] == 'executed' else self.style.WARNING
                self.stdout.write(
                    status_style(f"  {detail['script']}: {detail['status']} - {detail.get('reason', '')}")
                )
        
        # Monitor positions
        if not orders_only:
            self.stdout.write('Monitoring open positions...')
            monitor = PositionMonitor()
            monitor_results = monitor.monitor_all_positions()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Positions: {monitor_results['total']} total, "
                    f"{monitor_results['updated']} updated, "
                    f"{monitor_results['exited']} exited"
                )
            )
            
            # Print details
            for detail in monitor_results['details'][:10]:  # Show first 10
                if detail.get('action') == 'exited':
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  {detail['script']}: EXITED ({detail['exit_type']}) - {detail['exit_percent']}%"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  {detail['script']}: Status {detail.get('old_status')} -> {detail.get('new_status')}"
                        )
                    )
        
        self.stdout.write(self.style.SUCCESS('50MA Automated Trading completed!'))
