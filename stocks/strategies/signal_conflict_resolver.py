"""
Signal Conflict Resolver
Handles conflicting signals from different strategies
"""
import logging
from typing import Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class SignalConflictResolver:
    """Resolves conflicts between signals from different strategies"""
    
    def __init__(self, resolution_method: str = 'strength_based'):
        """
        Initialize conflict resolver
        
        Args:
            resolution_method: Method to resolve conflicts
                - 'strength_based': Use strongest signal
                - 'priority_based': Use strategy priority
                - 'recent_based': Use most recent signal
                - 'skip_conflicts': Skip conflicting signals
        """
        self.resolution_method = resolution_method
        self.strategy_priorities = {}  # Can be set via set_strategy_priorities
    
    def set_strategy_priorities(self, priorities: Dict[str, int]):
        """
        Set priority for strategies (higher number = higher priority)
        
        Args:
            priorities: Dict mapping strategy names to priority values
        """
        self.strategy_priorities = priorities
        logger.info(f"Strategy priorities set: {priorities}")
    
    def resolve_conflicts(self, signals: List[Dict]) -> List[Dict]:
        """
        Resolve conflicts in signals
        
        Args:
            signals: List of signals (may have conflicts)
        
        Returns:
            List of resolved signals (conflicts resolved)
        """
        if not signals:
            return []
        
        # Group by stock code
        stock_signals = defaultdict(list)
        for signal in signals:
            stock_code = signal.get('stock_code')
            if stock_code:
                stock_signals[stock_code].append(signal)
        
        resolved = []
        
        for stock_code, sigs in stock_signals.items():
            resolved_sigs = self._resolve_stock_conflicts(sigs)
            resolved.extend(resolved_sigs)
        
        return resolved
    
    def _resolve_stock_conflicts(self, signals: List[Dict]) -> List[Dict]:
        """
        Resolve conflicts for signals of a single stock
        
        Args:
            signals: List of signals for the stock
        
        Returns:
            List of resolved signals
        """
        if not signals:
            return []
        
        if len(signals) == 1:
            return signals
        
        # Separate by action
        buy_signals = [s for s in signals if s.get('action') == 'BUY']
        sell_signals = [s for s in signals if s.get('action') == 'SELL')
        hold_signals = [s for s in signals if s.get('action') == 'HOLD']
        
        # Check for conflicts
        has_conflict = (buy_signals and sell_signals) or \
                      (buy_signals and not buy_signals and sell_signals and not sell_signals)
        
        if not has_conflict:
            # No conflict - return all signals
            return signals
        
        # Resolve conflict based on method
        if self.resolution_method == 'strength_based':
            return self._resolve_by_strength(buy_signals, sell_signals, hold_signals)
        elif self.resolution_method == 'priority_based':
            return self._resolve_by_priority(buy_signals, sell_signals, hold_signals)
        elif self.resolution_method == 'recent_based':
            return self._resolve_by_recent(buy_signals, sell_signals, hold_signals)
        elif self.resolution_method == 'skip_conflicts':
            return self._skip_conflicts(buy_signals, sell_signals, hold_signals)
        else:
            logger.warning(f"Unknown resolution method: {self.resolution_method}")
            return self._resolve_by_strength(buy_signals, sell_signals, hold_signals)
    
    def _resolve_by_strength(self, buy_signals: List[Dict], 
                            sell_signals: List[Dict], 
                            hold_signals: List[Dict]) -> List[Dict]:
        """Resolve by signal strength"""
        resolved = []
        
        if buy_signals and sell_signals:
            # Conflict: BUY vs SELL
            max_buy_strength = max([s.get('strength', 0) for s in buy_signals])
            max_sell_strength = max([s.get('strength', 0) for s in sell_signals])
            
            if max_buy_strength > max_sell_strength:
                # BUY wins
                strongest_buy = max(buy_signals, key=lambda s: s.get('strength', 0))
                resolved.append(strongest_buy)
                logger.info(f"Conflict resolved: BUY (strength {max_buy_strength:.2f}) > SELL (strength {max_sell_strength:.2f})")
            elif max_sell_strength > max_buy_strength:
                # SELL wins
                strongest_sell = max(sell_signals, key=lambda s: s.get('strength', 0))
                resolved.append(strongest_sell)
                logger.info(f"Conflict resolved: SELL (strength {max_sell_strength:.2f}) > BUY (strength {max_buy_strength:.2f})")
            else:
                # Equal strength - skip both
                logger.warning(f"Equal strength conflict - skipping both signals")
        else:
            # No conflict - add all
            resolved.extend(buy_signals)
            resolved.extend(sell_signals)
            resolved.extend(hold_signals)
        
        return resolved
    
    def _resolve_by_priority(self, buy_signals: List[Dict], 
                            sell_signals: List[Dict], 
                            hold_signals: List[Dict]) -> List[Dict]:
        """Resolve by strategy priority"""
        resolved = []
        
        if buy_signals and sell_signals:
            # Conflict: BUY vs SELL
            # Get highest priority signal from each group
            buy_with_priority = [
                (s, self.strategy_priorities.get(s.get('strategy_name', ''), 0))
                for s in buy_signals
            ]
            sell_with_priority = [
                (s, self.strategy_priorities.get(s.get('strategy_name', ''), 0))
                for s in sell_signals
            ]
            
            max_buy_priority = max([p for _, p in buy_with_priority]) if buy_with_priority else 0
            max_sell_priority = max([p for _, p in sell_with_priority]) if sell_with_priority else 0
            
            if max_buy_priority > max_sell_priority:
                # BUY wins
                highest_buy = max(buy_with_priority, key=lambda x: x[1])[0]
                resolved.append(highest_buy)
                logger.info(f"Conflict resolved by priority: BUY (priority {max_buy_priority}) > SELL (priority {max_sell_priority})")
            elif max_sell_priority > max_buy_priority:
                # SELL wins
                highest_sell = max(sell_with_priority, key=lambda x: x[1])[0]
                resolved.append(highest_sell)
                logger.info(f"Conflict resolved by priority: SELL (priority {max_sell_priority}) > BUY (priority {max_buy_priority})")
            else:
                # Equal priority - use strength
                return self._resolve_by_strength(buy_signals, sell_signals, hold_signals)
        else:
            # No conflict - add all
            resolved.extend(buy_signals)
            resolved.extend(sell_signals)
            resolved.extend(hold_signals)
        
        return resolved
    
    def _resolve_by_recent(self, buy_signals: List[Dict], 
                          sell_signals: List[Dict], 
                          hold_signals: List[Dict]) -> List[Dict]:
        """Resolve by most recent signal"""
        resolved = []
        
        if buy_signals and sell_signals:
            # Conflict: BUY vs SELL
            # Get most recent from each
            from datetime import datetime
            
            buy_times = [
                (s, datetime.fromisoformat(s.get('processed_at', datetime.now().isoformat())))
                for s in buy_signals if s.get('processed_at')
            ]
            sell_times = [
                (s, datetime.fromisoformat(s.get('processed_at', datetime.now().isoformat())))
                for s in sell_signals if s.get('processed_at')
            ]
            
            if buy_times and sell_times:
                latest_buy = max(buy_times, key=lambda x: x[1])[0]
                latest_sell = max(sell_times, key=lambda x: x[1])[0]
                
                if buy_times[-1][1] > sell_times[-1][1]:
                    resolved.append(latest_buy)
                    logger.info("Conflict resolved: BUY is more recent")
                else:
                    resolved.append(latest_sell)
                    logger.info("Conflict resolved: SELL is more recent")
            else:
                # Fallback to strength
                return self._resolve_by_strength(buy_signals, sell_signals, hold_signals)
        else:
            # No conflict - add all
            resolved.extend(buy_signals)
            resolved.extend(sell_signals)
            resolved.extend(hold_signals)
        
        return resolved
    
    def _skip_conflicts(self, buy_signals: List[Dict], 
                       sell_signals: List[Dict], 
                       hold_signals: List[Dict]) -> List[Dict]:
        """Skip conflicting signals"""
        resolved = []
        
        if buy_signals and sell_signals:
            # Conflict exists - skip both
            logger.warning("Conflicting signals detected - skipping both")
            # Only add HOLD signals
            resolved.extend(hold_signals)
        else:
            # No conflict - add all
            resolved.extend(buy_signals)
            resolved.extend(sell_signals)
            resolved.extend(hold_signals)
        
        return resolved
