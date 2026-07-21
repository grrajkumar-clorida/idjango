"""
Position Monitor for 50MA Strategy
Monitors open positions and updates statuses, executes exits
"""
import logging
from decimal import Decimal
from typing import Dict, List
from django.conf import settings
from data.models import Stocks50MA, StockPriceData
from data.strategies.ma50_strategy import MA50Strategy
from infra.utils.breeze_client import BreezeAPI
from stocks.models import LiveTrade, Orders

logger = logging.getLogger(__name__)


class PositionMonitor:
    """Monitors and manages open positions"""
    
    def __init__(self):
        self.breeze = BreezeAPI()
        self.strategy = MA50Strategy()
        self.paper_trading = getattr(settings, 'PAPER_TRADING_MODE', True)
    
    def monitor_all_positions(self) -> Dict:
        """
        Monitor all open positions and update statuses
        
        Returns:
            Dict with monitoring results
        """
        # Get all open trades
        open_trades = LiveTrade.objects.filter(status="Executed")
        
        # Get live data map
        live_data_map = {
            spd.script: spd for spd in StockPriceData.objects.all()
        }
        
        results = {
            'total': open_trades.count(),
            'updated': 0,
            'exited': 0,
            'details': []
        }
        
        for trade in open_trades:
            live_data = live_data_map.get(trade.stock_code)
            
            if not live_data:
                continue
            
            current_price = live_data.close_price
            entry_price = float(trade.price)
            
            # Get corresponding Stocks50MA record
            stock = Stocks50MA.objects.filter(script=trade.stock_code).first()
            
            if not stock:
                continue
            
            # Check exit conditions
            is_bottom_entry = self.strategy.is_bottom_entry(stock, live_data) if stock else False
            
            exit_check = self.strategy.check_exit_condition(
                entry_price,
                current_price,
                is_bottom_entry
            )
            
            # Update status based on price
            new_status = self.strategy.update_status_based_on_price(
                stock,
                live_data,
                entry_price
            )
            
            # Update stock status if changed
            if new_status != stock.status:
                stock.status = new_status
                stock.save()
                results['updated'] += 1
                results['details'].append({
                    'script': trade.stock_code,
                    'old_status': trade.status,
                    'new_status': new_status,
                    'current_price': current_price,
                    'profit_percent': exit_check['profit_percent']
                })
            
            # Execute exit if conditions met
            if exit_check['should_exit']:
                exit_result = self.execute_exit(trade, exit_check, current_price)
                
                if exit_result['success']:
                    results['exited'] += 1
                    results['details'].append({
                        'script': trade.stock_code,
                        'action': 'exited',
                        'exit_type': exit_check['exit_type'],
                        'exit_percent': exit_check['exit_percent']
                    })
            
            # Update P/L
            self.update_profit_loss(trade, current_price, entry_price)
        
        return results
    
    def execute_exit(self, trade: LiveTrade, exit_check: Dict, current_price: float) -> Dict:
        """
        Execute exit order
        
        Args:
            trade: LiveTrade object
            exit_check: Exit condition check result
            current_price: Current market price
        
        Returns:
            Dict with exit result
        """
        exit_type = exit_check['exit_type']
        exit_percent = exit_check['exit_percent']
        
        # Calculate quantity to exit
        if exit_type == 'full':
            exit_quantity = trade.quantity
        else:  # partial
            exit_quantity = int(trade.quantity * (exit_percent / 100))
        
        if exit_quantity == 0:
            return {'success': False, 'message': 'Exit quantity is 0'}
        
        if self.paper_trading:
            # Paper trading mode
            logger.info(f"PAPER TRADING: Would place SELL order for {trade.stock_code}")
            logger.info(f"  Quantity: {exit_quantity}/{trade.quantity}, Type: {exit_type}")
            
            # Update trade
            if exit_type == 'full':
                trade.status = "Closed"
            else:
                trade.quantity -= exit_quantity
            
            trade.save()
            
            return {
                'success': True,
                'message': f'Paper trade exit executed ({exit_type})',
                'exit_quantity': exit_quantity
            }
        else:
            # Live trading mode
            try:
                response = self.breeze.place_order(
                    stock_code=trade.stock_code,
                    exchange=trade.exchange,
                    quantity=exit_quantity,
                    order_type="MARKET",
                    price=0,
                    product="cash",
                    action="SELL"
                )
                
                if response.get("Status") == "Success" or response.get("Status") == 200:
                    order_id = response.get("order_id") or response.get("Success", {}).get("order_id", "")
                    
                    # Update trade
                    if exit_type == 'full':
                        trade.status = "Closed"
                    else:
                        trade.quantity -= exit_quantity
                    
                    trade.save()
                    
                    # Update Orders record
                    order_record = Orders.objects.filter(
                        ticker=trade.stock_code,
                        status=1
                    ).first()
                    
                    if order_record:
                        if exit_type == 'full':
                            order_record.status = 0  # Closed
                        else:
                            order_record.qty = str(trade.quantity)
                        
                        order_record.save()
                    
                    logger.info(f"Exit order placed for {trade.stock_code}: {order_id}")
                    
                    return {
                        'success': True,
                        'message': f'Exit executed ({exit_type})',
                        'order_id': order_id,
                        'exit_quantity': exit_quantity
                    }
                else:
                    error_msg = response.get("ErrorMessage", "Unknown error")
                    logger.error(f"Exit order failed for {trade.stock_code}: {error_msg}")
                    return {
                        'success': False,
                        'message': error_msg
                    }
                    
            except Exception as e:
                logger.error(f"Exception executing exit for {trade.stock_code}: {str(e)}")
                return {
                    'success': False,
                    'message': f"Exception: {str(e)}"
                }
    
    def update_profit_loss(self, trade: LiveTrade, current_price: float, entry_price: float):
        """Update profit/loss for a trade"""
        if trade.action == "BUY":
            pnl = (current_price - entry_price) * trade.quantity
        else:
            pnl = (entry_price - current_price) * trade.quantity
        
        trade.profit_loss = Decimal(str(pnl))
        trade.save()
        
        # Update Orders record
        order_record = Orders.objects.filter(
            ticker=trade.stock_code,
            status=1
        ).first()
        
        if order_record:
            order_record.current_value = current_price * trade.quantity
            order_record.overall_pl = float(pnl)
            order_record.day_pl = float(pnl)  # Simplified - should calculate daily P/L
            order_record.save()
