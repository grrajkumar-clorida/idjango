"""
50MA Strategy Implementation (Path A — canonical)

Strategy Logic:
- Entry: Price reached above 50MA value AND CMP-50MA range is max 5-6% only
- Exit: Price moves up 8-10% → book profit
- Partial Exit: If buy price is at bottom → book 50%, remaining 50% for long-term holding

The stocks.strategies.ma50_strategy_adapter crossover spec (1-5%) must not
run in Celery beat; Path A owns this name via data.tasks.
"""
from decimal import Decimal
from typing import Dict, Optional
from data.models import Stocks50MA, StockPriceData
from infra.utils.infra import safe_float

# Beat / registry skip this name so the Path B adapter cannot place 50MA orders.
PATH_A_STRATEGY_NAME = "50MA_Strategy"


class MA50Strategy:
    """50MA Trading Strategy"""
    
    def __init__(self):
        self.name = PATH_A_STRATEGY_NAME
        self.entry_range_min = 5.0  # Minimum % above 50MA
        self.entry_range_max = 6.0  # Maximum % above 50MA
        self.profit_target_min = 8.0  # Minimum profit % to book
        self.profit_target_max = 10.0  # Maximum profit % to book
        self.partial_exit_percent = 50.0  # % to exit if bought at bottom

    def assign_pre_trade_status(self, stock: Stocks50MA, live_data: Optional[StockPriceData]) -> int:
        """
        Status for names that are not yet in a position (status < 8).

        Most-specific bands first so 5-6% can become status 8 (Order).
        """
        if stock.status >= 8:
            return stock.status
        if not live_data:
            return stock.status

        cmp_price = safe_float(live_data.close_price)
        cmp_50ma = safe_float(live_data.live50ma)
        cmp_50pa = safe_float(live_data.cp50ma)
        sma_price = safe_float(stock.stock_cmp)

        if cmp_price <= 0 or cmp_50ma <= 0:
            return stock.status

        if cmp_price < cmp_50ma:
            return 0  # Invalid — below 50MA
        if cmp_50pa > self.entry_range_max:
            return 1  # Over value
        if self.entry_range_min <= cmp_50pa <= self.entry_range_max:
            if sma_price and cmp_price > sma_price:
                return 8  # Order — in 5-6% window and CMP above ChartInk CMP
            return 7  # Confirmation — in window, waiting for CMP > SMA CMP
        if 2.0 <= cmp_50pa < self.entry_range_min:
            return 7  # Confirmation — approaching entry
        if cmp_50pa < 1.0:
            return 2  # Stoploss — too close to 50MA
        if cmp_price > cmp_50ma:
            return 6  # Entry / watching
        return 4  # New
    
    def check_entry_condition(self, stock: Stocks50MA, live_data: StockPriceData) -> Dict:
        """
        Check if stock meets entry conditions for 50MA strategy
        
        Entry Conditions:
        1. Price is above 50MA value
        2. CMP-50MA range is between 5-6%
        3. Status should be 7 (Confirmation) or 8 (Order)
        
        Returns:
            Dict with 'can_enter': bool, 'reason': str, 'entry_price': float
        """
        if not live_data or live_data.live50ma is None:
            return {'can_enter': False, 'reason': 'No live data available'}
        
        cmp_price = safe_float(live_data.close_price)
        live_50ma = safe_float(live_data.live50ma)
        cp50ma_percent = safe_float(live_data.cp50ma)
        
        # Check if price is above 50MA
        if cmp_price <= live_50ma:
            return {
                'can_enter': False,
                'reason': f'Price {cmp_price} is not above 50MA {live_50ma}',
                'entry_price': cmp_price
            }
        
        # Check if CMP-50MA range is between 5-6%
        if cp50ma_percent < self.entry_range_min or cp50ma_percent > self.entry_range_max:
            return {
                'can_enter': False,
                'reason': f'CP50MA% {cp50ma_percent}% is not in range {self.entry_range_min}-{self.entry_range_max}%',
                'entry_price': cmp_price
            }
        
        # Check status - should be 7 (Confirmation) or 8 (Order)
        if stock.status not in [7, 8]:
            return {
                'can_enter': False,
                'reason': f'Status {stock.status} is not ready for entry (needs 7 or 8)',
                'entry_price': cmp_price
            }
        
        return {
            'can_enter': True,
            'reason': 'Entry conditions met',
            'entry_price': cmp_price,
            '50ma_value': live_50ma,
            'cp50ma_percent': cp50ma_percent
        }
    
    def calculate_position_size(self, entry_price: float, capital: float = 100000, risk_percent: float = 1.0) -> int:
        """
        Calculate position size based on entry price and risk
        
        Args:
            entry_price: Entry price of the stock
            capital: Available capital
            risk_percent: Risk percentage per trade (default 1%)
        
        Returns:
            Quantity to buy
        """
        risk_amount = capital * (risk_percent / 100)
        quantity = int(risk_amount / entry_price)
        
        # Minimum 1 share
        return max(1, quantity)
    
    def check_exit_condition(self, entry_price: float, current_price: float, 
                            is_bottom_entry: bool = False) -> Dict:
        """
        Check if exit conditions are met
        
        Exit Conditions:
        1. If profit is 8-10%: Book full profit
        2. If bought at bottom and profit > 5%: Book 50%, hold 50%
        
        Args:
            entry_price: Price at which stock was bought
            current_price: Current market price
            is_bottom_entry: Whether stock was bought at bottom of range
        
        Returns:
            Dict with 'should_exit': bool, 'exit_type': str, 'exit_percent': float
        """
        profit_percent = ((current_price - entry_price) / entry_price) * 100
        
        # Full exit: profit reached 8% (covers gap-through above 10%)
        if profit_percent >= self.profit_target_min:
            return {
                'should_exit': True,
                'exit_type': 'full',
                'exit_percent': 100.0,
                'profit_percent': profit_percent,
                'reason': f'Profit {profit_percent:.2f}% is in target range {self.profit_target_min}-{self.profit_target_max}%'
            }
        
        # Partial exit: Bought at bottom and profit > 5%
        if is_bottom_entry and profit_percent >= 5.0:
            return {
                'should_exit': True,
                'exit_type': 'partial',
                'exit_percent': self.partial_exit_percent,
                'profit_percent': profit_percent,
                'reason': f'Bought at bottom with profit {profit_percent:.2f}%, booking {self.partial_exit_percent}%'
            }
        
        return {
            'should_exit': False,
            'exit_type': None,
            'exit_percent': 0.0,
            'profit_percent': profit_percent,
            'reason': f'Profit {profit_percent:.2f}% does not meet exit criteria'
        }
    
    def is_bottom_entry(self, stock: Stocks50MA, live_data: StockPriceData) -> bool:
        """
        Check if entry is at the bottom of the 50MA range
        
        Bottom entry: Price is close to 50MA (within 5-5.5%)
        """
        if not live_data or live_data.live50ma is None:
            return False
        
        cp50ma_percent = safe_float(live_data.cp50ma)
        
        # Bottom entry is when CP50MA% is at lower end (5-5.5%)
        return 5.0 <= cp50ma_percent <= 5.5
    
    def get_target_prices(self, entry_price: float) -> Dict:
        """
        Calculate target prices for the trade
        
        Returns:
            Dict with target_1, target_2, target_3 prices
        """
        return {
            'target_1': entry_price * 1.08,  # 8% profit
            'target_2': entry_price * 1.10,  # 10% profit
            'target_3': entry_price * 1.15,  # 15% profit (long term)
        }
    
    def update_status_based_on_price(self, stock: Stocks50MA, live_data: StockPriceData, 
                                     entry_price: Optional[float] = None) -> int:
        """
        Update stock status based on current price vs targets
        
        Status progression:
        8: Order placed
        9: Target 1 reached (8% profit)
        10: Target 2 reached (10% profit)
        11: Target 3 reached (15% profit)
        12: Above T3 (hold for long term)
        
        Args:
            stock: Stocks50MA object
            live_data: StockPriceData object with live prices
            entry_price: Entry price (if None, uses stock.stock_cmp)
        
        Returns:
            New status value
        """
        if not live_data:
            return stock.status
        
        current_price = safe_float(live_data.close_price)
        entry = safe_float(entry_price if entry_price is not None else stock.stock_cmp)
        
        if not entry:
            return stock.status
        
        # Calculate profit percentage
        profit_percent = ((current_price - entry) / entry) * 100
        
        # Update status based on profit targets
        if profit_percent >= 15.0:
            return 12  # Above T3
        elif profit_percent >= 10.0:
            return 11  # Target 3
        elif profit_percent >= 8.0:
            return 10  # Target 2
        elif profit_percent >= 5.0:
            return 9   # Target 1
        
        # If still in position but no target hit, keep current status
        return stock.status if stock.status >= 8 else stock.status
