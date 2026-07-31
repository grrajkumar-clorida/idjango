"""
Test runner with reporting
"""
import unittest
import sys
import os
from io import StringIO
from datetime import datetime
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Import Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'idjango.settings')
import django
django.setup()

from django.test.utils import get_runner
from django.conf import settings


class TestRunner:
    """Custom test runner with reporting"""
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'tests': [],
            'summary': {}
        }
    
    def run_all_tests(self):
        """Run all tests and generate report"""
        print("=" * 80)
        print("PHASE 1 TEST SUITE")
        print("=" * 80)
        print()
        
        # Test modules
        test_modules = [
            'stocks.tests.test_base_strategy',
            'stocks.tests.test_strategy_executor',
            'stocks.tests.test_signal_processor',
            'stocks.tests.test_risk_manager',
            'stocks.tests.test_order_manager',
            'stocks.tests.test_position_tracker',
            'stocks.tests.test_exit_manager',
            'stocks.tests.test_integration',
        ]
        
        total_tests = 0
        total_failures = 0
        total_errors = 0
        total_skipped = 0
        
        for module_name in test_modules:
            print(f"\n{'=' * 80}")
            print(f"Running: {module_name}")
            print('=' * 80)
            
            try:
                # Load test suite
                loader = unittest.TestLoader()
                suite = loader.loadTestsFromName(module_name)
                
                # Run tests
                stream = StringIO()
                runner = unittest.TextTestRunner(stream=stream, verbosity=2)
                result = runner.run(suite)
                
                # Print output
                output = stream.getvalue()
                print(output)
                
                # Collect results
                module_result = {
                    'module': module_name,
                    'tests_run': result.testsRun,
                    'failures': len(result.failures),
                    'errors': len(result.errors),
                    'skipped': len(result.skipped),
                    'success': result.wasSuccessful()
                }
                
                self.results['tests'].append(module_result)
                
                total_tests += result.testsRun
                total_failures += len(result.failures)
                total_errors += len(result.errors)
                total_skipped += len(result.skipped)
                
            except Exception as e:
                print(f"ERROR loading {module_name}: {str(e)}")
                self.results['tests'].append({
                    'module': module_name,
                    'error': str(e)
                })
        
        # Summary
        self.results['summary'] = {
            'total_tests': total_tests,
            'failures': total_failures,
            'errors': total_errors,
            'skipped': total_skipped,
            'success_rate': ((total_tests - total_failures - total_errors) / total_tests * 100) if total_tests > 0 else 0
        }
        
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"Total Tests: {total_tests}")
        print(f"Failures: {total_failures}")
        print(f"Errors: {total_errors}")
        print(f"Skipped: {total_skipped}")
        print(f"Success Rate: {self.results['summary']['success_rate']:.2f}%")
        print("=" * 80)
        
        return self.results
    
    def generate_report(self, output_file='test_report.json'):
        """Generate JSON test report"""
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\nTest report saved to: {output_file}")
    
    def generate_html_report(self, output_file='test_report.html'):
        """Generate HTML test report"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Phase 1 Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .summary {{ background: #f5f5f5; padding: 20px; border-radius: 5px; margin: 20px 0; }}
        .test-module {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
        .success {{ color: green; }}
        .failure {{ color: red; }}
        .error {{ color: orange; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 10px; text-align: left; border: 1px solid #ddd; }}
        th {{ background: #4CAF50; color: white; }}
    </style>
</head>
<body>
    <h1>Phase 1 Test Report</h1>
    <p>Generated: {self.results['timestamp']}</p>
    
    <div class="summary">
        <h2>Summary</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Total Tests</td>
                <td>{self.results['summary']['total_tests']}</td>
            </tr>
            <tr>
                <td>Failures</td>
                <td class="failure">{self.results['summary']['failures']}</td>
            </tr>
            <tr>
                <td>Errors</td>
                <td class="error">{self.results['summary']['errors']}</td>
            </tr>
            <tr>
                <td>Skipped</td>
                <td>{self.results['summary']['skipped']}</td>
            </tr>
            <tr>
                <td>Success Rate</td>
                <td class="success">{self.results['summary']['success_rate']:.2f}%</td>
            </tr>
        </table>
    </div>
    
    <h2>Test Modules</h2>
"""
        
        for test in self.results['tests']:
            status_class = 'success' if test.get('success', False) else 'failure'
            html += f"""
    <div class="test-module">
        <h3>{test['module']}</h3>
        <table>
            <tr>
                <td>Tests Run</td>
                <td>{test.get('tests_run', 0)}</td>
            </tr>
            <tr>
                <td>Failures</td>
                <td class="failure">{test.get('failures', 0)}</td>
            </tr>
            <tr>
                <td>Errors</td>
                <td class="error">{test.get('errors', 0)}</td>
            </tr>
            <tr>
                <td>Status</td>
                <td class="{status_class}">{'PASSED' if test.get('success') else 'FAILED'}</td>
            </tr>
        </table>
    </div>
"""
        
        html += """
</body>
</html>
"""
        
        with open(output_file, 'w') as f:
            f.write(html)
        print(f"HTML report saved to: {output_file}")


if __name__ == '__main__':
    runner = TestRunner()
    results = runner.run_all_tests()
    runner.generate_report('test_report.json')
    runner.generate_html_report('test_report.html')
