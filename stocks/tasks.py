from celery import shared_task
import logging
from typing import List
from django.utils import timezone
from datetime import datetime

from .utils import fetch_and_store_stock_data
from .models import Strategy, StrategySignal, LiveTrade
from .engine.strategy_executor import StrategyExecutor
from .engine.signal_processor import SignalProcessor
from .strategies.registry import StrategyRegistry
from .strategies.strategy_aggregator import StrategyAggregator
from .strategies.signal_conflict_resolver import SignalConflictResolver
from .engine.order_manager import OrderManager
from .positions.exit_manager import ExitManager
from .positions.position_tracker import PositionTracker
from .monitoring.trade_monitor import TradeMonitor
from .monitoring.performance_tracker import PerformanceTracker
from .monitoring.alert_manager import AlertManager
from infra.utils.breeze_client import BreezeAPI
from data.strategies.ma50_strategy import PATH_A_STRATEGY_NAME

logger = logging.getLogger(__name__)


@shared_task
def scheduled_fetch_stock_data():
    stocks = ["ITC", "IOC", "TCS"]
    for stock in stocks:
        fetch_and_store_stock_data(stock, "NSE", "1day", 30)
    return "Stock data fetched successfully"


@shared_task
def process_strategy_signals():
    """
    Process all enabled strategies and generate signals
    This task runs periodically to check for new trading signals
    """
    try:
        executor = StrategyExecutor()
        processor = SignalProcessor()
        registry = StrategyRegistry()
        aggregator = StrategyAggregator(aggregation_method='weighted_average')
        conflict_resolver = SignalConflictResolver(resolution_method='strength_based')
        
        # Get all enabled strategies from registry
        enabled_strategies = Strategy.objects.filter(enabled=True)
        
        if not enabled_strategies.exists():
            logger.info("No enabled strategies found")
            return {"status": "success", "signals_generated": 0}
        
        # Register all enabled strategies with executor
        for strategy in enabled_strategies:
            try:
                # Path A owns 50MA (5-6% via data.tasks). Do not run the crossover adapter.
                if strategy.name == PATH_A_STRATEGY_NAME:
                    logger.info(
                        "Skipping %s in process_strategy_signals — owned by data.tasks",
                        strategy.name,
                    )
                    continue

                if executor.get_strategy(strategy.name):
                    continue
                
                logger.warning(f"Strategy adapter not implemented: {strategy.name}")
                continue
            except Exception as e:
                logger.error(f"Error registering strategy {strategy.name}: {e}")
                continue
        
        # Get list of stocks to check
        # For 50MA strategy, get stocks from Stocks50MA with status 7/8
        stocks_to_check = []
        
        # Check if 50MA strategy is enabled
        ma50_strategy = Strategy.objects.filter(name=PATH_A_STRATEGY_NAME, enabled=True).first()
        if ma50_strategy:
            logger.info(
                "50MA universe is owned by Path A (data.tasks); not loading adapter stocks"
            )
        
        # Fallback to default watchlist if no 50MA stocks
        if not stocks_to_check:
            stocks_to_check = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]  # Default watchlist
        
        # Collect all signals from all strategies
        all_signals = []
        signals_generated = 0
        
        for strategy in enabled_strategies:
            try:
                if strategy.name == PATH_A_STRATEGY_NAME:
                    continue

                # Get strategy instance from executor
                strategy_instance = executor.get_strategy(strategy.name)
                if not strategy_instance:
                    logger.warning(f"Strategy instance not found: {strategy.name}")
                    continue
                
                # Execute strategy for each stock
                for stock_code in stocks_to_check:
                    try:
                        # For 50MA strategy, call generate_signal directly (bypasses executor's data fetching)
                        if strategy.name == "50MA_Strategy":
                            signal = strategy_instance.generate_signal(
                                stock_code=stock_code,
                                exchange="NSE"
                            )
                            signals = signal if signal else None
                        else:
                            # For other strategies, use executor's execute_strategy
                            signals = executor.execute_strategy(
                                strategy.name, 
                                stock_code, 
                                "NSE"
                            )
                        
                        if signals:
                            # Process each signal
                            for signal in signals if isinstance(signals, list) else [signals]:
                                # Skip HOLD signals
                                if signal.get('action') == 'HOLD' and signal.get('strength', 0) < 0.5:
                                    continue
                                
                                # Validate signal
                                if not strategy_instance.validate_signal(signal):
                                    logger.debug(f"Signal validation failed for {strategy.name} - {stock_code}")
                                    continue
                                
                                processed = processor.process_signal(
                                    signal, 
                                    stock_code, 
                                    strategy.name
                                )
                                
                                if processed:
                                    # Collect signal for aggregation
                                    all_signals.append(processed)
                                    signals_generated += 1
                                    logger.info(f"Signal generated: {strategy.name} - {stock_code} - {processed.get('action')}")
                    
                    except Exception as e:
                        logger.error(f"Error processing {stock_code} for {strategy.name}: {e}")
                        AlertManager().alert_strategy_error(strategy.name, str(e))
            
            except Exception as e:
                logger.error(f"Error processing strategy {strategy.name}: {e}")
                AlertManager().alert_strategy_error(strategy.name, str(e))
        
        # Aggregate signals from multiple strategies
        if all_signals:
            # Group signals by stock code
            stock_signals = {}
            for signal in all_signals:
                stock_code = signal.get('stock_code')
                if stock_code not in stock_signals:
                    stock_signals[stock_code] = []
                stock_signals[stock_code].append(signal)
            
            # Process each stock's signals
            for stock_code, sigs in stock_signals.items():
                if len(sigs) > 1:
                    # Multiple strategies - aggregate
                    aggregated = aggregator.aggregate_signals(sigs)
                    if aggregated:
                        # Resolve any conflicts
                        resolved = conflict_resolver.resolve_conflicts([aggregated])
                        
                        for resolved_signal in resolved:
                            # Find the primary strategy (first one)
                            primary_strategy = enabled_strategies.first()
                            if resolved_signal.get('strategies'):
                                try:
                                    primary_strategy = Strategy.objects.get(
                                        name=resolved_signal['strategies'][0]
                                    )
                                except Strategy.DoesNotExist:
                                    pass
                            
                            # Save aggregated signal
                            StrategySignal.objects.create(
                                strategy=primary_strategy,
                                stock_code=stock_code,
                                signal_type=resolved_signal.get('action', 'HOLD'),
                                strength=resolved_signal.get('strength', 0.5),
                                price=resolved_signal.get('price'),
                                stop_loss=resolved_signal.get('stop_loss'),
                                take_profit=resolved_signal.get('take_profit'),
                                metadata={
                                    **resolved_signal.get('metadata', {}),
                                    'aggregated': True,
                                    'signal_count': len(sigs),
                                    'strategies': resolved_signal.get('strategies', [])
                                },
                            )
                            logger.info(f"Aggregated signal: {stock_code} - {resolved_signal.get('action')} from {len(sigs)} strategies")
                else:
                    # Single signal - save directly
                    signal = sigs[0]
                    strategy_name = signal.get('strategy_name')
                    try:
                        strategy_obj = Strategy.objects.get(name=strategy_name)
                    except Strategy.DoesNotExist:
                        strategy_obj = enabled_strategies.first()
                    
                    StrategySignal.objects.create(
                        strategy=strategy_obj,
                        stock_code=stock_code,
                        signal_type=signal.get('action', 'HOLD'),
                        strength=signal.get('strength', 0.5),
                        price=signal.get('price'),
                        stop_loss=signal.get('stop_loss'),
                        take_profit=signal.get('take_profit'),
                        metadata=signal.get('metadata', {}),
                    )
        
        logger.info(f"Generated {signals_generated} signals, aggregated {len(stock_signals)} stocks")
        return {"status": "success", "signals_generated": signals_generated}
    
    except Exception as e:
        logger.error(f"Error in process_strategy_signals: {e}")
        return {"status": "error", "error": str(e)}


@shared_task
def execute_pending_signals():
    """
    Execute validated signals that haven't been executed yet
    """
    try:
        order_manager = OrderManager()
        alert_manager = AlertManager()
        
        # Get pending signals
        pending_signals = StrategySignal.objects.filter(
            executed=False,
            signal_type__in=['BUY', 'SELL']
        ).order_by('timestamp')
        
        executed_count = 0
        failed_count = 0
        
        for signal in pending_signals:
            try:
                if signal.strategy and signal.strategy.name == PATH_A_STRATEGY_NAME:
                    continue

                # Convert signal to order format
                signal_dict = {
                    'action': signal.signal_type,
                    'price': signal.price or 0,
                    'stop_loss': signal.stop_loss,
                    'take_profit': signal.take_profit,
                    'order_type': 'MARKET',
                    'strategy_name': signal.strategy.name,
                }
                
                # Execute signal
                result = order_manager.execute_signal(
                    signal_dict,
                    signal.stock_code,
                    "NSE"
                )
                
                if result.get('success'):
                    signal.executed = True
                    signal.executed_at = timezone.now()
                    if result.get('trade_id'):
                        try:
                            signal.trade = LiveTrade.objects.get(id=result['trade_id'])
                        except LiveTrade.DoesNotExist:
                            pass
                    signal.save()
                    
                    # Get trade and send alert
                    if result.get('trade_id'):
                        try:
                            trade = LiveTrade.objects.get(id=result['trade_id'])
                            alert_manager.alert_trade_executed(trade)
                        except LiveTrade.DoesNotExist:
                            pass
                    
                    executed_count += 1
                else:
                    logger.warning(f"Failed to execute signal {signal.id}: {result.get('error')}")
                    failed_count += 1
                    
                    # Alert on failure
                    if result.get('trade_id'):
                        try:
                            trade = LiveTrade.objects.get(id=result['trade_id'])
                            alert_manager.alert_order_failed(trade, result.get('error', 'Unknown error'))
                        except LiveTrade.DoesNotExist:
                            pass
            
            except Exception as e:
                logger.error(f"Error executing signal {signal.id}: {e}")
                failed_count += 1
        
        logger.info(f"Executed {executed_count} signals, {failed_count} failed")
        return {
            "status": "success",
            "executed": executed_count,
            "failed": failed_count
        }
    
    except Exception as e:
        logger.error(f"Error in execute_pending_signals: {e}")
        return {"status": "error", "error": str(e)}


@shared_task
def monitor_positions():
    """
    Monitor open positions and execute exits (stop-loss, take-profit)
    """
    try:
        exit_manager = ExitManager()
        position_tracker = PositionTracker()
        alert_manager = AlertManager()
        breeze = BreezeAPI()
        
        if not breeze.api_status:
            logger.warning("Breeze API not available for position monitoring")
            return {"status": "error", "error": "API not available"}
        
        # Get all open positions
        positions = position_tracker.get_all_positions()
        
        exits_executed = 0
        
        for position in positions:
            try:
                # Get current price
                current_price = position_tracker.get_current_price(
                    position.stock_code,
                    position.exchange
                )
                
                if not current_price:
                    logger.warning(f"Could not get current price for {position.stock_code}")
                    continue
                
                # Update P/L
                position_tracker.update_position_pnl(position, current_price)
                
                # Get strategy name and 50MA value for strategy-specific exits
                strategy_name = None
                ma50_value = None
                
                try:
                    from stocks.models import StrategySignal
                    signal = StrategySignal.objects.filter(trade=position).first()
                    if signal and signal.strategy:
                        strategy_name = signal.strategy.name
                        
                        # For 50MA strategy, get 50MA value
                        if strategy_name == "50MA_Strategy":
                            from data.models import StockPriceData
                            latest_data = StockPriceData.objects.filter(
                                stock_code=position.stock_code
                            ).order_by('-date').first()
                            if latest_data and latest_data.live50ma:
                                ma50_value = latest_data.live50ma
                except Exception as e:
                    logger.debug(f"Could not get strategy info for {position.stock_code}: {e}")
                
                # Monitor exits with strategy-specific logic
                exit_result = exit_manager.monitor_exits(
                    position, 
                    current_price,
                    strategy_name=strategy_name,
                    ma50_value=ma50_value
                )
                
                if exit_result and exit_result.get('success'):
                    exit_reason = exit_result.get('exit_reason', 'Exit executed')
                    exit_type = 'take_profit' if 'profit' in exit_reason.lower() else 'other'
                    
                    # Send alerts based on exit type
                    if 'stop_loss' in exit_reason.lower():
                        alert_manager.alert_stop_loss_hit(position, current_price)
                    elif 'profit' in exit_reason.lower() or '6-12%' in exit_reason:
                        alert_manager.alert_take_profit_hit(position, current_price)
                    elif 'bottom value' in exit_reason.lower():
                        # Partial exit alert
                        alert_manager.send_alert(
                            'PARTIAL_EXIT',
                            f"50MA Partial Exit: {position.stock_code} - {exit_reason}",
                            severity='INFO',
                            data={'position_id': position.id, 'exit_reason': exit_reason}
                        )
                    
                    exits_executed += 1
                    logger.info(f"Exit executed for {position.stock_code}: {exit_reason}")
            
            except Exception as e:
                logger.error(f"Error monitoring position {position.id}: {e}")
        
        logger.info(f"Monitored {len(positions)} positions, executed {exits_executed} exits")
        return {
            "status": "success",
            "positions_monitored": len(positions),
            "exits_executed": exits_executed
        }
    
    except Exception as e:
        logger.error(f"Error in monitor_positions: {e}")
        return {"status": "error", "error": str(e)}


@shared_task
def update_trailing_stops():
    """
    Update trailing stop-loss orders for profitable positions
    """
    try:
        exit_manager = ExitManager()
        position_tracker = PositionTracker()
        breeze = BreezeAPI()
        
        if not breeze.api_status:
            logger.warning("Breeze API not available for trailing stop update")
            return {"status": "error", "error": "API not available"}
        
        # Get positions with trailing stop-loss
        positions = LiveTrade.objects.filter(
            status='Executed',
            trailing_stop_loss__isnull=False
        )
        
        updated_count = 0
        
        for position in positions:
            try:
                # Get current price
                current_price = position_tracker.get_current_price(
                    position.stock_code,
                    position.exchange
                )
                
                if not current_price:
                    continue
                
                # Update trailing stop
                updated = exit_manager.update_trailing_stop(position, current_price)
                
                if updated:
                    updated_count += 1
            
            except Exception as e:
                logger.error(f"Error updating trailing stop for position {position.id}: {e}")
        
        logger.info(f"Updated {updated_count} trailing stops")
        return {
            "status": "success",
            "updated": updated_count
        }
    
    except Exception as e:
        logger.error(f"Error in update_trailing_stops: {e}")
        return {"status": "error", "error": str(e)}


@shared_task
def calculate_performance_metrics():
    """
    Calculate and store performance metrics
    Runs at end of trading day
    """
    try:
        performance_tracker = PerformanceTracker()
        
        # Calculate daily performance
        daily_perf = performance_tracker.get_daily_performance()
        
        # Calculate strategy performance
        strategies_perf = performance_tracker.get_all_strategies_performance(days=1)
        
        logger.info(f"Calculated performance metrics for {len(strategies_perf)} strategies")
        return {
            "status": "success",
            "daily_performance": daily_perf,
            "strategies_count": len(strategies_perf)
        }
    
    except Exception as e:
        logger.error(f"Error in calculate_performance_metrics: {e}")
        return {"status": "error", "error": str(e)}


@shared_task
def reconcile_positions():
    """
    Reconcile positions with broker
    """
    try:
        trade_monitor = TradeMonitor()
        
        # Update trade statuses from broker
        result = trade_monitor.update_trade_statuses()
        
        logger.info(f"Reconciled positions: {result['updated']} updated, {result['errors']} errors")
        return {
            "status": "success",
            **result
        }
    
    except Exception as e:
        logger.error(f"Error in reconcile_positions: {e}")
        return {"status": "error", "error": str(e)}


@shared_task
def check_risk_limits():
    """
    Check risk limits and generate alerts if breached
    """
    try:
        alert_manager = AlertManager()
        
        # Check all risk limits
        breaches = alert_manager.check_risk_limits()
        
        logger.info(f"Checked risk limits: {len(breaches)} breaches found")
        return {
            "status": "success",
            "breaches": len(breaches),
            "details": breaches
        }
    
    except Exception as e:
        logger.error(f"Error in check_risk_limits: {e}")
        return {"status": "error", "error": str(e)}
