"""
REST API Views for Trading System
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import datetime, timedelta

from stocks.models import Strategy, StrategySignal, LiveTrade, RiskLimits
from stocks.strategies.registry import StrategyRegistry
from stocks.monitoring.trade_monitor import TradeMonitor
from stocks.monitoring.performance_tracker import PerformanceTracker
from stocks.risk.risk_manager import RiskManager
from stocks.positions.position_tracker import PositionTracker
from stocks.positions.exit_manager import ExitManager
from stocks.engine.order_manager import OrderManager
from stocks.monitoring.alert_manager import AlertManager

logger = logging.getLogger(__name__)


def api_response(success=True, data=None, message=None, status_code=200):
    """Standard API response format"""
    response_data = {
        'success': success,
        'timestamp': timezone.now().isoformat()
    }
    
    if data is not None:
        response_data['data'] = data
    
    if message:
        response_data['message'] = message
    
    return JsonResponse(response_data, status=status_code)


# Strategy Management Endpoints

@require_http_methods(["GET"])
def list_strategies(request):
    """List all strategies"""
    try:
        strategies = Strategy.objects.all()
        
        data = []
        for strategy in strategies:
            data.append({
                'id': strategy.id,
                'name': strategy.name,
                'code': strategy.code,
                'enabled': strategy.enabled,
                'description': strategy.description,
                'parameters': strategy.parameters,
                'created_at': strategy.created_at.isoformat() if strategy.created_at else None,
                'updated_at': strategy.updated_at.isoformat() if strategy.updated_at else None,
                'signal_count': strategy.signals.count()
            })
        
        return api_response(data={'strategies': data, 'total': len(data)})
    
    except Exception as e:
        logger.error(f"Error listing strategies: {e}")
        return api_response(success=False, message=str(e), status_code=500)


@require_http_methods(["GET"])
def get_strategy_status(request, strategy_id):
    """Get strategy status and details"""
    try:
        strategy = Strategy.objects.get(id=strategy_id)
        
        registry = StrategyRegistry()
        strategy_info = registry.get_strategy_info(strategy.name)
        
        # Get recent signals
        recent_signals = strategy.signals.order_by('-timestamp')[:10]
        signals_data = []
        for signal in recent_signals:
            signals_data.append({
                'id': signal.id,
                'stock_code': signal.stock_code,
                'signal_type': signal.signal_type,
                'strength': signal.strength,
                'price': signal.price,
                'executed': signal.executed,
                'timestamp': signal.timestamp.isoformat() if signal.timestamp else None
            })
        
        data = {
            'strategy': {
                'id': strategy.id,
                'name': strategy.name,
                'code': strategy.code,
                'enabled': strategy.enabled,
                'description': strategy.description,
                'parameters': strategy.parameters
            },
            'info': strategy_info,
            'recent_signals': signals_data,
            'total_signals': strategy.signals.count(),
            'executed_signals': strategy.signals.filter(executed=True).count()
        }
        
        return api_response(data=data)
    
    except Strategy.DoesNotExist:
        return api_response(success=False, message="Strategy not found", status_code=404)
    except Exception as e:
        logger.error(f"Error getting strategy status: {e}")
        return api_response(success=False, message=str(e), status_code=500)


@csrf_exempt
@require_http_methods(["POST"])
def enable_strategy(request, strategy_id):
    """Enable a strategy"""
    try:
        strategy = Strategy.objects.get(id=strategy_id)
        strategy.enabled = True
        strategy.save()
        
        # Refresh registry
        registry = StrategyRegistry()
        registry.refresh()
        
        return api_response(
            data={'strategy_id': strategy.id, 'enabled': True},
            message=f"Strategy '{strategy.name}' enabled"
        )
    
    except Strategy.DoesNotExist:
        return api_response(success=False, message="Strategy not found", status_code=404)
    except Exception as e:
        logger.error(f"Error enabling strategy: {e}")
        return api_response(success=False, message=str(e), status_code=500)


@csrf_exempt
@require_http_methods(["POST"])
def disable_strategy(request, strategy_id):
    """Disable a strategy"""
    try:
        strategy = Strategy.objects.get(id=strategy_id)
        strategy.enabled = False
        strategy.save()
        
        # Refresh registry
        registry = StrategyRegistry()
        registry.refresh()
        
        return api_response(
            data={'strategy_id': strategy.id, 'enabled': False},
            message=f"Strategy '{strategy.name}' disabled"
        )
    
    except Strategy.DoesNotExist:
        return api_response(success=False, message="Strategy not found", status_code=404)
    except Exception as e:
        logger.error(f"Error disabling strategy: {e}")
        return api_response(success=False, message=str(e), status_code=500)


@csrf_exempt
@require_http_methods(["POST"])
def register_strategy(request):
    """Register a new strategy"""
    try:
        body = json.loads(request.body)
        
        name = body.get('name')
        code = body.get('code', name.lower().replace(' ', '_'))
        description = body.get('description', '')
        parameters = body.get('parameters', {})
        enabled = body.get('enabled', False)
        
        if not name:
            return api_response(success=False, message="Strategy name is required", status_code=400)
        
        strategy, created = Strategy.objects.get_or_create(
            name=name,
            defaults={
                'code': code,
                'description': description,
                'parameters': parameters,
                'enabled': enabled
            }
        )
        
        if not created:
            # Update existing
            strategy.description = description
            strategy.parameters = parameters
            strategy.enabled = enabled
            strategy.save()
        
        # Refresh registry
        registry = StrategyRegistry()
        registry.refresh()
        
        return api_response(
            data={
                'strategy_id': strategy.id,
                'name': strategy.name,
                'code': strategy.code,
                'enabled': strategy.enabled,
                'created': created
            },
            message=f"Strategy '{strategy.name}' {'registered' if created else 'updated'}"
        )
    
    except json.JSONDecodeError:
        return api_response(success=False, message="Invalid JSON", status_code=400)
    except Exception as e:
        logger.error(f"Error registering strategy: {e}")
        return api_response(success=False, message=str(e), status_code=500)


# Position Management Endpoints

@require_http_methods(["GET"])
def list_positions(request):
    """Get all open positions"""
    try:
        tracker = PositionTracker()
        positions = tracker.get_all_positions()
        
        data = []
        for position in positions:
            # Get current price and update P/L
            current_price = tracker.get_current_price(position.stock_code, position.exchange)
            if current_price:
                tracker.update_position_pnl(position, current_price)
            
            data.append({
                'id': position.id,
                'stock_code': position.stock_code,
                'exchange': position.exchange,
                'action': position.action,
                'quantity': position.quantity,
                'price': float(position.price) if position.price else None,
                'current_price': current_price,
                'profit_loss': float(position.profit_loss) if position.profit_loss else 0,
                'stop_loss': float(position.stop_loss) if position.stop_loss else None,
                'take_profit': float(position.take_profit) if position.take_profit else None,
                'status': position.status,
                'timestamp': position.timestamp.isoformat() if position.timestamp else None
            })
        
        return api_response(data={'positions': data, 'total': len(data)})
    
    except Exception as e:
        logger.error(f"Error listing positions: {e}")
        return api_response(success=False, message=str(e), status_code=500)


@require_http_methods(["GET"])
def get_position_details(request, position_id):
    """Get position details"""
    try:
        position = LiveTrade.objects.get(id=position_id)
        tracker = PositionTracker()
        
        current_price = tracker.get_current_price(position.stock_code, position.exchange)
        if current_price:
            tracker.update_position_pnl(position, current_price)
        
        # Get related signal
        signal = None
        try:
            signal_obj = StrategySignal.objects.filter(trade=position).first()
            if signal_obj:
                signal = {
                    'id': signal_obj.id,
                    'strategy': signal_obj.strategy.name,
                    'signal_type': signal_obj.signal_type,
                    'strength': signal_obj.strength,
                    'timestamp': signal_obj.timestamp.isoformat() if signal_obj.timestamp else None
                }
        except Exception:
            pass
        
        data = {
            'id': position.id,
            'stock_code': position.stock_code,
            'exchange': position.exchange,
            'action': position.action,
            'quantity': position.quantity,
            'price': float(position.price) if position.price else None,
            'current_price': current_price,
            'profit_loss': float(position.profit_loss) if position.profit_loss else 0,
            'profit_percent': ((current_price - float(position.price)) / float(position.price) * 100) if current_price and position.price else None,
            'stop_loss': float(position.stop_loss) if position.stop_loss else None,
            'take_profit': float(position.take_profit) if position.take_profit else None,
            'trailing_stop_loss': float(position.trailing_stop_loss) if position.trailing_stop_loss else None,
            'status': position.status,
            'timestamp': position.timestamp.isoformat() if position.timestamp else None,
            'signal': signal
        }
        
        return api_response(data=data)
    
    except LiveTrade.DoesNotExist:
        return api_response(success=False, message="Position not found", status_code=404)
    except Exception as e:
        logger.error(f"Error getting position details: {e}")
        return api_response(success=False, message=str(e), status_code=500)


@csrf_exempt
@require_http_methods(["POST"])
def close_position(request, position_id):
    """Close a position"""
    try:
        position = LiveTrade.objects.get(id=position_id)
        
        if position.status != "Executed":
            return api_response(success=False, message="Position is not open", status_code=400)
        
        exit_manager = ExitManager()
        tracker = PositionTracker()
        
        current_price = tracker.get_current_price(position.stock_code, position.exchange)
        if not current_price:
            return api_response(success=False, message="Could not get current price", status_code=400)
        
        result = exit_manager.execute_exit(position, "Manual close")
        
        if result.get('success'):
            return api_response(
                data={
                    'position_id': position.id,
                    'order_id': result.get('order_id'),
                    'quantity': result.get('quantity')
                },
                message="Position closed successfully"
            )
        else:
            return api_response(
                success=False,
                message=result.get('error', 'Failed to close position'),
                status_code=400
            )
    
    except LiveTrade.DoesNotExist:
        return api_response(success=False, message="Position not found", status_code=404)
    except Exception as e:
        logger.error(f"Error closing position: {e}")
        return api_response(success=False, message=str(e), status_code=500)


# Performance Endpoints

@require_http_methods(["GET"])
def get_performance(request):
    """Get performance metrics"""
    try:
        days = int(request.GET.get('days', 30))
        
        tracker = PerformanceTracker()
        summary = tracker.get_performance_summary(days=days)
        
        return api_response(data=summary)
    
    except Exception as e:
        logger.error(f"Error getting performance: {e}")
        return api_response(success=False, message=str(e), status_code=500)


@require_http_methods(["GET"])
def get_strategy_performance(request, strategy_id):
    """Get performance for a specific strategy"""
    try:
        strategy = Strategy.objects.get(id=strategy_id)
        days = int(request.GET.get('days', 30))
        
        tracker = PerformanceTracker()
        performance = tracker.get_strategy_performance(strategy.name, days=days)
        
        return api_response(data=performance)
    
    except Strategy.DoesNotExist:
        return api_response(success=False, message="Strategy not found", status_code=404)
    except Exception as e:
        logger.error(f"Error getting strategy performance: {e}")
        return api_response(success=False, message=str(e), status_code=500)


# Risk Management Endpoints

@require_http_methods(["GET"])
def get_risk_exposure(request):
    """Get current risk exposure"""
    try:
        risk_manager = RiskManager()
        exposure = risk_manager.get_current_exposure()
        
        # Get risk limits
        limits = RiskLimits.objects.first()
        limits_data = None
        if limits:
            limits_data = {
                'max_position_size': float(limits.max_position_size) if limits.max_position_size else None,
                'max_portfolio_exposure': float(limits.max_portfolio_exposure) if limits.max_portfolio_exposure else None,
                'max_daily_loss': float(limits.max_daily_loss) if limits.max_daily_loss else None,
                'max_drawdown': float(limits.max_drawdown) if limits.max_drawdown else None
            }
        
        data = {
            'exposure': exposure,
            'limits': limits_data
        }
        
        return api_response(data=data)
    
    except Exception as e:
        logger.error(f"Error getting risk exposure: {e}")
        return api_response(success=False, message=str(e), status_code=500)


@csrf_exempt
@require_http_methods(["POST"])
def set_risk_limits(request):
    """Set risk limits"""
    try:
        body = json.loads(request.body)
        
        limits, created = RiskLimits.objects.get_or_create(id=1)
        
        if 'max_position_size' in body:
            limits.max_position_size = body['max_position_size']
        if 'max_portfolio_exposure' in body:
            limits.max_portfolio_exposure = body['max_portfolio_exposure']
        if 'max_daily_loss' in body:
            limits.max_daily_loss = body['max_daily_loss']
        if 'max_drawdown' in body:
            limits.max_drawdown = body['max_drawdown']
        
        limits.save()
        
        return api_response(
            data={
                'max_position_size': float(limits.max_position_size) if limits.max_position_size else None,
                'max_portfolio_exposure': float(limits.max_portfolio_exposure) if limits.max_portfolio_exposure else None,
                'max_daily_loss': float(limits.max_daily_loss) if limits.max_daily_loss else None,
                'max_drawdown': float(limits.max_drawdown) if limits.max_drawdown else None
            },
            message="Risk limits updated"
        )
    
    except json.JSONDecodeError:
        return api_response(success=False, message="Invalid JSON", status_code=400)
    except Exception as e:
        logger.error(f"Error setting risk limits: {e}")
        return api_response(success=False, message=str(e), status_code=500)


# Manual Override Endpoints

@csrf_exempt
@require_http_methods(["POST"])
def manual_trade(request):
    """Place a manual trade"""
    try:
        body = json.loads(request.body)
        
        stock_code = body.get('stock_code')
        exchange = body.get('exchange', 'NSE')
        action = body.get('action')  # BUY or SELL
        quantity = body.get('quantity')
        order_type = body.get('order_type', 'MARKET')
        price = body.get('price', 0)
        stop_loss = body.get('stop_loss')
        take_profit = body.get('take_profit')
        
        if not all([stock_code, action, quantity]):
            return api_response(success=False, message="Missing required fields", status_code=400)
        
        order_manager = OrderManager()
        
        signal_dict = {
            'action': action,
            'price': price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'order_type': order_type,
            'strategy_name': 'Manual'
        }
        
        result = order_manager.execute_signal(signal_dict, stock_code, exchange)
        
        if result.get('success'):
            return api_response(
                data={
                    'trade_id': result.get('trade_id'),
                    'order_id': result.get('order_id')
                },
                message="Manual trade executed"
            )
        else:
            return api_response(
                success=False,
                message=result.get('error', 'Failed to execute trade'),
                status_code=400
            )
    
    except json.JSONDecodeError:
        return api_response(success=False, message="Invalid JSON", status_code=400)
    except Exception as e:
        logger.error(f"Error placing manual trade: {e}")
        return api_response(success=False, message=str(e), status_code=500)


@csrf_exempt
@require_http_methods(["POST"])
def emergency_stop(request):
    """Emergency stop - disable all strategies"""
    try:
        # Disable all strategies
        Strategy.objects.all().update(enabled=False)
        
        # Refresh registry
        registry = StrategyRegistry()
        registry.refresh()
        
        # Send alert
        alert_manager = AlertManager()
        alert_manager.send_alert(
            'EMERGENCY_STOP',
            'Emergency stop activated - all strategies disabled',
            severity='CRITICAL'
        )
        
        return api_response(
            data={'strategies_disabled': Strategy.objects.count()},
            message="Emergency stop activated - all strategies disabled"
        )
    
    except Exception as e:
        logger.error(f"Error in emergency stop: {e}")
        return api_response(success=False, message=str(e), status_code=500)


# System Status Endpoint

@require_http_methods(["GET"])
def system_status(request):
    """Get system status"""
    try:
        monitor = TradeMonitor()
        health = monitor.get_system_health()
        
        # Get strategy counts
        total_strategies = Strategy.objects.count()
        enabled_strategies = Strategy.objects.filter(enabled=True).count()
        
        # Get position counts
        tracker = PositionTracker()
        positions = tracker.get_all_positions()
        
        data = {
            'system_health': health,
            'strategies': {
                'total': total_strategies,
                'enabled': enabled_strategies,
                'disabled': total_strategies - enabled_strategies
            },
            'positions': {
                'open': len(positions),
                'total_value': sum(float(p.price) * p.quantity for p in positions) if positions else 0
            },
            'timestamp': timezone.now().isoformat()
        }
        
        return api_response(data=data)
    
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return api_response(success=False, message=str(e), status_code=500)
