#!/usr/bin/env python3
"""
Test runner for Disk Extractor

Runs all unit tests and provides comprehensive reporting.
"""

import unittest
import sys
import os
from pathlib import Path
from io import StringIO

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'



class ColoredTextTestResult(unittest.TextTestResult):
    """Test result class with colored output"""
    
    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.success_count = 0
        self.verbosity = verbosity  # Store verbosity for later use
    
    def addSuccess(self, test):
        super().addSuccess(test)
        self.success_count += 1
        if self.verbosity > 1:
            self.stream.write(f"{GREEN}✓ PASS{RESET}: ")
            self.stream.writeln(self.getDescription(test))
    
    def addError(self, test, err):
        super().addError(test, err)
        if self.verbosity > 1:
            self.stream.write(f"{RED}❌ ERROR{RESET}: ")
            self.stream.writeln(self.getDescription(test))
    
    def addFailure(self, test, err):
        super().addFailure(test, err)
        if self.verbosity > 1:
            self.stream.write(f"{RED}❌ FAIL{RESET}: ")
            self.stream.writeln(self.getDescription(test))
    
    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        if self.verbosity > 1:
            self.stream.write(f"{YELLOW}⚠️  SKIP{RESET}: ")
            self.stream.writeln(f"{self.getDescription(test)} ({reason})")


class ColoredTextTestRunner(unittest.TextTestRunner):
    """Test runner with colored output"""
    
    resultclass = ColoredTextTestResult
    
    def run(self, test):
        result = super().run(test)
        
        # Print summary
        print("\n" + "=" * 70)
        print("📊 TEST SUMMARY")
        print("=" * 70)
        
        total_tests = result.testsRun
        successes = result.success_count
        failures = len(result.failures)
        errors = len(result.errors)
        skipped = len(result.skipped)
        
        print(f"Total Tests: {total_tests}")
        print(f"{GREEN}✓ Passed: {successes}{RESET}")
        if failures > 0:
            print(f"{RED}❌ Failed: {failures}{RESET}")
        if errors > 0:
            print(f"{RED}❌ Errors: {errors}{RESET}")
        if skipped > 0:
            print(f"{YELLOW}⚠️  Skipped: {skipped}{RESET}")
        
        success_rate = (successes / total_tests * 100) if total_tests > 0 else 0
        print(f"Success Rate: {success_rate:.1f}%")
        
        if result.wasSuccessful():
            print("\n{GREEN}🎉 ALL TESTS PASSED!{RESET}")
        else:
            print(f"\n{RED}❌ {failures + errors} TEST(S) FAILED{RESET}")
            
            if result.failures:
                print("\n📋 FAILURES:")
                for test, traceback in result.failures:
                    print(f"  • {test}")
            
            if result.errors:
                print("\n📋 ERRORS:")
                for test, traceback in result.errors:
                    print(f"  • {test}")
        
        return result


def discover_tests(test_dir: str = "tests/unit") -> unittest.TestSuite:
    """
    Discover and load all tests from the specified directory
    
    Args:
        test_dir: Directory containing test files
        
    Returns:
        Test suite containing all discovered tests
    """
    loader = unittest.TestLoader()
    start_dir = project_root / test_dir
    
    if not start_dir.exists():
        print(f"❌ Test directory not found: {start_dir}")
        return unittest.TestSuite()
    
    suite = loader.discover(str(start_dir), pattern='test_*.py')
    return suite


def run_specific_test(test_name: str) -> None:
    """
    Run a specific test module or test case
    
    Args:
        test_name: Name of test module or test case
    """
    try:
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromName(test_name)
        runner = ColoredTextTestRunner(verbosity=2)
        runner.run(suite)
    except Exception as e:
        print(f"{RED}❌ Error running test '{test_name}': {e}{RESET}")


def run_all_tests(verbosity: int = 2) -> bool:
    """
    Run all unit tests
    
    Args:
        verbosity: Test output verbosity level
        
    Returns:
        True if all tests passed
    """
    print("🧪 DISK EXTRACTOR - UNIT TEST SUITE")
    print("=" * 70)
    
    # Discover all unit tests
    suite = discover_tests("tests/unit")
    
    if suite.countTestCases() == 0:
        print("❌ No tests found!")
        return False
    
    print(f"Found {suite.countTestCases()} test(s)")
    
    # List test modules found
    test_modules = set()
    for test_group in suite:
        for test_case in test_group:
            if hasattr(test_case, '_testMethodName'):
                module_name = test_case.__class__.__module__.split('.')[-1]
                test_modules.add(module_name)
    
    print(f"Test modules: {', '.join(sorted(test_modules))}")
    print()
    
    # Run tests
    runner = ColoredTextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def run_integration_tests(verbosity: int = 2) -> bool:
    """
    Run integration tests
    
    Args:
        verbosity: Test output verbosity level
        
    Returns:
        True if all tests passed
    """
    print("🔗 DISK EXTRACTOR - INTEGRATION TEST SUITE")
    print("=" * 70)
    
    # Discover integration tests
    suite = discover_tests("tests/integration")
    
    if suite.countTestCases() == 0:
        print("⚠️  No integration tests found")
        return True
    
    print(f"Found {suite.countTestCases()} integration test(s)")
    print()
    
    # Run tests
    runner = ColoredTextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def main():
    """Main test runner entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Disk Extractor tests")
    parser.add_argument(
        '--unit', 
        action='store_true', 
        help='Run unit tests only'
    )
    parser.add_argument(
        '--integration', 
        action='store_true', 
        help='Run integration tests only'
    )
    parser.add_argument(
        '--test', 
        type=str, 
        help='Run specific test (e.g., tests.unit.test_validation.TestValidateFilename)'
    )
    parser.add_argument(
        '--verbose', '-v', 
        action='count', 
        default=2,
        help='Increase verbosity'
    )
    parser.add_argument(
        '--quiet', '-q', 
        action='store_true',
        help='Minimal output'
    )
    
    args = parser.parse_args()
    
    if args.quiet:
        verbosity = 0
    else:
        verbosity = args.verbose
    
    success = True
    
    if args.test:
        # Run specific test
        run_specific_test(args.test)
    elif args.unit:
        # Run unit tests only
        success = run_all_tests(verbosity)
    elif args.integration:
        # Run integration tests only
        success = run_integration_tests(verbosity)
    else:
        # Run all tests
        unit_success = run_all_tests(verbosity)
        print("\n" + "=" * 70)
        integration_success = run_integration_tests(verbosity)
        success = unit_success and integration_success
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
