"""
Alert Manager
Manages alerts and notifications for trading events
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from stocks.models import LiveTrade, StrategySignal, RiskLimits
from stocks.risk.risk_manager import RiskManager
from infra.utils.telegram import send_telegram

logger = logging.getLogger(__name__)


class AlertManager:
    """Manages alerts and notifications"""
    
    def __init__(self):
        self.risk_manager = RiskManager()
        self.alert_history = []  # In-memory alert history (can be moved to DB)
    
    def send_alert(self, alert_type: str, message: str, severity: str = 'INFO', 
                   data: Optional[Dict] = None) -> bool:
        """
        Send an alert
        
        Args:
            alert_type: Type of alert (TRADE_EXECUTED, STOP_LOSS_HIT, etc.)
            message: Alert message
            severity: Alert severity (INFO, WARNING, ERROR, CRITICAL)
            data: Additional data dictionary
        
        Returns:
            True if alert sent successfully
        """
        alert = {
            'type': alert_type,
            'message': message,
            'severity': severity,
            'data': data or {},
            'timestamp': timezone.now(),
        }
        
        self.alert_history.append(alert)
        
        # Log the alert
        log_level = {
            'INFO': logger.info,
            'WARNING': logger.warning,
            'ERROR': logger.error,
            'CRITICAL': logger.critical,
        }.get(severity, logger.info)
        
        log_level(f"Alert [{severity}]: {alert_type} - {message}")
        
        # Send email for critical alerts
        if severity in ['ERROR', 'CRITICAL']:
            self._send_email_alert(alert_type, message, severity, data)
        
        # Send Telegram alert for all alerts
        self._send_telegram_alert(alert_type, message, severity, data)
        
        return True
    
    def _send_email_alert(self, alert_type: str, message: str, severity: str, 
                          data: Optional[Dict] = None):
        """Send email alert (if email configured)"""
        try:
            if not getattr(settings, 'ALERT_EMAIL_ENABLED', True):
                return
            
            if hasattr(settings, 'ADMINS') and settings.ADMINS:
                subject = f"[{severity}] Trading Alert: {alert_type}"
                body = f"""
                Alert Type: {alert_type}
                Severity: {severity}
                Message: {message}
                
                Additional Data:
                {data or 'None'}
                
                Timestamp: {timezone.now()}
                """
                
                recipient_list = [admin[1] for admin in settings.ADMINS]
                send_mail(
                    subject,
                    body,
                    settings.DEFAULT_FROM_EMAIL,
                    recipient_list,
                    fail_silently=True,
                )
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
    
    def _send_telegram_alert(self, alert_type: str, message: str, severity: str,
                             data: Optional[Dict] = None):
        """Send Telegram alert"""
        try:
            if not getattr(settings, 'TELEGRAM_BOT_TOKEN', None):
                logger.debug("Telegram bot token not configured")
                return
            
            # Format message with emoji based on severity
            emoji_map = {
                'INFO': 'ℹ️',
                'WARNING': '⚠️',
                'ERROR': '❌',
                'CRITICAL': '🚨',
            }
            emoji = emoji_map.get(severity, '📢')
            
            # Telegram uses Markdown formatting
            telegram_message = f"{emoji} *{alert_type}*\n\n"
            telegram_message += f"*Severity:* {severity}\n"
            telegram_message += f"*Message:* {message}\n"
            
            if data:
                telegram_message += "\n*Details:*\n"
                for key, value in data.items():
                    # Format value for Telegram (escape special chars if needed)
                    formatted_value = str(value)
                    telegram_message += f"• {key}: `{formatted_value}`\n"
            
            telegram_message += f"\n*Time:* {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            send_telegram(telegram_message)
            
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
    
    def alert_trade_executed(self, trade: LiveTrade) -> bool:
        """Alert when a trade is executed"""
        message = f"Trade executed: {trade.action} {trade.quantity} {trade.stock_code} @ {trade.price}"
        return self.send_alert(
            'TRADE_EXECUTED',
            message,
            'INFO',
            {
                'trade_id': trade.id,
                'stock_code': trade.stock_code,
                'action': trade.action,
                'quantity': trade.quantity,
                'price': float(trade.price) if trade.price else None,
            }
        )
    
    def alert_stop_loss_hit(self, trade: LiveTrade, current_price: float) -> bool:
        """Alert when stop-loss is hit"""
        message = f"Stop-loss hit for {trade.stock_code}: Current price {current_price}, Stop-loss {trade.stop_loss}"
        return self.send_alert(
            'STOP_LOSS_HIT',
            message,
            'WARNING',
            {
                'trade_id': trade.id,
                'stock_code': trade.stock_code,
                'current_price': current_price,
                'stop_loss': float(trade.stop_loss) if trade.stop_loss else None,
            }
        )
    
    def alert_take_profit_hit(self, trade: LiveTrade, current_price: float) -> bool:
        """Alert when take-profit is hit"""
        message = f"Take-profit hit for {trade.stock_code}: Current price {current_price}, Take-profit {trade.take_profit}"
        return self.send_alert(
            'TAKE_PROFIT_HIT',
            message,
            'INFO',
            {
                'trade_id': trade.id,
                'stock_code': trade.stock_code,
                'current_price': current_price,
                'take_profit': float(trade.take_profit) if trade.take_profit else None,
            }
        )
    
    def alert_risk_limit_breach(self, limit_type: str, current_value: float, 
                                limit_value: float) -> bool:
        """Alert when risk limit is breached"""
        message = f"Risk limit breached: {limit_type} - Current: {current_value}, Limit: {limit_value}"
        return self.send_alert(
            'RISK_LIMIT_BREACH',
            message,
            'CRITICAL',
            {
                'limit_type': limit_type,
                'current_value': current_value,
                'limit_value': limit_value,
            }
        )
    
    def alert_order_failed(self, trade: LiveTrade, error: str) -> bool:
        """Alert when order fails"""
        message = f"Order failed for {trade.stock_code}: {error}"
        return self.send_alert(
            'ORDER_FAILED',
            message,
            'ERROR',
            {
                'trade_id': trade.id,
                'stock_code': trade.stock_code,
                'error': error,
            }
        )
    
    def alert_strategy_error(self, strategy_name: str, error: str) -> bool:
        """Alert when strategy encounters an error"""
        message = f"Strategy error in {strategy_name}: {error}"
        return self.send_alert(
            'STRATEGY_ERROR',
            message,
            'ERROR',
            {
                'strategy_name': strategy_name,
                'error': error,
            }
        )
    
    def alert_api_connection_failed(self) -> bool:
        """Alert when API connection fails"""
        message = "Breeze API connection failed"
        return self.send_alert(
            'API_CONNECTION_FAILED',
            message,
            'CRITICAL',
        )
    
    def check_risk_limits(self) -> List[Dict]:
        """
        Check all risk limits and generate alerts if breached
        
        Returns:
            List of breach alerts
        """
        alerts = []
        
        try:
            risk_limits = RiskLimits.objects.first()
            if not risk_limits:
                return alerts
            
            # Check daily loss limit
            daily_pl = self.risk_manager.get_daily_pl()
            if abs(daily_pl) > float(risk_limits.max_daily_loss):
                alert = self.alert_risk_limit_breach(
                    'Daily Loss Limit',
                    abs(daily_pl),
                    float(risk_limits.max_daily_loss)
                )
                alerts.append({
                    'type': 'DAILY_LOSS_LIMIT',
                    'current': abs(daily_pl),
                    'limit': float(risk_limits.max_daily_loss),
                })
            
            # Check portfolio exposure
            exposure = self.risk_manager.get_portfolio_exposure()
            if exposure > float(risk_limits.max_portfolio_exposure):
                alert = self.alert_risk_limit_breach(
                    'Portfolio Exposure',
                    exposure,
                    float(risk_limits.max_portfolio_exposure)
                )
                alerts.append({
                    'type': 'PORTFOLIO_EXPOSURE',
                    'current': exposure,
                    'limit': float(risk_limits.max_portfolio_exposure),
                })
            
            # Check drawdown
            drawdown = self.risk_manager.get_current_drawdown()
            if drawdown > float(risk_limits.max_drawdown):
                alert = self.alert_risk_limit_breach(
                    'Max Drawdown',
                    drawdown,
                    float(risk_limits.max_drawdown)
                )
                alerts.append({
                    'type': 'MAX_DRAWDOWN',
                    'current': drawdown,
                    'limit': float(risk_limits.max_drawdown),
                })
        
        except Exception as e:
            logger.error(f"Error checking risk limits: {e}")
        
        return alerts
    
    def get_recent_alerts(self, hours: int = 24, severity: Optional[str] = None) -> List[Dict]:
        """
        Get recent alerts
        
        Args:
            hours: Number of hours to look back
            severity: Filter by severity (optional)
        
        Returns:
            List of alert dictionaries
        """
        since = timezone.now() - timedelta(hours=hours)
        
        alerts = [
            alert for alert in self.alert_history
            if alert['timestamp'] >= since
        ]
        
        if severity:
            alerts = [alert for alert in alerts if alert['severity'] == severity]
        
        return alerts
