"""
Signal Processor
Processes and validates strategy signals
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class SignalProcessor:
    """Processes and validates trading signals"""
    
    def __init__(self, validation_window: int = 5):
        """
        Initialize signal processor
        
        Args:
            validation_window: Time window in seconds for signal validation
        """
        self.validation_window = validation_window
        self.recent_signals = {}  # Track recent signals to avoid duplicates
    
    def process_signal(self, signal: Dict, stock_code: str, 
                      strategy_name: str) -> Optional[Dict]:
        """
        Process a signal from a strategy
        
        Args:
            signal: Signal dictionary
            stock_code: Stock code
            strategy_name: Strategy name
        
        Returns:
            Processed signal dict or None if invalid
        """
        if not signal:
            return None
        
        # Validate signal structure
        if not self._validate_signal_structure(signal):
            logger.warning(f"Invalid signal structure from {strategy_name}")
            return None
        
        # Check for duplicate signals
        signal_key = f"{stock_code}_{strategy_name}_{signal.get('action')}"
        if self._is_duplicate_signal(signal_key):
            logger.debug(f"Duplicate signal ignored: {signal_key}")
            return None
        
        # Add metadata
        processed_signal = signal.copy()
        processed_signal['stock_code'] = stock_code
        processed_signal['strategy_name'] = strategy_name
        processed_signal['processed_at'] = datetime.now()
        processed_signal['signal_id'] = signal_key
        
        # Record signal
        self.recent_signals[signal_key] = datetime.now()
        
        # Clean old signals
        self._clean_old_signals()
        
        return processed_signal
    
    def aggregate_signals(self, signals: List[Dict]) -> Dict:
        """
        Aggregate multiple signals for the same stock
        
        Args:
            signals: List of signals
        
        Returns:
            Aggregated signal dict
        """
        if not signals:
            return None
        
        # Group by stock code
        stock_signals = {}
        for signal in signals:
            stock_code = signal.get('stock_code')
            if stock_code not in stock_signals:
                stock_signals[stock_code] = []
            stock_signals[stock_code].append(signal)
        
        aggregated = []
        
        for stock_code, sigs in stock_signals.items():
            # Count actions
            buy_count = sum(1 for s in sigs if s.get('action') == 'BUY')
            sell_count = sum(1 for s in sigs if s.get('action') == 'SELL')
            hold_count = sum(1 for s in sigs if s.get('action') == 'HOLD')
            
            # Calculate average strength
            strengths = [s.get('strength', 0) for s in sigs]
            avg_strength = sum(strengths) / len(strengths) if strengths else 0
            
            # Determine final action
            if buy_count > sell_count:
                final_action = 'BUY'
            elif sell_count > buy_count:
                final_action = 'SELL'
            else:
                final_action = 'HOLD'
            
            # Get average price
            prices = [s.get('price', 0) for s in sigs if s.get('price')]
            avg_price = sum(prices) / len(prices) if prices else 0
            
            aggregated.append({
                'stock_code': stock_code,
                'action': final_action,
                'strength': avg_strength,
                'price': avg_price,
                'signal_count': len(sigs),
                'buy_signals': buy_count,
                'sell_signals': sell_count,
                'strategies': [s.get('strategy_name') for s in sigs],
                'processed_at': datetime.now()
            })
        
        return aggregated
    
    def resolve_conflicts(self, signals: List[Dict]) -> List[Dict]:
        """
        Resolve conflicting signals (e.g., one BUY, one SELL)
        
        Args:
            signals: List of signals
        
        Returns:
            List of resolved signals
        """
        if not signals:
            return []
        
        # Group by stock
        stock_signals = {}
        for signal in signals:
            stock_code = signal.get('stock_code')
            if stock_code not in stock_signals:
                stock_signals[stock_code] = []
            stock_signals[stock_code].append(signal)
        
        resolved = []
        
        for stock_code, sigs in stock_signals.items():
            buy_signals = [s for s in sigs if s.get('action') == 'BUY']
            sell_signals = [s for s in sigs if s.get('action') == 'SELL']
            
            # If conflicting, prioritize by strength
            if buy_signals and sell_signals:
                buy_strength = max([s.get('strength', 0) for s in buy_signals])
                sell_strength = max([s.get('strength', 0) for s in sell_signals])
                
                if buy_strength > sell_strength:
                    resolved.extend(buy_signals)
                elif sell_strength > buy_strength:
                    resolved.extend(sell_signals)
                else:
                    # Equal strength - skip both (conflict)
                    logger.warning(f"Conflicting signals for {stock_code} with equal strength - skipping")
            else:
                resolved.extend(sigs)
        
        return resolved
    
    def _validate_signal_structure(self, signal: Dict) -> bool:
        """Validate signal has required fields"""
        required_fields = ['action']
        
        for field in required_fields:
            if field not in signal:
                return False
        
        # Validate action value
        if signal['action'] not in ['BUY', 'SELL', 'HOLD']:
            return False
        
        return True
    
    def _is_duplicate_signal(self, signal_key: str) -> bool:
        """Check if signal is duplicate within validation window"""
        if signal_key in self.recent_signals:
            signal_time = self.recent_signals[signal_key]
            if datetime.now() - signal_time < timedelta(seconds=self.validation_window):
                return True
        
        return False
    
    def _clean_old_signals(self):
        """Remove signals older than validation window"""
        cutoff_time = datetime.now() - timedelta(seconds=self.validation_window * 2)
        
        keys_to_remove = [
            key for key, time in self.recent_signals.items()
            if time < cutoff_time
        ]
        
        for key in keys_to_remove:
            del self.recent_signals[key]
