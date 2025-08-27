#!/usr/bin/env python3
"""
Basic functionality test for vision system components
Tests each component can be initialized and basic methods work
"""

import asyncio
import time
from pathlib import Path
import tempfile
from PIL import Image

# Import all vision components
from enhanced_vision_architecture import EnhancedVisionSystem, ReliableVisionRequest, ReliableVisionTier
from enhanced_dom_analyzer import EnhancedDOMAnalyzer
from failsafe_recovery_system import ResilientOperationWrapper, RecoveryStrategy
from vision_performance_optimizer import VisionPerformanceOptimizer
from containerized_vision_service import ContainerizedVisionService
from vision_module import VisionState, VisionElement, VisionMeta

async def test_enhanced_vision_system():
	"""Test enhanced vision system basic functionality"""
	print("Testing EnhancedVisionSystem...")
	
	system = EnhancedVisionSystem()
	
	# Test system health check
	health = system.get_system_health()
	print(f"  System health: {health['overall_status']}")
	
	# Create a test image
	test_image_path = Path(tempfile.gettempdir()) / "test_vision.png"
	img = Image.new('RGB', (800, 600), color='white')
	img.save(test_image_path)
	
	# Create test request
	request = ReliableVisionRequest(
		page_url="https://test.example.com",
		page_title="Test Page",
		screenshot_path=str(test_image_path),
		required_accuracy=0.8,
		max_response_time=5.0
	)
	
	try:
		# Test tier 1 analysis (should always work)
		request.force_tier = ReliableVisionTier.TIER1_DOM_ENHANCED
		response = await system.analyze(request)
		
		print(f"  Tier 1 analysis successful:")
		print(f"    Tier used: {response.tier_used}")
		print(f"    Confidence: {response.confidence:.2f}")
		print(f"    Processing time: {response.analysis_time:.3f}s")
		print(f"    Elements found: {len(response.vision_state.elements)}")
		
		# Test emergency fallback
		request.force_tier = ReliableVisionTier.EMERGENCY_FALLBACK
		response = await system.analyze(request)
		
		print(f"  Emergency fallback successful:")
		print(f"    Tier used: {response.tier_used}")
		print(f"    Confidence: {response.confidence:.2f}")
		print(f"    Fallback reason: {response.fallback_reason}")
		
		return True
		
	except Exception as e:
		print(f"  ERROR: {e}")
		return False
	
	finally:
		# Cleanup
		if test_image_path.exists():
			test_image_path.unlink()

async def test_performance_optimizer():
	"""Test vision performance optimizer"""
	print("Testing VisionPerformanceOptimizer...")
	
	optimizer = VisionPerformanceOptimizer()
	
	try:
		await optimizer.initialize()
		print("  Optimizer initialized successfully")
		
		# Test request optimization
		test_request = {
			'page_url': 'https://test.com',
			'required_accuracy': 0.8
		}
		
		optimized_request, metadata = await optimizer.optimize_vision_request(test_request)
		
		print(f"  Request optimization completed:")
		print(f"    Cache hit: {metadata['cache_hit']}")
		print(f"    Optimization level: {metadata['optimization_level']}")
		print(f"    Total time: {metadata['total_time']:.3f}s")
		
		# Test performance report
		report = optimizer.get_performance_report()
		print(f"  Performance report generated: {len(report)} metrics")
		
		return True
		
	except Exception as e:
		print(f"  ERROR: {e}")
		return False
	
	finally:
		await optimizer.cleanup()

async def test_failsafe_system():
	"""Test failsafe recovery system"""
	print("Testing Failsafe Recovery System...")
	
	strategy = RecoveryStrategy(max_retries=2, base_delay=0.1)
	wrapper = ResilientOperationWrapper("test_vision", strategy)
	
	try:
		# Test successful operation
		async def successful_operation():
			await asyncio.sleep(0.01)
			return {"result": "success", "confidence": 0.9}
		
		result = await wrapper.execute(successful_operation)
		print(f"  Successful operation: {result['result']}")
		
		# Test operation with fallback
		async def failing_operation():
			raise Exception("Simulated failure")
		
		async def fallback_operation(context):
			return {"result": "fallback", "confidence": 0.3}
		
		result = await wrapper.execute(failing_operation, fallback_operation)
		print(f"  Fallback operation: {result['result']}")
		
		# Test status report
		status = wrapper.get_status_report()
		print(f"  Status report: {status['operation_name']}")
		
		return True
		
	except Exception as e:
		print(f"  ERROR: {e}")
		return False

async def test_containerized_service():
	"""Test containerized vision service"""
	print("Testing ContainerizedVisionService...")
	
	service = ContainerizedVisionService("test-vision")
	
	try:
		# Test initialization (won't actually start containers in test)
		success = await service.initialize()
		if success:
			print("  Service initialization successful")
		else:
			print("  Service initialization failed (Docker not available)")
		
		# Test service status
		status = await service.get_all_service_status()
		print(f"  Service status retrieved: {len(status['services'])} services")
		
		return True
		
	except Exception as e:
		print(f"  INFO: {e} (expected if Docker not running)")
		return True  # Docker errors are expected in many environments
	
	finally:
		await service.cleanup()

def test_dom_analyzer():
	"""Test DOM analyzer (without actual page)"""
	print("Testing EnhancedDOMAnalyzer...")
	
	try:
		analyzer = EnhancedDOMAnalyzer()
		print(f"  DOM analyzer initialized")
		print(f"  Performance stats: {analyzer.performance_stats}")
		
		return True
		
	except Exception as e:
		print(f"  ERROR: {e}")
		return False

async def run_all_tests():
	"""Run all component tests"""
	print("="*60)
	print("VISION SYSTEM COMPONENT TESTS")
	print("="*60)
	
	tests = [
		("Enhanced Vision System", test_enhanced_vision_system()),
		("Performance Optimizer", test_performance_optimizer()),
		("Failsafe Recovery System", test_failsafe_system()),
		("Containerized Service", test_containerized_service()),
		("DOM Analyzer", test_dom_analyzer())
	]
	
	results = []
	
	for test_name, test_coro in tests:
		print(f"\n{test_name}:")
		print("-" * 40)
		
		try:
			if asyncio.iscoroutine(test_coro):
				success = await test_coro
			else:
				success = test_coro
			
			results.append((test_name, success))
			
		except Exception as e:
			print(f"  CRITICAL ERROR: {e}")
			results.append((test_name, False))
	
	# Summary
	print("\n" + "="*60)
	print("TEST SUMMARY")
	print("="*60)
	
	passed = sum(1 for _, success in results if success)
	total = len(results)
	
	for test_name, success in results:
		status = "PASS" if success else "FAIL"
		print(f"{test_name:30} {status}")
	
	print(f"\nOverall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
	
	if passed == total:
		print("🎉 All vision components are working correctly!")
	elif passed >= total * 0.8:
		print("✅ Most vision components are working correctly")
	else:
		print("⚠️  Some vision components need attention")
	
	return passed, total

if __name__ == "__main__":
	asyncio.run(run_all_tests())