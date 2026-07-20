"""
Order Manager
Manages order lifecycle (placement, modification, cancellation)
"""
import logging
import time
from typing import Dict, Optional
from decimal import Decimal

from stocks.models import LiveTrade, Orders
from stocks.risk.risk_manager import RiskManager
from stocks.risk.position_sizer import PositionSizer
from infra.utils.breeze_client import BreezeAPI

logger = logging.getLogger(__name__)


class OrderManager:
    """Manages order execution"""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        """
        Initialize OrderManager
        
        Args:
            max_retries: Maximum number of retry attempts for failed orders
            retry_delay: Initial delay between retries in seconds (exponential backoff)
        """
        self.breeze = BreezeAPI()
        self.risk_manager = RiskManager()
        self.position_sizer = PositionSizer()
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    def execute_signal(self, signal: Dict, stock_code: str, 
                      exchange: str = "NSE") -> Dict:
        """
        Execute a trading signal
        
        Args:
            signal: Signal dictionary from strategy
            stock_code: Stock code
            exchange: Exchange code
        
        Returns:
            Dict with execution result
        """
        action = signal.get('action')
        price = signal.get('price', 0)
        
        if action not in ['BUY', 'SELL']:
            return {
                'success': False,
                'error': f'Invalid action: {action}'
            }
        
        # Calculate position size
        quantity = self._calculate_quantity(signal, stock_code, price)
        
        if quantity <= 0:
            return {
                'success': False,
                'error': 'Invalid quantity calculated'
            }
        
        # Validate risk
        is_valid, reason = self.risk_manager.validate_trade(
            stock_code, quantity, price, action
        )
        
        if not is_valid:
            return {
                'success': False,
                'error': reason
            }
        
        # Place order
        return self.place_order(
            stock_code=stock_code,
            exchange=exchange,
            quantity=quantity,
            order_type=signal.get('order_type', 'MARKET'),
            price=price,
            action=action,
            stop_loss=signal.get('stop_loss'),
            take_profit=signal.get('take_profit'),
            strategy_name=signal.get('strategy_name')
        )
    
    def place_order(self, stock_code: str, exchange: str, quantity: int,
                   order_type: str = "MARKET", price: float = 0,
                   action: str = "BUY", stop_loss: Optional[float] = None,
                   take_profit: Optional[float] = None,
                   strategy_name: Optional[str] = None,
                   retry_on_failure: bool = True) -> Dict:
        """
        Place an order with retry logic
        
        Args:
            stock_code: Stock code
            exchange: Exchange code
            quantity: Quantity
            order_type: MARKET or LIMIT
            price: Price (for LIMIT orders)
            action: BUY or SELL
            stop_loss: Stop-loss price
            take_profit: Take-profit price
            strategy_name: Strategy name
            retry_on_failure: Whether to retry on failure
        
        Returns:
            Dict with order result
        """
        last_error = None
        
        for attempt in range(self.max_retries if retry_on_failure else 1):
            try:
                # Check API status before placing order
                if not self.breeze.api_status:
                    error_msg = "Breeze API not available"
                    logger.error(error_msg)
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (2 ** attempt))
                        continue
                    return {
                        'success': False,
                        'error': error_msg,
                        'retries': attempt + 1
                    }
                
                response = self.breeze.place_order(
                    stock_code=stock_code,
                    exchange=exchange,
                    quantity=quantity,
                    order_type=order_type,
                    price=price,
                    product="cash",
                    action=action
                )
                
                if response.get("Status") == "Success" or response.get("Status") == 200:
                    order_id = response.get("order_id") or response.get("Success", {}).get("order_id", "")
                    
                    # Verify order was actually placed
                    if not order_id:
                        error_msg = "Order placed but no order ID returned"
                        logger.warning(f"{error_msg} for {stock_code}")
                        if attempt < self.max_retries - 1:
                            time.sleep(self.retry_delay * (2 ** attempt))
                            continue
                        return {
                            'success': False,
                            'error': error_msg,
                            'retries': attempt + 1
                        }
                    
                    # Create LiveTrade record
                    trade = LiveTrade.objects.create(
                        stock_code=stock_code,
                        exchange=exchange,
                        quantity=quantity,
                        order_type=order_type,
                        price=Decimal(str(price)) if price > 0 else Decimal('0'),
                        action=action,
                        status="Pending",  # Start as Pending, will be updated when confirmed
                        order_id=order_id,
                        stop_loss=Decimal(str(stop_loss)) if stop_loss else None,
                        take_profit=Decimal(str(take_profit)) if take_profit else None
                    )
                    
                    # Create Orders record
                    order_value = price * quantity if price > 0 else 0
                    Orders.objects.create(
                        ticker=stock_code,
                        script=stock_code,
                        order_id=order_id,
                        position=action,
                        stop_loss=stop_loss or 0.0,
                        qty=str(quantity),
                        price=price,
                        invested_value=order_value,
                        current_value=order_value,
                        day_pl=0.0,
                        overall_pl=0.0,
                        status=1,  # Active
                        message=f"Order placed via {strategy_name or 'Manual'}"
                    )
                    
                    logger.info(f"Order placed: {stock_code} - {action} - {quantity} @ {price} (Order ID: {order_id})")
                    
                    # Confirm order status
                    confirmation = self._confirm_order(order_id)
                    if confirmation.get('confirmed'):
                        trade.status = "Executed"
                        trade.save()
                    
                    return {
                        'success': True,
                        'order_id': order_id,
                        'trade_id': trade.id,
                        'message': 'Order executed successfully',
                        'retries': attempt + 1,
                        'confirmed': confirmation.get('confirmed', False)
                    }
                else:
                    error_msg = response.get("ErrorMessage", "Unknown error")
                    last_error = error_msg
                    
                    # Check if error is retryable
                    if not self._is_retryable_error(error_msg):
                        logger.error(f"Non-retryable error for {stock_code}: {error_msg}")
                        return {
                            'success': False,
                            'error': error_msg,
                            'retries': attempt + 1,
                            'retryable': False
                        }
                    
                    logger.warning(f"Order attempt {attempt + 1} failed for {stock_code}: {error_msg}")
                    
                    if attempt < self.max_retries - 1:
                        delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                        logger.info(f"Retrying in {delay} seconds...")
                        time.sleep(delay)
                    else:
                        logger.error(f"Order failed after {self.max_retries} attempts for {stock_code}: {error_msg}")
                        
            except Exception as e:
                last_error = str(e)
                logger.error(f"Exception placing order for {stock_code} (attempt {attempt + 1}): {str(e)}")
                
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    time.sleep(delay)
                else:
                    logger.error(f"Order failed after {self.max_retries} attempts due to exception: {str(e)}")
        
        return {
            'success': False,
            'error': last_error or "Unknown error",
            'retries': self.max_retries,
            'retryable': True
        }
    
    def _confirm_order(self, order_id: str) -> Dict:
        """
        Confirm order status with broker
        
        Args:
            order_id: Order ID to confirm
        
        Returns:
            Dict with confirmation status
        """
        try:
            if not self.breeze.api_status:
                return {'confirmed': False, 'error': 'API not available'}
            
            order_details = self.breeze.api.get_order_detail(order_id)
            
            if order_details and order_details.get('Success'):
                status = order_details.get('Status', '')
                if status in ['Executed', 'Filled']:
                    return {'confirmed': True, 'status': status}
                else:
                    return {'confirmed': False, 'status': status}
            
            return {'confirmed': False, 'error': 'Could not confirm order'}
        
        except Exception as e:
            logger.error(f"Error confirming order {order_id}: {e}")
            return {'confirmed': False, 'error': str(e)}
    
    def _is_retryable_error(self, error_msg: str) -> bool:
        """
        Check if error is retryable
        
        Args:
            error_msg: Error message
        
        Returns:
            True if error is retryable
        """
        retryable_errors = [
            'timeout',
            'connection',
            'network',
            'temporary',
            'server error',
            'service unavailable',
            'rate limit',
        ]
        
        error_lower = error_msg.lower()
        return any(retryable in error_lower for retryable in retryable_errors)
    
    def modify_order(self, order_id: str, new_price: float) -> Dict:
        """
        Modify an existing order
        
        Args:
            order_id: Order ID
            new_price: New price
        
        Returns:
            Dict with modification result
        """
        try:
            response = self.breeze.modify_order(order_id, new_price)
            
            if response.get("Status") == "Success":
                # Update LiveTrade
                LiveTrade.objects.filter(order_id=order_id).update(price=Decimal(str(new_price)))
                
                logger.info(f"Order modified: {order_id} - New price: {new_price}")
                
                return {
                    'success': True,
                    'message': 'Order modified successfully'
                }
            else:
                return {
                    'success': False,
                    'error': response.get("ErrorMessage", "Unknown error")
                }
                
        except Exception as e:
            logger.error(f"Exception modifying order {order_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def cancel_order(self, order_id: str) -> Dict:
        """
        Cancel an existing order
        
        Args:
            order_id: Order ID
        
        Returns:
            Dict with cancellation result
        """
        try:
            response = self.breeze.cancel_order(order_id)
            
            if response.get("Status") == "Success":
                # Update LiveTrade
                LiveTrade.objects.filter(order_id=order_id).update(status="Canceled")
                
                # Update Orders
                Orders.objects.filter(order_id=order_id).update(status=0)
                
                logger.info(f"Order canceled: {order_id}")
                
                return {
                    'success': True,
                    'message': 'Order canceled successfully'
                }
            else:
                return {
                    'success': False,
                    'error': response.get("ErrorMessage", "Unknown error")
                }
                
        except Exception as e:
            logger.error(f"Exception canceling order {order_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _calculate_quantity(self, signal: Dict, stock_code: str, price: float) -> int:
        """Calculate quantity based on signal and risk"""
        # Check if signal has quantity
        if 'quantity' in signal:
            return int(signal['quantity'])
        
        # Use position sizer
        sizing_method = signal.get('position_sizing_method', 'risk_percent')
        risk_percent = signal.get('risk_percent', 1.0)
        
        if sizing_method == 'fixed':
            fixed_amount = signal.get('fixed_amount', 10000)
            return self.position_sizer.fixed_size(price, fixed_amount)
        elif sizing_method == 'volatility':
            atr = signal.get('atr', 0)
            capital = signal.get('capital', 100000)
            return self.position_sizer.volatility_based(price, capital, atr, risk_percent)
        else:
            # Default: risk percent
            capital = signal.get('capital', 100000)
            return self.risk_manager.calculate_position_size(stock_code, price, risk_percent, capital)
