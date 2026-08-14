"""
Celery tasks for automated 50MA trading (Path A)
"""
from celery import shared_task
import logging
from django.core.management import call_command

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
        
        logger.info(
            f"50MA desk: queued={results.get('queued', 0)}, "
            f"executed={results.get('executed', 0)}, "
            f"skipped={results.get('skipped', 0)}, failed={results.get('failed', 0)}"
        )
        
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
        live_data_map = StockPriceData.latest_by_stock_code()
        
        stocks_with_positions = Stocks50MA.objects.filter(status__gte=8)
        
        updated_count = 0
        
        for stock in stocks_with_positions:
            live_data = live_data_map.get(stock.stock_code)
            
            if not live_data:
                continue
            
            from stocks.models import LiveTrade
            trade = LiveTrade.objects.filter(
                stock_code=stock.stock_code,
                status="Executed"
            ).first()
            
            entry_price = trade.price if trade else stock.stock_cmp
            
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


@shared_task(soft_time_limit=540, time_limit=600)
def ingest_50ma_eod():
    """
    After-market Path A ingest: ChartInk → CMP sheet → ICICI tickers.
    Scheduled ~16:30 IST.
    """
    try:
        logger.info("EOD ingest: get_chartink50ma")
        call_command("get_chartink50ma", "50ma")
        logger.info("EOD ingest: fetch_price_data")
        call_command("fetch_price_data")
        logger.info("EOD ingest: get_tickers")
        call_command("get_tickers")
        logger.info("EOD ingest complete")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"EOD 50MA ingest failed: {e}")
        return {"error": str(e)}


@shared_task(soft_time_limit=180, time_limit=240)
def ingest_price_data():
    """Refresh Google Finance CMPs and pre-trade statuses during market hours."""
    try:
        call_command("fetch_price_data")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"fetch_price_data failed: {e}")
        return {"error": str(e)}
