#!/usr/bin/env python3
"""
E2E Test: Kroger Milk and Bananas Price Check at 40205
Tests runner.py with a real-world grocery price checking task
"""

import asyncio
import os
import sys
import time
import json
from pathlib import Path
from dotenv import load_dotenv

# Add the browser-use directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from runner import main as runner_main

class E2ETestResult:
    def __init__(self):
        self.start_time = time.time()
        self.end_time = None
        self.success = False
        self.error = None
        self.output = ""
        self.grade = "F"
        self.commentary = ""
        self.metrics = {}

async def test_kroger_prices():
    """Test runner.py with Kroger milk and bananas price checking task"""
    
    # Load environment
    load_dotenv()
    
    # Test configuration
    test_goal = "Check the current prices of milk and bananas at Kroger store in zip code 40205. Find the specific store location and get the current pricing for these two items."
    
    result = E2ETestResult()
    
    print("=" * 80)
    print("E2E TEST: Kroger Milk & Bananas Price Check (40205)")
    print("=" * 80)
    print(f"GOAL: {test_goal}")
    print(f"START TIME: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Capture stdout to analyze results
    import io
    from contextlib import redirect_stdout, redirect_stderr
    
    captured_output = io.StringIO()
    captured_error = io.StringIO()
    
    try:
        # Run the main runner with our test goal
        with redirect_stdout(captured_output), redirect_stderr(captured_error):
            await runner_main(test_goal)
        
        result.success = True
        result.output = captured_output.getvalue()
        error_output = captured_error.getvalue()
        
        if error_output:
            result.output += f"\n[STDERR]\n{error_output}"
            
    except Exception as e:
        result.success = False
        result.error = str(e)
        result.output = captured_output.getvalue()
        error_output = captured_error.getvalue()
        
        if error_output:
            result.output += f"\n[STDERR]\n{error_output}"
        
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    result.end_time = time.time()
    result.metrics['duration'] = result.end_time - result.start_time
    
    # Analyze results and assign grade
    result.grade, result.commentary = analyze_test_results(result)
    
    return result

def analyze_test_results(result: E2ETestResult) -> tuple[str, str]:
    """Analyze test results and provide grade with commentary"""
    
    output = result.output.lower()
    duration = result.metrics.get('duration', 0)
    
    # Scoring criteria
    score = 0
    max_score = 100
    commentary_points = []
    
    # Basic execution (20 points)
    if result.success:
        score += 20
        commentary_points.append("✅ Task completed without fatal errors (+20)")
    else:
        commentary_points.append(f"❌ Task failed with error: {result.error} (0)")
    
    # Browser automation (15 points)
    if "browser" in output and ("start" in output or "navigation" in output):
        score += 15
        commentary_points.append("✅ Browser automation initiated (+15)")
    else:
        commentary_points.append("❌ No evidence of browser automation (0)")
    
    # Local LLM usage (15 points)
    if "local" in output and ("llm" in output or "llamacpp" in output):
        score += 15
        commentary_points.append("✅ Local LLM utilized (+15)")
    else:
        commentary_points.append("❌ Local LLM not detected (0)")
    
    # Planning phase (10 points)
    if "planner" in output or "subtask" in output:
        score += 10
        commentary_points.append("✅ Planning phase executed (+10)")
    else:
        commentary_points.append("❌ No planning phase detected (0)")
    
    # Kroger-specific navigation (15 points)
    if "kroger" in output:
        score += 15
        commentary_points.append("✅ Kroger website accessed (+15)")
    else:
        commentary_points.append("❌ No Kroger website interaction detected (0)")
    
    # Location targeting (10 points)
    if "40205" in output or "zip" in output or "location" in output:
        score += 10
        commentary_points.append("✅ Location targeting attempted (+10)")
    else:
        commentary_points.append("❌ No location targeting detected (0)")
    
    # Product search (10 points)
    if ("milk" in output and "banana" in output) or "price" in output:
        score += 10
        commentary_points.append("✅ Product search attempted (+10)")
    else:
        commentary_points.append("❌ No product search detected (0)")
    
    # Performance (5 points)
    if duration < 300:  # Under 5 minutes
        score += 5
        commentary_points.append(f"✅ Good performance: {duration:.1f}s (+5)")
    elif duration < 600:  # Under 10 minutes
        score += 3
        commentary_points.append(f"⚠️ Acceptable performance: {duration:.1f}s (+3)")
    else:
        commentary_points.append(f"❌ Slow performance: {duration:.1f}s (0)")
    
    # Error handling and recovery
    if "recovery" in output or "retry" in output:
        commentary_points.append("✅ Error recovery mechanisms active")
    
    # Hybrid LLM usage
    if "cloud" in output and "local" in output:
        commentary_points.append("✅ Hybrid local/cloud LLM strategy detected")
    
    # Grade assignment
    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B"
    elif score >= 70:
        grade = "C"
    elif score >= 60:
        grade = "D"
    else:
        grade = "F"
    
    # Build commentary
    commentary = f"SCORE: {score}/{max_score} ({score/max_score*100:.1f}%)\n"
    commentary += f"DURATION: {duration:.1f} seconds\n\n"
    commentary += "DETAILED ANALYSIS:\n"
    commentary += "\n".join(commentary_points)
    
    # Additional insights
    commentary += "\n\nKEY INSIGHTS:\n"
    
    if result.success:
        commentary += "• Task execution completed successfully\n"
    else:
        commentary += "• Task execution encountered fatal errors\n"
    
    if "502" in output or "timeout" in output:
        commentary += "• Network/timeout issues detected - may need optimization\n"
    
    if "unicode" in output or "encoding" in output:
        commentary += "• Unicode/encoding issues detected - Windows compatibility concern\n"
    
    if duration > 600:
        commentary += "• Performance optimization needed for production use\n"
    
    return grade, commentary

def print_test_report(result: E2ETestResult):
    """Print comprehensive test report"""
    
    print("\n" + "=" * 80)
    print("E2E TEST REPORT")
    print("=" * 80)
    
    print(f"GRADE: {result.grade}")
    print(f"SUCCESS: {result.success}")
    print(f"DURATION: {result.metrics.get('duration', 0):.1f} seconds")
    
    if result.error:
        print(f"ERROR: {result.error}")
    
    print("\nCOMMENTARY:")
    print(result.commentary)
    
    print("\nFULL OUTPUT:")
    print("-" * 40)
    print(result.output)
    print("-" * 40)
    
    # Save detailed results to file
    report_file = Path(__file__).parent / "test_results_kroger_e2e.json"
    report_data = {
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "grade": result.grade,
        "success": result.success,
        "duration": result.metrics.get('duration', 0),
        "error": result.error,
        "commentary": result.commentary,
        "output": result.output
    }
    
    with open(report_file, 'w') as f:
        json.dump(report_data, f, indent=2)
    
    print(f"\nDetailed results saved to: {report_file}")

async def main():
    """Main test execution"""
    
    print("Kroger E2E Test Starting...")
    print("This test will evaluate runner.py with a real-world grocery price checking task")
    print()
    
    # Check prerequisites
    print("PREREQUISITES CHECK:")
    
    # Check if llama.cpp server is running
    try:
        import httpx
        response = httpx.get("http://localhost:8080/health", timeout=5)
        if response.status_code == 200:
            print("✅ llama.cpp server is running")
        else:
            print(f"⚠️ llama.cpp server responded with status {response.status_code}")
    except Exception as e:
        print(f"❌ llama.cpp server not accessible: {e}")
        print("   Please start with: start-llama-server.bat")
    
    # Check environment variables
    required_env = ["OPENAI_API_KEY", "SERPER_API_KEY"]
    for env_var in required_env:
        if os.getenv(env_var):
            print(f"✅ {env_var} is set")
        else:
            print(f"❌ {env_var} is not set")
    
    print()
    
    # Run the test
    result = await test_kroger_prices()
    
    # Print comprehensive report
    print_test_report(result)
    
    return result.grade, result.success

if __name__ == "__main__":
    grade, success = asyncio.run(main())
    print(f"\nFINAL RESULT: Grade {grade} - {'PASS' if success else 'FAIL'}")
    sys.exit(0 if success else 1)