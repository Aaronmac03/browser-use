#!/usr/bin/env python3
"""
Quick E2E Test for Browser-Use Performance Assessment
====================================================

Focused test to identify and grade current performance issues.
"""

import asyncio
import sys
import time
import traceback
from pathlib import Path
from dotenv import load_dotenv

# Add browser-use to path
sys.path.insert(0, str(Path(__file__).parent))

def log(message: str):
    """Log with timestamp."""
    print(f"[{time.strftime('%H:%M:%S')}] {message}")

class QuickE2ETest:
    """Quick end-to-end test for performance assessment."""
    
    def __init__(self):
        self.results = {}
        self.start_time = time.time()
    
    async def test_basic_navigation(self) -> dict:
        """Test basic navigation to a simple website."""
        log("Testing basic navigation...")
        
        test_start = time.time()
        try:
            from runner import main as runner_main
            
            # Simple navigation test
            goal = "Navigate to httpbin.org/html and tell me what you see"
            
            await asyncio.wait_for(runner_main(goal), timeout=120)
            
            duration = time.time() - test_start
            log(f"Basic navigation completed in {duration:.1f}s")
            
            return {
                'status': 'PASS',
                'duration': duration,
                'error': None
            }
            
        except asyncio.TimeoutError:
            duration = time.time() - test_start
            log(f"Basic navigation timed out after 120s")
            return {
                'status': 'TIMEOUT',
                'duration': duration,
                'error': 'Timeout after 120s'
            }
            
        except Exception as e:
            duration = time.time() - test_start
            log(f"Basic navigation failed: {e}")
            return {
                'status': 'FAIL',
                'duration': duration,
                'error': str(e),
                'traceback': traceback.format_exc()
            }
    
    async def test_llm_connectivity(self) -> dict:
        """Test LLM connectivity and response."""
        log("Testing LLM connectivity...")
        
        test_start = time.time()
        try:
            from runner import make_local_llm
            from browser_use.llm.messages import UserMessage
            
            llm = make_local_llm()
            
            # Simple test prompt with proper message format
            messages = [UserMessage(content="What is 2+2? Answer with just the number.")]
            response = await llm.ainvoke(messages)
            
            duration = time.time() - test_start
            log(f"LLM responded in {duration:.1f}s: {response.completion[:50]}...")
            
            return {
                'status': 'PASS',
                'duration': duration,
                'response_length': len(str(response.completion)),
                'error': None
            }
            
        except Exception as e:
            duration = time.time() - test_start
            log(f"LLM connectivity failed: {e}")
            return {
                'status': 'FAIL',
                'duration': duration,
                'error': str(e),
                'traceback': traceback.format_exc()
            }
    
    async def test_browser_startup(self) -> dict:
        """Test browser startup and CDP connection."""
        log("Testing browser startup...")
        
        test_start = time.time()
        try:
            from runner import make_browser
            
            browser = make_browser()
            
            # Test browser start
            await browser.start()
            
            # Test basic browser state
            from browser_use.browser.events import BrowserStateRequestEvent
            state_event = browser.event_bus.dispatch(BrowserStateRequestEvent())
            state = await asyncio.wait_for(state_event, timeout=10)
            
            await browser.stop()
            
            duration = time.time() - test_start
            log(f"Browser startup completed in {duration:.1f}s")
            
            return {
                'status': 'PASS',
                'duration': duration,
                'has_state': state is not None,
                'error': None
            }
            
        except Exception as e:
            duration = time.time() - test_start
            log(f"Browser startup failed: {e}")
            return {
                'status': 'FAIL',
                'duration': duration,
                'error': str(e),
                'traceback': traceback.format_exc()
            }
    
    async def test_cloud_planning(self) -> dict:
        """Test cloud LLM planning functionality."""
        log("Testing cloud planning...")
        
        test_start = time.time()
        try:
            from runner import plan_with_o3_then_gemini
            
            goal = "Find the weather in New York"
            subtasks = await plan_with_o3_then_gemini(goal)
            
            duration = time.time() - test_start
            log(f"Cloud planning completed in {duration:.1f}s, generated {len(subtasks)} subtasks")
            
            return {
                'status': 'PASS',
                'duration': duration,
                'subtask_count': len(subtasks),
                'error': None
            }
            
        except Exception as e:
            duration = time.time() - test_start
            log(f"Cloud planning failed: {e}")
            return {
                'status': 'FAIL',
                'duration': duration,
                'error': str(e),
                'traceback': traceback.format_exc()
            }
    
    async def run_all_tests(self) -> dict:
        """Run all quick tests and return results."""
        log("Starting Quick E2E Performance Test")
        log("=" * 50)
        
        tests = [
            ('LLM Connectivity', self.test_llm_connectivity),
            ('Cloud Planning', self.test_cloud_planning),
            ('Browser Startup', self.test_browser_startup),
            ('Basic Navigation', self.test_basic_navigation),
        ]
        
        results = {}
        passed_tests = 0
        
        for test_name, test_func in tests:
            log(f"Running {test_name}...")
            result = await test_func()
            results[test_name] = result
            
            if result['status'] == 'PASS':
                passed_tests += 1
            
            log("")  # Add spacing
        
        # Calculate overall metrics
        total_tests = len(tests)
        success_rate = passed_tests / total_tests
        total_duration = time.time() - self.start_time
        
        overall_result = {
            'success_rate': success_rate,
            'passed_tests': passed_tests,
            'total_tests': total_tests,
            'total_duration': total_duration,
            'individual_results': results
        }
        
        # Generate performance grade
        if success_rate >= 0.75:
            grade = "A" if success_rate >= 0.9 else "B"
            status = "GOOD"
        elif success_rate >= 0.5:
            grade = "C"
            status = "NEEDS IMPROVEMENT"
        else:
            grade = "D"
            status = "POOR"
        
        overall_result['grade'] = grade
        overall_result['status'] = status
        
        return overall_result

def print_results(results: dict):
    """Print formatted test results."""
    print("=" * 60)
    print("QUICK E2E TEST RESULTS")
    print("=" * 60)
    
    # Individual test results
    for test_name, result in results['individual_results'].items():
        status = result['status']
        duration = result.get('duration', 0)
        
        if status == 'PASS':
            print(f"[PASS] {test_name}: PASSED ({duration:.1f}s)")
        elif status == 'TIMEOUT':
            print(f"[TIMEOUT] {test_name}: TIMEOUT ({duration:.1f}s)")
        else:
            print(f"[FAIL] {test_name}: FAILED ({duration:.1f}s)")
            if 'error' in result:
                print(f"   Error: {result['error']}")
    
    print()
    print("=" * 60)
    print("OVERALL ASSESSMENT")
    print("=" * 60)
    
    print(f"Grade: {results['grade']}")
    print(f"Status: {results['status']}")
    print(f"Success Rate: {results['success_rate']:.1%} ({results['passed_tests']}/{results['total_tests']})")
    print(f"Total Duration: {results['total_duration']:.1f}s")
    
    # Performance analysis
    print()
    print("PERFORMANCE ANALYSIS:")
    
    if results['grade'] in ['A', 'B']:
        print("[OK] System is performing well")
        print("[OK] Ready for production use")
    elif results['grade'] == 'C':
        print("[WARN] System has some issues but is functional")
        print("[INFO] Optimization recommended")
    else:
        print("[ERROR] System has significant issues")
        print("[CRITICAL] Major fixes required")
    
    # Identify specific issues
    failed_tests = [name for name, result in results['individual_results'].items() 
                   if result['status'] != 'PASS']
    
    if failed_tests:
        print()
        print("FAILED COMPONENTS:")
        for test_name in failed_tests:
            result = results['individual_results'][test_name]
            print(f"[FAIL] {test_name}: {result.get('error', 'Unknown error')}")

async def main():
    """Run quick E2E test."""
    load_dotenv()
    
    tester = QuickE2ETest()
    results = await tester.run_all_tests()
    
    print_results(results)
    
    # Return success/failure for exit code
    return results['success_rate'] >= 0.5

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n[INTERRUPT] Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Test failed with exception: {e}")
        traceback.print_exc()
        sys.exit(1)