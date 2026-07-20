"""
Celery tasks for automated 50MA trading
"""
from celery import shared_task
import logging
from data.engine.order_executor import OrderExecutor
from data.engine.position_monitor import PositionMonitor

logger = logging.getLogger(__name__)


@shared_task
def execute_50ma_orders():
    """
    Execute orders for stocks with status 8 (Order ready)
    Runs every minute during market hours
    """
    try:
        executor = OrderExecutor()
        results = executor.execute_orders_for_status_8()
        
        logger.info(f"50MA Order Execution: {results['executed']} executed, "
                   f"{results['skipped']} skipped, {results['failed']} failed")
        
        return results
    except Exception as e:
        logger.error(f"Error executing 50MA orders: {str(e)}")
        return {'error': str(e)}


@shared_task
def monitor_50ma_positions():
    """
    Monitor all open 50MA positions and update statuses
    Runs every minute during market hours
    """
    try:
        monitor = PositionMonitor()
        results = monitor.monitor_all_positions()
        
        logger.info(f"50MA Position Monitoring: {results['total']} positions, "
                   f"{results['updated']} updated, {results['exited']} exited")
        
        return results
    except Exception as e:
        logger.error(f"Error monitoring 50MA positions: {str(e)}")
        return {'error': str(e)}


@shared_task
def update_50ma_statuses():
    """
    Update stock statuses based on price movements
    This complements the fetch_price_data command
    """
    try:
        from data.models import Stocks50MA, StockPriceData
        from data.strategies.ma50_strategy import MA50Strategy
        
        strategy = MA50Strategy()
        
        # Get live data map
        live_data_map = {
            spd.script: spd for spd in StockPriceData.objects.all()
        }
        
        # Get all stocks with open positions (status >= 8)
        stocks_with_positions = Stocks50MA.objects.filter(status__gte=8)
        
        updated_count = 0
        
        for stock in stocks_with_positions:
            live_data = live_data_map.get(stock.script)
            
            if not live_data:
                continue
            
            # Get entry price from LiveTrade
            from stocks.models import LiveTrade
            trade = LiveTrade.objects.filter(
                stock_code=stock.script,
                status="Executed"
            ).first()
            
            entry_price = trade.price if trade else stock.stock_cmp
            
            # Update status based on current price
            new_status = strategy.update_status_based_on_price(
                stock,
                live_data,
                float(entry_price) if entry_price else None
            )
            
            if new_status != stock.status:
                stock.status = new_status
                stock.save()
                updated_count += 1
        
        logger.info(f"Updated {updated_count} stock statuses")
        return {'updated': updated_count}
        
    except Exception as e:
        logger.error(f"Error updating 50MA statuses: {str(e)}")
        return {'error': str(e)}
