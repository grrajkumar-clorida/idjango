"""
Strategy Aggregator
Combines signals from multiple strategies
"""
import logging
from typing import Dict, List, Optional
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)


class StrategyAggregator:
    """Aggregates signals from multiple strategies"""
    
    def __init__(self, aggregation_method: str = 'weighted_average'):
        """
        Initialize aggregator
        
        Args:
            aggregation_method: Method to use for aggregation
                - 'weighted_average': Weight by signal strength
                - 'majority': Majority vote
                - 'strongest': Use strongest signal
                - 'consensus': Require consensus
        """
        self.aggregation_method = aggregation_method
    
    def aggregate_signals(self, signals: List[Dict], 
                         strategy_weights: Optional[Dict[str, float]] = None) -> Optional[Dict]:
        """
        Aggregate multiple signals for the same stock
        
        Args:
            signals: List of signal dictionaries
            strategy_weights: Optional weights for each strategy
        
        Returns:
            Aggregated signal dict or None
        """
        if not signals:
            return None
        
        if len(signals) == 1:
            return signals[0]
        
        # Group by stock code
        stock_signals = defaultdict(list)
        for signal in signals:
            stock_code = signal.get('stock_code')
            if stock_code:
                stock_signals[stock_code].append(signal)
        
        aggregated_results = []
        
        for stock_code, sigs in stock_signals.items():
            aggregated = self._aggregate_stock_signals(sigs, strategy_weights)
            if aggregated:
                aggregated_results.append(aggregated)
        
        # Return first aggregated signal (or all if needed)
        return aggregated_results[0] if aggregated_results else None
    
    def _aggregate_stock_signals(self, signals: List[Dict], 
                                 strategy_weights: Optional[Dict[str, float]] = None) -> Optional[Dict]:
        """
        Aggregate signals for a single stock
        
        Args:
            signals: List of signals for the stock
            strategy_weights: Optional weights for strategies
        
        Returns:
            Aggregated signal dict
        """
        if not signals:
            return None
        
        # Separate by action type
        buy_signals = [s for s in signals if s.get('action') == 'BUY']
        sell_signals = [s for s in signals if s.get('action') == 'SELL']
        hold_signals = [s for s in signals if s.get('action') == 'HOLD']
        
        # Apply aggregation method
        if self.aggregation_method == 'weighted_average':
            return self._weighted_average_aggregation(
                buy_signals, sell_signals, hold_signals, strategy_weights
            )
        elif self.aggregation_method == 'majority':
            return self._majority_vote_aggregation(buy_signals, sell_signals, hold_signals)
        elif self.aggregation_method == 'strongest':
            return self._strongest_signal_aggregation(buy_signals, sell_signals, hold_signals)
        elif self.aggregation_method == 'consensus':
            return self._consensus_aggregation(buy_signals, sell_signals, hold_signals)
        else:
            logger.warning(f"Unknown aggregation method: {self.aggregation_method}")
            return self._weighted_average_aggregation(
                buy_signals, sell_signals, hold_signals, strategy_weights
            )
    
    def _weighted_average_aggregation(self, buy_signals: List[Dict], 
                                     sell_signals: List[Dict], 
                                     hold_signals: List[Dict],
                                     strategy_weights: Optional[Dict[str, float]] = None) -> Optional[Dict]:
        """Weighted average aggregation based on signal strength"""
        # Calculate weighted scores
        buy_score = sum(
            (strategy_weights.get(s.get('strategy_name', ''), 1.0) if strategy_weights else 1.0) * 
            s.get('strength', 0) 
            for s in buy_signals
        )
        
        sell_score = sum(
            (strategy_weights.get(s.get('strategy_name', ''), 1.0) if strategy_weights else 1.0) * 
            s.get('strength', 0) 
            for s in sell_signals
        )
        
        hold_score = sum(
            (strategy_weights.get(s.get('strategy_name', ''), 1.0) if strategy_weights else 1.0) * 
            s.get('strength', 0) 
            for s in hold_signals
        )
        
        # Determine action
        if buy_score > sell_score and buy_score > hold_score:
            action = 'BUY'
            strength = min(1.0, buy_score / len(buy_signals) if buy_signals else 0)
            price_signals = buy_signals
        elif sell_score > buy_score and sell_score > hold_score:
            action = 'SELL'
            strength = min(1.0, sell_score / len(sell_signals) if sell_signals else 0)
            price_signals = sell_signals
        else:
            action = 'HOLD'
            strength = 0.3
            price_signals = buy_signals + sell_signals if buy_signals or sell_signals else hold_signals
        
        # Calculate average price
        prices = [s.get('price', 0) for s in price_signals if s.get('price', 0) > 0]
        avg_price = sum(prices) / len(prices) if prices else 0
        
        # Calculate average stop_loss and take_profit
        stop_losses = [s.get('stop_loss') for s in price_signals if s.get('stop_loss')]
        avg_stop_loss = sum(stop_losses) / len(stop_losses) if stop_losses else None
        
        take_profits = [s.get('take_profit') for s in price_signals if s.get('take_profit')]
        avg_take_profit = sum(take_profits) / len(take_profits) if take_profits else None
        
        return {
            'action': action,
            'strength': strength,
            'price': avg_price,
            'stop_loss': avg_stop_loss,
            'take_profit': avg_take_profit,
            'aggregation_method': 'weighted_average',
            'buy_score': buy_score,
            'sell_score': sell_score,
            'hold_score': hold_score,
            'signal_count': len(buy_signals) + len(sell_signals) + len(hold_signals),
            'strategies': [s.get('strategy_name') for s in buy_signals + sell_signals + hold_signals],
            'metadata': {
                'buy_signals': len(buy_signals),
                'sell_signals': len(sell_signals),
                'hold_signals': len(hold_signals),
                'aggregated_at': datetime.now().isoformat()
            }
        }
    
    def _majority_vote_aggregation(self, buy_signals: List[Dict], 
                                   sell_signals: List[Dict], 
                                   hold_signals: List[Dict]) -> Optional[Dict]:
        """Majority vote aggregation"""
        buy_count = len(buy_signals)
        sell_count = len(sell_signals)
        hold_count = len(hold_signals)
        
        if buy_count > sell_count and buy_count > hold_count:
            action = 'BUY'
            price_signals = buy_signals
        elif sell_count > buy_count and sell_count > hold_count:
            action = 'SELL'
            price_signals = sell_signals
        else:
            action = 'HOLD'
            price_signals = buy_signals + sell_signals if buy_signals or sell_signals else hold_signals
        
        # Use strongest signal from winning group
        if price_signals:
            strongest = max(price_signals, key=lambda s: s.get('strength', 0))
            return {
                'action': action,
                'strength': strongest.get('strength', 0.5),
                'price': strongest.get('price'),
                'stop_loss': strongest.get('stop_loss'),
                'take_profit': strongest.get('take_profit'),
                'aggregation_method': 'majority',
                'signal_count': buy_count + sell_count + hold_count,
                'strategies': [s.get('strategy_name') for s in buy_signals + sell_signals + hold_signals],
                'metadata': {
                    'buy_count': buy_count,
                    'sell_count': sell_count,
                    'hold_count': hold_count
                }
            }
        
        return None
    
    def _strongest_signal_aggregation(self, buy_signals: List[Dict], 
                                     sell_signals: List[Dict], 
                                     hold_signals: List[Dict]) -> Optional[Dict]:
        """Use strongest signal"""
        all_signals = buy_signals + sell_signals + hold_signals
        
        if not all_signals:
            return None
        
        strongest = max(all_signals, key=lambda s: s.get('strength', 0))
        
        return {
            'action': strongest.get('action'),
            'strength': strongest.get('strength', 0.5),
            'price': strongest.get('price'),
            'stop_loss': strongest.get('stop_loss'),
            'take_profit': strongest.get('take_profit'),
            'aggregation_method': 'strongest',
            'signal_count': len(all_signals),
            'strategies': [strongest.get('strategy_name')],
            'metadata': {
                'selected_strategy': strongest.get('strategy_name'),
                'all_signals': len(all_signals)
            }
        }
    
    def _consensus_aggregation(self, buy_signals: List[Dict], 
                              sell_signals: List[Dict], 
                              hold_signals: List[Dict]) -> Optional[Dict]:
        """Require consensus (all signals must agree)"""
        buy_count = len(buy_signals)
        sell_count = len(sell_signals)
        hold_count = len(hold_signals)
        
        total_signals = buy_count + sell_count + hold_count
        
        if total_signals == 0:
            return None
        
        # Consensus: all signals must be same action
        if buy_count == total_signals:
            action = 'BUY'
            price_signals = buy_signals
        elif sell_count == total_signals:
            action = 'SELL'
            price_signals = sell_signals
        elif hold_count == total_signals:
            action = 'HOLD'
            price_signals = hold_signals
        else:
            # No consensus - return None
            logger.debug(f"No consensus: {buy_count} BUY, {sell_count} SELL, {hold_count} HOLD")
            return None
        
        # Average consensus signals
        if price_signals:
            avg_strength = sum(s.get('strength', 0) for s in price_signals) / len(price_signals)
            prices = [s.get('price', 0) for s in price_signals if s.get('price', 0) > 0]
            avg_price = sum(prices) / len(prices) if prices else 0
            
            return {
                'action': action,
                'strength': avg_strength,
                'price': avg_price,
                'stop_loss': price_signals[0].get('stop_loss') if price_signals else None,
                'take_profit': price_signals[0].get('take_profit') if price_signals else None,
                'aggregation_method': 'consensus',
                'signal_count': total_signals,
                'strategies': [s.get('strategy_name') for s in price_signals],
                'metadata': {
                    'consensus_reached': True,
                    'all_signals': total_signals
                }
            }
        
        return None
