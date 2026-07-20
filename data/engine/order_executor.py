"""
Automated Order Executor for 50MA Strategy
Monitors stocks with status 8 and places orders automatically
"""
import logging
from decimal import Decimal
from typing import Dict, Optional
from django.conf import settings
from data.models import Stocks50MA, StockPriceData
from data.strategies.ma50_strategy import MA50Strategy
from infra.utils.breeze_client import BreezeAPI
from stocks.models import LiveTrade, Orders

logger = logging.getLogger(__name__)


class OrderExecutor:
    """Executes orders for 50MA strategy"""
    
    def __init__(self):
        self.breeze = BreezeAPI()
        self.strategy = MA50Strategy()
        self.paper_trading = getattr(settings, 'PAPER_TRADING_MODE', True)
        self.max_position_size = getattr(settings, 'MAX_POSITION_SIZE', 100000)
    
    def execute_orders_for_status_8(self) -> Dict:
        """
        Execute orders for all stocks with status 8 (Order ready)
        
        Returns:
            Dict with execution results
        """
        # Get all stocks with status 8 that haven't been traded yet
        stocks_to_trade = Stocks50MA.objects.filter(status=8)
        
        # Get live data map
        live_data_map = {
            spd.script: spd for spd in StockPriceData.objects.all()
        }
        
        results = {
            'total': stocks_to_trade.count(),
            'executed': 0,
            'skipped': 0,
            'failed': 0,
            'details': []
        }
        
        for stock in stocks_to_trade:
            live_data = live_data_map.get(stock.script)
            
            if not live_data:
                results['skipped'] += 1
                results['details'].append({
                    'script': stock.script,
                    'status': 'skipped',
                    'reason': 'No live data available'
                })
                continue
            
            # Check entry conditions
            entry_check = self.strategy.check_entry_condition(stock, live_data)
            
            if not entry_check['can_enter']:
                results['skipped'] += 1
                results['details'].append({
                    'script': stock.script,
                    'status': 'skipped',
                    'reason': entry_check['reason']
                })
                continue
            
            # Check if already have open position
            existing_trade = LiveTrade.objects.filter(
                stock_code=stock.script,
                status="Executed"
            ).first()
            
            if existing_trade:
                results['skipped'] += 1
                results['details'].append({
                    'script': stock.script,
                    'status': 'skipped',
                    'reason': 'Already have open position'
                })
                continue
            
            # Execute order
            result = self.place_order(stock, live_data, entry_check)
            
            if result['success']:
                results['executed'] += 1
            else:
                results['failed'] += 1
            
            results['details'].append({
                'script': stock.script,
                'status': 'executed' if result['success'] else 'failed',
                'reason': result.get('message', ''),
                'order_id': result.get('order_id')
            })
        
        return results
    
    def place_order(self, stock: Stocks50MA, live_data: StockPriceData, 
                   entry_check: Dict) -> Dict:
        """
        Place order for a stock
        
        Args:
            stock: Stocks50MA object
            live_data: StockPriceData object
            entry_check: Entry condition check result
        
        Returns:
            Dict with execution result
        """
        entry_price = entry_check['entry_price']
        
        # Calculate position size
        quantity = self.strategy.calculate_position_size(entry_price)
        
        # Check if order value exceeds max position size
        order_value = entry_price * quantity
        if order_value > self.max_position_size:
            quantity = int(self.max_position_size / entry_price)
            logger.warning(f"Reduced quantity for {stock.script} due to max position size")
        
        # Check if bought at bottom
        is_bottom_entry = self.strategy.is_bottom_entry(stock, live_data)
        
        # Get target prices
        targets = self.strategy.get_target_prices(entry_price)
        
        if self.paper_trading:
            # Paper trading mode - simulate order
            logger.info(f"PAPER TRADING: Would place BUY order for {stock.script}")
            logger.info(f"  Quantity: {quantity}, Price: {entry_price}")
            logger.info(f"  Targets: T1={targets['target_1']:.2f}, T2={targets['target_2']:.2f}, T3={targets['target_3']:.2f}")
            
            # Create simulated trade record
            trade = LiveTrade.objects.create(
                stock_code=stock.script,
                exchange="NSE",
                quantity=quantity,
                order_type="MARKET",
                price=Decimal(str(entry_price)),
                action="BUY",
                status="Executed",
                order_id=f"PAPER_{stock.script}_{stock.id}",
                stop_loss=Decimal(str(entry_price * 0.95)),  # 5% stop loss
                take_profit=Decimal(str(targets['target_2']))
            )
            
            # Update stock status to indicate order placed
            stock.status = 8  # Keep status 8 until targets are hit
            stock.save()
            
            return {
                'success': True,
                'message': 'Paper trade executed',
                'order_id': trade.order_id,
                'quantity': quantity,
                'price': entry_price
            }
        else:
            # Live trading mode
            try:
                response = self.breeze.place_order(
                    stock_code=stock.script,
                    exchange="NSE",
                    quantity=quantity,
                    order_type="MARKET",
                    price=0,
                    product="cash",
                    action="BUY"
                )
                
                if response.get("Status") == "Success" or response.get("Status") == 200:
                    order_id = response.get("order_id") or response.get("Success", {}).get("order_id", "")
                    
                    # Create trade record
                    trade = LiveTrade.objects.create(
                        stock_code=stock.script,
                        exchange="NSE",
                        quantity=quantity,
                        order_type="MARKET",
                        price=Decimal(str(entry_price)),
                        action="BUY",
                        status="Executed",
                        order_id=order_id,
                        stop_loss=Decimal(str(entry_price * 0.95)),  # 5% stop loss
                        take_profit=Decimal(str(targets['target_2']))
                    )
                    
                    # Also create Orders record
                    Orders.objects.create(
                        ticker=stock.script,
                        script=stock.script,
                        order_id=order_id,
                        position="BUY",
                        stop_loss=float(entry_price * 0.95),
                        qty=str(quantity),
                        price=entry_price,
                        invested_value=order_value,
                        current_value=order_value,
                        day_pl=0.0,
                        overall_pl=0.0,
                        targets={
                            'target_1': targets['target_1'],
                            'target_2': targets['target_2'],
                            'target_3': targets['target_3'],
                            'entry_price': entry_price,
                            'is_bottom_entry': is_bottom_entry
                        },
                        status=1,  # Active
                        message=f"50MA Strategy Entry"
                    )
                    
                    # Update stock status
                    stock.status = 8
                    stock.save()
                    
                    logger.info(f"Order placed successfully for {stock.script}: {order_id}")
                    
                    return {
                        'success': True,
                        'message': 'Order executed successfully',
                        'order_id': order_id,
                        'quantity': quantity,
                        'price': entry_price
                    }
                else:
                    error_msg = response.get("ErrorMessage", "Unknown error")
                    logger.error(f"Order failed for {stock.script}: {error_msg}")
                    return {
                        'success': False,
                        'message': error_msg,
                        'order_id': None
                    }
                    
            except Exception as e:
                logger.error(f"Exception placing order for {stock.script}: {str(e)}")
                return {
                    'success': False,
                    'message': f"Exception: {str(e)}",
                    'order_id': None
                }
