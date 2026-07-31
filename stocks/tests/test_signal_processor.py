"""
Unit tests for SignalProcessor
"""
import unittest
from datetime import datetime, timedelta
from stocks.engine.signal_processor import SignalProcessor


class SignalProcessorTestCase(unittest.TestCase):
    """Test cases for SignalProcessor"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.processor = SignalProcessor(validation_window=5)
    
    def test_process_valid_signal(self):
        """Test processing a valid signal"""
        signal = {
            'action': 'BUY',
            'strength': 0.8,
            'price': 100.0
        }
        
        processed = self.processor.process_signal(signal, "TEST", "TestStrategy")
        
        self.assertIsNotNone(processed)
        self.assertEqual(processed['stock_code'], "TEST")
        self.assertEqual(processed['strategy_name'], "TestStrategy")
        self.assertIn('processed_at', processed)
        self.assertIn('signal_id', processed)
    
    def test_process_invalid_signal_structure(self):
        """Test processing invalid signal structure"""
        invalid_signal = {'strength': 0.8}  # Missing 'action'
        
        processed = self.processor.process_signal(invalid_signal, "TEST", "TestStrategy")
        self.assertIsNone(processed)
    
    def test_process_invalid_action(self):
        """Test processing signal with invalid action"""
        invalid_signal = {'action': 'INVALID'}
        
        processed = self.processor.process_signal(invalid_signal, "TEST", "TestStrategy")
        self.assertIsNone(processed)
    
    def test_duplicate_signal_prevention(self):
        """Test duplicate signal prevention"""
        signal = {
            'action': 'BUY',
            'strength': 0.8,
            'price': 100.0
        }
        
        # Process first signal
        processed1 = self.processor.process_signal(signal, "TEST", "TestStrategy")
        self.assertIsNotNone(processed1)
        
        # Process duplicate signal immediately
        processed2 = self.processor.process_signal(signal, "TEST", "TestStrategy")
        self.assertIsNone(processed2)  # Should be ignored
    
    def test_aggregate_signals(self):
        """Test signal aggregation"""
        signals = [
            {'stock_code': 'TEST1', 'action': 'BUY', 'strength': 0.8, 'price': 100},
            {'stock_code': 'TEST1', 'action': 'BUY', 'strength': 0.6, 'price': 101},
            {'stock_code': 'TEST2', 'action': 'SELL', 'strength': 0.7, 'price': 200},
        ]
        
        aggregated = self.processor.aggregate_signals(signals)
        
        self.assertIsNotNone(aggregated)
        self.assertEqual(len(aggregated), 2)  # Two stocks
        
        # Check TEST1 aggregation
        test1 = next((s for s in aggregated if s['stock_code'] == 'TEST1'), None)
        self.assertIsNotNone(test1)
        self.assertEqual(test1['action'], 'BUY')
        self.assertEqual(test1['buy_signals'], 2)
    
    def test_resolve_conflicts(self):
        """Test conflict resolution"""
        signals = [
            {'stock_code': 'TEST', 'action': 'BUY', 'strength': 0.8, 'price': 100},
            {'stock_code': 'TEST', 'action': 'SELL', 'strength': 0.6, 'price': 101},
        ]
        
        resolved = self.processor.resolve_conflicts(signals)
        
        # BUY signal should win (higher strength)
        buy_signals = [s for s in resolved if s['action'] == 'BUY']
        self.assertEqual(len(buy_signals), 1)
    
    def test_resolve_conflicts_equal_strength(self):
        """Test conflict resolution with equal strength"""
        signals = [
            {'stock_code': 'TEST', 'action': 'BUY', 'strength': 0.8, 'price': 100},
            {'stock_code': 'TEST', 'action': 'SELL', 'strength': 0.8, 'price': 101},
        ]
        
        resolved = self.processor.resolve_conflicts(signals)
        
        # Both should be skipped (conflict)
        self.assertEqual(len(resolved), 0)
    
    def test_clean_old_signals(self):
        """Test cleaning old signals"""
        signal = {
            'action': 'BUY',
            'strength': 0.8,
            'price': 100.0
        }
        
        # Process signal
        self.processor.process_signal(signal, "TEST", "TestStrategy")
        
        # Manually set old timestamp
        signal_key = "TEST_TestStrategy_BUY"
        self.processor.recent_signals[signal_key] = datetime.now() - timedelta(seconds=20)
        
        # Process new signal (should trigger cleanup)
        self.processor.process_signal(signal, "TEST2", "TestStrategy")
        
        # Old signal should be cleaned up
        self.assertNotIn(signal_key, self.processor.recent_signals)


if __name__ == '__main__':
    unittest.main()
