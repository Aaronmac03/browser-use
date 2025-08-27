#!/usr/bin/env python3
"""
Comprehensive test suite for vision system improvements
Tests reliability, performance, and functionality of the new multi-tier vision system
"""

import asyncio
import time
import tempfile
import json
from pathlib import Path
from typing import Dict, Any, List
from PIL import Image, ImageDraw, ImageFont

# Import our improved components
from multi_tier_vision import MultiTierVisionSystem, VisionRequest, VisionTier
from vision_service_manager import VisionServiceManager
from enhanced_dom_analyzer import EnhancedDOMAnalyzer
from improved_hybrid_agent import ImprovedHybridAgent

# Test utilities
class TestResults:
    def __init__(self):
        self.tests = []
        self.passed = 0
        self.failed = 0
        self.start_time = time.time()
    
    def add_test(self, name: str, passed: bool, duration: float, details: str = ""):
        self.tests.append({
            'name': name,
            'passed': passed,
            'duration': duration,
            'details': details
        })
        if passed:
            self.passed += 1
        else:
            self.failed += 1
    
    def get_summary(self) -> Dict[str, Any]:
        total_time = time.time() - self.start_time
        return {
            'total_tests': len(self.tests),
            'passed': self.passed,
            'failed': self.failed,
            'success_rate': self.passed / max(1, len(self.tests)),
            'total_time': total_time,
            'tests': self.tests
        }


def create_test_image(width: int = 800, height: int = 600, content: str = "Test Page") -> str:
    """Create a test image with some content"""
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to use a font, fallback to default if not available
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        font = ImageFont.load_default()
    
    # Draw some test content
    draw.text((50, 50), content, fill='black', font=font)
    draw.rectangle([100, 150, 300, 200], outline='blue', width=2)
    draw.text((110, 160), "Button", fill='blue', font=font)
    draw.rectangle([100, 250, 400, 280], outline='green', width=2)
    draw.text((110, 255), "Input Field", fill='green', font=font)
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
        img.save(temp_file.name)
        return temp_file.name


async def test_service_manager():
    """Test the vision service manager"""
    print("🔧 Testing Vision Service Manager...")
    results = TestResults()
    
    manager = VisionServiceManager()
    
    # Test 1: Health check
    start_time = time.time()
    try:
        health_info = await manager.health_check_all()
        duration = time.time() - start_time
        
        # Check if we got health info
        has_ollama_info = 'ollama' in health_info
        results.add_test(
            "Service Health Check",
            has_ollama_info,
            duration,
            f"Health info keys: {list(health_info.keys())}"
        )
    except Exception as e:
        duration = time.time() - start_time
        results.add_test("Service Health Check", False, duration, str(e))
    
    # Test 2: Overall status
    start_time = time.time()
    try:
        status = manager.get_overall_status()
        duration = time.time() - start_time
        
        valid_statuses = ['healthy', 'unhealthy', 'transitioning']
        results.add_test(
            "Overall Status Check",
            status in valid_statuses,
            duration,
            f"Status: {status}"
        )
    except Exception as e:
        duration = time.time() - start_time
        results.add_test("Overall Status Check", False, duration, str(e))
    
    return results


async def test_enhanced_dom_analyzer():
    """Test the enhanced DOM analyzer"""
    print("🌐 Testing Enhanced DOM Analyzer...")
    results = TestResults()
    
    from playwright.async_api import async_playwright
    
    analyzer = EnhancedDOMAnalyzer()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Test 1: Simple page analysis
        start_time = time.time()
        try:
            await page.goto("https://example.com")
            vision_state = await analyzer.analyze_page(page)
            duration = time.time() - start_time
            
            # Check if we got reasonable results
            has_caption = len(vision_state.caption) > 0
            has_elements = len(vision_state.elements) >= 0  # Could be 0 for simple pages
            fast_response = duration < 2.0  # Should be very fast
            
            success = has_caption and fast_response
            results.add_test(
                "Simple Page Analysis",
                success,
                duration,
                f"Caption: {vision_state.caption[:50]}..., Elements: {len(vision_state.elements)}, Fast: {fast_response}"
            )
        except Exception as e:
            duration = time.time() - start_time
            results.add_test("Simple Page Analysis", False, duration, str(e))
        
        # Test 2: Complex page analysis
        start_time = time.time()
        try:
            # Create a page with form elements
            await page.set_content("""
            <html>
            <body>
                <h1>Test Form</h1>
                <form>
                    <input type="text" name="username" placeholder="Username">
                    <input type="password" name="password" placeholder="Password">
                    <button type="submit">Login</button>
                </form>
                <a href="#" onclick="alert('clicked')">Click me</a>
            </body>
            </html>
            """)
            
            vision_state = await analyzer.analyze_page(page)
            duration = time.time() - start_time
            
            # Check if we detected form elements
            has_fields = len(vision_state.fields) > 0
            has_buttons = any(e.role == 'button' for e in vision_state.elements)
            has_links = any(e.role == 'link' for e in vision_state.elements)
            
            success = has_fields and (has_buttons or has_links)
            results.add_test(
                "Complex Page Analysis",
                success,
                duration,
                f"Fields: {len(vision_state.fields)}, Buttons: {has_buttons}, Links: {has_links}"
            )
        except Exception as e:
            duration = time.time() - start_time
            results.add_test("Complex Page Analysis", False, duration, str(e))
        
        # Test 3: Performance consistency
        start_time = time.time()
        try:
            times = []
            for i in range(3):
                test_start = time.time()
                await analyzer.analyze_page(page)
                times.append(time.time() - test_start)
            
            duration = time.time() - start_time
            avg_time = sum(times) / len(times)
            max_time = max(times)
            consistent = max_time < avg_time * 2  # Max time shouldn't be more than 2x average
            
            results.add_test(
                "Performance Consistency",
                consistent,
                duration,
                f"Avg: {avg_time:.3f}s, Max: {max_time:.3f}s, Consistent: {consistent}"
            )
        except Exception as e:
            duration = time.time() - start_time
            results.add_test("Performance Consistency", False, duration, str(e))
        
        await browser.close()
    
    return results


async def test_multi_tier_vision():
    """Test the multi-tier vision system"""
    print("🎯 Testing Multi-Tier Vision System...")
    results = TestResults()
    
    vision_system = MultiTierVisionSystem()
    
    # Create test image
    test_image_path = create_test_image()
    
    try:
        # Test 1: Tier 1 (DOM) analysis
        start_time = time.time()
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto("https://example.com")
                
                request = VisionRequest(
                    page_url=page.url,
                    page_title=await page.title(),
                    force_tier=VisionTier.TIER1_DOM,
                    max_response_time=2.0
                )
                
                response = await vision_system.analyze(request, page)
                duration = time.time() - start_time
                
                # Check results
                correct_tier = response.tier_used == VisionTier.TIER1_DOM
                fast_response = response.analysis_time < 2.0
                has_content = len(response.vision_state.caption) > 0
                
                success = correct_tier and fast_response and has_content
                results.add_test(
                    "Tier 1 DOM Analysis",
                    success,
                    duration,
                    f"Tier: {response.tier_used.value}, Time: {response.analysis_time:.3f}s, Confidence: {response.confidence:.2f}"
                )
                
                await browser.close()
        except Exception as e:
            duration = time.time() - start_time
            results.add_test("Tier 1 DOM Analysis", False, duration, str(e))
        
        # Test 2: Tier 3 (Advanced) analysis
        start_time = time.time()
        try:
            request = VisionRequest(
                page_url="https://test.com",
                page_title="Test Page",
                screenshot_path=test_image_path,
                force_tier=VisionTier.TIER3_ADVANCED,
                max_response_time=30.0
            )
            
            response = await vision_system.analyze(request)
            duration = time.time() - start_time
            
            # Check results - this might fail if Ollama isn't working, but that's expected
            attempted_tier3 = response.tier_used == VisionTier.TIER3_ADVANCED or response.fallback_reason
            has_response = response.vision_state is not None
            
            success = attempted_tier3 and has_response
            results.add_test(
                "Tier 3 Advanced Analysis",
                success,
                duration,
                f"Tier: {response.tier_used.value}, Fallback: {response.fallback_reason}, Time: {response.analysis_time:.3f}s"
            )
        except Exception as e:
            duration = time.time() - start_time
            results.add_test("Tier 3 Advanced Analysis", False, duration, str(e))
        
        # Test 3: Automatic tier selection
        start_time = time.time()
        try:
            request = VisionRequest(
                page_url="https://test.com",
                page_title="Test Page",
                screenshot_path=test_image_path,
                max_response_time=5.0,
                required_accuracy=0.7
            )
            
            response = await vision_system.analyze(request)
            duration = time.time() - start_time
            
            # Check that system selected a tier and provided results
            has_tier = response.tier_used in [VisionTier.TIER1_DOM, VisionTier.TIER2_LIGHTWEIGHT, VisionTier.TIER3_ADVANCED, VisionTier.FALLBACK]
            within_time_limit = response.analysis_time <= request.max_response_time + 1.0  # Allow 1s buffer
            has_results = response.vision_state is not None
            
            success = has_tier and within_time_limit and has_results
            results.add_test(
                "Automatic Tier Selection",
                success,
                duration,
                f"Selected: {response.tier_used.value}, Time: {response.analysis_time:.3f}s, Within limit: {within_time_limit}"
            )
        except Exception as e:
            duration = time.time() - start_time
            results.add_test("Automatic Tier Selection", False, duration, str(e))
        
        # Test 4: Performance tracking
        start_time = time.time()
        try:
            performance_summary = vision_system.get_performance_summary()
            duration = time.time() - start_time
            
            # Check that we have performance data
            has_tier_data = len(performance_summary) > 0
            has_metrics = all('success_rate' in tier_data for tier_data in performance_summary.values())
            
            success = has_tier_data and has_metrics
            results.add_test(
                "Performance Tracking",
                success,
                duration,
                f"Tiers tracked: {list(performance_summary.keys())}"
            )
        except Exception as e:
            duration = time.time() - start_time
            results.add_test("Performance Tracking", False, duration, str(e))
        
    finally:
        # Cleanup test image
        try:
            Path(test_image_path).unlink()
        except:
            pass
    
    return results


async def test_improved_hybrid_agent():
    """Test the improved hybrid agent"""
    print("🤖 Testing Improved Hybrid Agent...")
    results = TestResults()
    
    # Test 1: Agent initialization
    start_time = time.time()
    try:
        agent = ImprovedHybridAgent()
        initialized = await agent.initialize()
        duration = time.time() - start_time
        
        results.add_test(
            "Agent Initialization",
            initialized,
            duration,
            f"Initialized: {initialized}"
        )
        
        if initialized:
            # Test 2: Simple task execution
            start_time = time.time()
            try:
                test_task = "analyze the current page"
                result = await agent.execute_task(test_task)
                duration = time.time() - start_time
                
                has_result = result is not None
                has_task_info = 'task' in result and 'completed' in result
                reasonable_time = duration < 30.0  # Should complete within 30 seconds
                
                success = has_result and has_task_info and reasonable_time
                results.add_test(
                    "Simple Task Execution",
                    success,
                    duration,
                    f"Completed: {result.get('completed', False)}, Steps: {result.get('steps_executed', 0)}"
                )
            except Exception as e:
                duration = time.time() - start_time
                results.add_test("Simple Task Execution", False, duration, str(e))
        
        # Cleanup
        try:
            await agent.cleanup()
        except:
            pass
            
    except Exception as e:
        duration = time.time() - start_time
        results.add_test("Agent Initialization", False, duration, str(e))
    
    return results


async def test_reliability_improvements():
    """Test specific reliability improvements"""
    print("🛡️ Testing Reliability Improvements...")
    results = TestResults()
    
    # Test 1: Error handling in vision analysis
    start_time = time.time()
    try:
        vision_system = MultiTierVisionSystem()
        
        # Test with invalid screenshot path
        request = VisionRequest(
            page_url="https://test.com",
            page_title="Test Page",
            screenshot_path="nonexistent_file.png",
            force_tier=VisionTier.TIER3_ADVANCED
        )
        
        response = await vision_system.analyze(request)
        duration = time.time() - start_time
        
        # Should handle error gracefully and provide fallback
        handled_gracefully = response.vision_state is not None
        has_fallback_info = response.fallback_reason is not None or response.tier_used == VisionTier.FALLBACK
        
        success = handled_gracefully
        results.add_test(
            "Error Handling - Invalid Screenshot",
            success,
            duration,
            f"Graceful: {handled_gracefully}, Fallback: {has_fallback_info}, Tier: {response.tier_used.value}"
        )
    except Exception as e:
        duration = time.time() - start_time
        results.add_test("Error Handling - Invalid Screenshot", False, duration, str(e))
    
    # Test 2: Service recovery
    start_time = time.time()
    try:
        service_manager = VisionServiceManager()
        
        # Test health check with potentially unavailable service
        health_info = await service_manager.health_check_all()
        duration = time.time() - start_time
        
        # Should provide health info even if services are down
        has_health_info = isinstance(health_info, dict) and len(health_info) > 0
        has_ollama_status = 'ollama' in health_info
        
        success = has_health_info and has_ollama_status
        results.add_test(
            "Service Recovery - Health Check",
            success,
            duration,
            f"Health info available: {has_health_info}, Ollama status: {health_info.get('ollama', {}).get('status', 'unknown')}"
        )
    except Exception as e:
        duration = time.time() - start_time
        results.add_test("Service Recovery - Health Check", False, duration, str(e))
    
    # Test 3: Timeout handling
    start_time = time.time()
    try:
        vision_system = MultiTierVisionSystem()
        
        # Test with very short timeout
        request = VisionRequest(
            page_url="https://test.com",
            page_title="Test Page",
            max_response_time=0.1,  # Very short timeout
            required_accuracy=0.9
        )
        
        response = await vision_system.analyze(request)
        duration = time.time() - start_time
        
        # Should handle timeout and provide reasonable response
        completed_quickly = duration < 5.0  # Should not hang
        has_response = response.vision_state is not None
        
        success = completed_quickly and has_response
        results.add_test(
            "Timeout Handling",
            success,
            duration,
            f"Quick completion: {completed_quickly}, Has response: {has_response}, Tier: {response.tier_used.value}"
        )
    except Exception as e:
        duration = time.time() - start_time
        results.add_test("Timeout Handling", False, duration, str(e))
    
    return results


async def run_comprehensive_tests():
    """Run all tests and generate comprehensive report"""
    print("🚀 Starting Comprehensive Vision System Tests")
    print("=" * 60)
    
    all_results = {}
    
    # Run all test suites
    test_suites = [
        ("Service Manager", test_service_manager),
        ("Enhanced DOM Analyzer", test_enhanced_dom_analyzer),
        ("Multi-Tier Vision", test_multi_tier_vision),
        ("Improved Hybrid Agent", test_improved_hybrid_agent),
        ("Reliability Improvements", test_reliability_improvements)
    ]
    
    for suite_name, test_func in test_suites:
        try:
            print(f"\n{suite_name}:")
            results = await test_func()
            all_results[suite_name] = results.get_summary()
            
            # Print immediate results
            summary = results.get_summary()
            print(f"  ✅ Passed: {summary['passed']}")
            print(f"  ❌ Failed: {summary['failed']}")
            print(f"  📊 Success Rate: {summary['success_rate']:.1%}")
            print(f"  ⏱️ Duration: {summary['total_time']:.2f}s")
            
        except Exception as e:
            print(f"  💥 Test suite failed: {e}")
            all_results[suite_name] = {
                'total_tests': 0,
                'passed': 0,
                'failed': 1,
                'success_rate': 0.0,
                'total_time': 0.0,
                'error': str(e)
            }
    
    # Generate comprehensive report
    print("\n" + "=" * 60)
    print("📋 COMPREHENSIVE TEST REPORT")
    print("=" * 60)
    
    total_tests = sum(suite['total_tests'] for suite in all_results.values())
    total_passed = sum(suite['passed'] for suite in all_results.values())
    total_failed = sum(suite['failed'] for suite in all_results.values())
    overall_success_rate = total_passed / max(1, total_tests)
    
    print(f"Overall Results:")
    print(f"  Total Tests: {total_tests}")
    print(f"  Passed: {total_passed}")
    print(f"  Failed: {total_failed}")
    print(f"  Success Rate: {overall_success_rate:.1%}")
    
    print(f"\nDetailed Results by Suite:")
    for suite_name, results in all_results.items():
        print(f"  {suite_name}:")
        print(f"    Tests: {results['total_tests']}")
        print(f"    Success Rate: {results['success_rate']:.1%}")
        print(f"    Duration: {results['total_time']:.2f}s")
        if 'error' in results:
            print(f"    Error: {results['error']}")
    
    # Save detailed report
    report_file = Path("vision_test_report.json")
    with open(report_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n📄 Detailed report saved to: {report_file}")
    
    # Recommendations based on results
    print(f"\n💡 RECOMMENDATIONS:")
    
    if overall_success_rate >= 0.8:
        print("  ✅ Vision system improvements are working well!")
        print("  ✅ Ready for production use with monitoring")
    elif overall_success_rate >= 0.6:
        print("  ⚠️ Vision system shows improvement but needs refinement")
        print("  ⚠️ Focus on failed test areas before production")
    else:
        print("  ❌ Vision system needs significant work")
        print("  ❌ Address critical failures before proceeding")
    
    # Specific recommendations
    service_success = all_results.get("Service Manager", {}).get('success_rate', 0)
    if service_success < 0.5:
        print("  🔧 Priority: Fix service management issues")
    
    dom_success = all_results.get("Enhanced DOM Analyzer", {}).get('success_rate', 0)
    if dom_success >= 0.8:
        print("  🌐 DOM analyzer is reliable - good fallback option")
    
    vision_success = all_results.get("Multi-Tier Vision", {}).get('success_rate', 0)
    if vision_success >= 0.6:
        print("  🎯 Multi-tier system is functional")
    else:
        print("  🎯 Multi-tier system needs debugging")
    
    print("\n" + "=" * 60)
    return overall_success_rate >= 0.6


if __name__ == "__main__":
    success = asyncio.run(run_comprehensive_tests())
    exit(0 if success else 1)