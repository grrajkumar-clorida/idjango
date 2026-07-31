"""
Real-time Trade Monitor
Monitors trades, positions, and order status in real-time
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from django.utils import timezone

from stocks.models import LiveTrade, Orders, StrategySignal
from stocks.positions.position_tracker import PositionTracker
from infra.utils.breeze_client import BreezeAPI

logger = logging.getLogger(__name__)


class TradeMonitor:
    """Real-time trade monitoring"""
    
    def __init__(self):
        self.breeze = BreezeAPI()
        self.position_tracker = PositionTracker()
    
    def get_active_trades(self) -> List[Dict]:
        """
        Get all active trades
        
        Returns:
            List of active trade dictionaries
        """
        active_statuses = ['Pending', 'Open', 'Partially Filled']
        trades = LiveTrade.objects.filter(status__in=active_statuses)
        
        result = []
        for trade in trades:
            result.append({
                'id': trade.id,
                'stock_code': trade.stock_code,
                'exchange': trade.exchange,
                'action': trade.action,
                'quantity': trade.quantity,
                'price': float(trade.price) if trade.price else None,
                'status': trade.status,
                'order_id': trade.order_id,
                'stop_loss': float(trade.stop_loss) if trade.stop_loss else None,
                'take_profit': float(trade.take_profit) if trade.take_profit else None,
                'profit_loss': float(trade.profit_loss),
                'timestamp': trade.timestamp,
            })
        
        return result
    
    def get_recent_trades(self, hours: int = 24) -> List[Dict]:
        """
        Get recent trades within specified hours
        
        Args:
            hours: Number of hours to look back
        
        Returns:
            List of recent trade dictionaries
        """
        since = timezone.now() - timedelta(hours=hours)
        trades = LiveTrade.objects.filter(timestamp__gte=since).order_by('-timestamp')
        
        result = []
        for trade in trades:
            result.append({
                'id': trade.id,
                'stock_code': trade.stock_code,
                'exchange': trade.exchange,
                'action': trade.action,
                'quantity': trade.quantity,
                'price': float(trade.price) if trade.price else None,
                'status': trade.status,
                'order_id': trade.order_id,
                'profit_loss': float(trade.profit_loss),
                'timestamp': trade.timestamp,
            })
        
        return result
    
    def get_pending_signals(self) -> List[Dict]:
        """
        Get all pending signals that haven't been executed
        
        Returns:
            List of pending signal dictionaries
        """
        signals = StrategySignal.objects.filter(executed=False).order_by('-timestamp')
        
        result = []
        for signal in signals:
            result.append({
                'id': signal.id,
                'strategy': signal.strategy.name,
                'stock_code': signal.stock_code,
                'signal_type': signal.signal_type,
                'strength': signal.strength,
                'price': signal.price,
                'stop_loss': signal.stop_loss,
                'take_profit': signal.take_profit,
                'timestamp': signal.timestamp,
            })
        
        return result
    
    def get_trade_statistics(self, hours: int = 24) -> Dict:
        """
        Get trade statistics for the specified period
        
        Args:
            hours: Number of hours to analyze
        
        Returns:
            Dictionary with trade statistics
        """
        since = timezone.now() - timedelta(hours=hours)
        trades = LiveTrade.objects.filter(timestamp__gte=since)
        
        total_trades = trades.count()
        executed_trades = trades.filter(status='Executed').count()
        pending_trades = trades.filter(status__in=['Pending', 'Open']).count()
        failed_trades = trades.filter(status='Failed').count()
        
        total_pl = sum(float(trade.profit_loss) for trade in trades if trade.profit_loss)
        winning_trades = trades.filter(profit_loss__gt=0).count()
        losing_trades = trades.filter(profit_loss__lt=0).count()
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        return {
            'total_trades': total_trades,
            'executed_trades': executed_trades,
            'pending_trades': pending_trades,
            'failed_trades': failed_trades,
            'total_pl': total_pl,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': round(win_rate, 2),
            'period_hours': hours,
        }
    
    def monitor_order_status(self, order_id: str) -> Optional[Dict]:
        """
        Monitor specific order status
        
        Args:
            order_id: Order ID to monitor
        
        Returns:
            Order status dictionary or None
        """
        try:
            if not self.breeze.api_status:
                logger.warning("Breeze API not available")
                return None
            
            # Get order details from Breeze API
            order_details = self.breeze.api.get_order_detail(order_id)
            
            if order_details and order_details.get('Success'):
                return {
                    'order_id': order_id,
                    'status': order_details.get('Status'),
                    'quantity': order_details.get('Quantity'),
                    'filled_quantity': order_details.get('FilledQuantity', 0),
                    'price': order_details.get('Price'),
                    'message': order_details.get('Message', ''),
                }
        except Exception as e:
            logger.error(f"Error monitoring order {order_id}: {e}")
        
        return None
    
    def update_trade_statuses(self) -> Dict:
        """
        Update status of all pending trades by checking with broker
        
        Returns:
            Dictionary with update results
        """
        pending_trades = LiveTrade.objects.filter(
            status__in=['Pending', 'Open'],
            order_id__isnull=False
        )
        
        updated = 0
        errors = 0
        
        for trade in pending_trades:
            try:
                order_status = self.monitor_order_status(trade.order_id)
                
                if order_status:
                    # Update trade status based on order status
                    if order_status['status'] == 'Executed':
                        trade.status = 'Executed'
                        updated += 1
                    elif order_status['status'] == 'Cancelled':
                        trade.status = 'Cancelled'
                        updated += 1
                    elif order_status['status'] == 'Rejected':
                        trade.status = 'Failed'
                        updated += 1
                    
                    trade.save()
            except Exception as e:
                logger.error(f"Error updating trade {trade.id}: {e}")
                errors += 1
        
        return {
            'updated': updated,
            'errors': errors,
            'total_checked': pending_trades.count(),
        }
    
    def get_system_health(self) -> Dict:
        """
        Get system health status
        
        Returns:
            Dictionary with system health metrics
        """
        health = {
            'breeze_api_status': self.breeze.api_status if hasattr(self.breeze, 'api_status') else False,
            'active_trades': LiveTrade.objects.filter(status__in=['Pending', 'Open']).count(),
            'pending_signals': StrategySignal.objects.filter(executed=False).count(),
            'recent_errors': 0,  # Can be enhanced with error tracking
            'last_update': timezone.now(),
        }
        
        return health
