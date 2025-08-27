"""
Comprehensive performance testing for vision system.
Tests response time consistency, memory usage, load testing, and degradation patterns.

Key Focus Areas:
- Response time consistency under various loads
- Memory usage and leak detection  
- Model degradation patterns over time
- Service restart recovery testing
- Performance benchmarking and SLA validation
"""

import asyncio
import gc
import json
import psutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import threading

import pytest
from PIL import Image

# Import vision system components
from vision_module import VisionAnalyzer, VisionState
from multi_tier_vision import MultiTierVisionSystem, VisionRequest, VisionTier
from enhanced_dom_analyzer import EnhancedDOMAnalyzer
from vision_service_manager import VisionServiceManager


@dataclass
class PerformanceMetrics:
	"""Performance metrics for a single test run"""
	test_id: str
	start_time: float
	end_time: float
	response_time: float
	memory_before_mb: float
	memory_after_mb: float
	memory_peak_mb: float
	cpu_percent: float
	success: bool
	error_message: Optional[str] = None


@dataclass
class LoadTestResult:
	"""Results from a load test"""
	test_name: str
	total_requests: int
	successful_requests: int
	failed_requests: int
	avg_response_time: float
	min_response_time: float
	max_response_time: float
	p95_response_time: float
	throughput_rps: float
	memory_growth_mb: float
	cpu_usage_percent: float
	error_rate: float
	timestamp: float


@dataclass
class DegradationTestResult:
	"""Results from degradation testing over time"""
	test_name: str
	iterations: int
	initial_response_time: float
	final_response_time: float
	degradation_factor: float
	memory_leak_detected: bool
	memory_growth_rate_mb_per_hour: float
	success_rate_degradation: float
	timestamp: float


class PerformanceProfiler:
	"""Performance profiling utilities"""
	
	def __init__(self):
		self.process = psutil.Process()
		self.baseline_memory = self.get_memory_usage()
	
	def get_memory_usage(self) -> float:
		"""Get current memory usage in MB"""
		return self.process.memory_info().rss / 1024 / 1024
	
	def get_cpu_usage(self) -> float:
		"""Get current CPU usage percentage"""
		return self.process.cpu_percent(interval=0.1)
	
	def memory_profile(self):
		"""Context manager for memory profiling"""
		class MemoryProfiler:
			def __init__(self, profiler):
				self.profiler = profiler
				self.start_memory = 0
				self.peak_memory = 0
				self.end_memory = 0
			
			def __enter__(self):
				gc.collect()  # Force garbage collection before measurement
				self.start_memory = self.profiler.get_memory_usage()
				self.peak_memory = self.start_memory
				return self
			
			def __exit__(self, exc_type, exc_val, exc_tb):
				gc.collect()  # Force garbage collection after test
				self.end_memory = self.profiler.get_memory_usage()
				self.peak_memory = max(self.peak_memory, self.end_memory)
			
			def update_peak(self):
				"""Update peak memory usage"""
				current = self.profiler.get_memory_usage()
				self.peak_memory = max(self.peak_memory, current)
		
		return MemoryProfiler(self)


class VisionPerformanceTester:
	"""Comprehensive performance testing for vision system"""
	
	def __init__(self):
		self.vision_analyzer = VisionAnalyzer()
		self.multi_tier_system = MultiTierVisionSystem()
		self.dom_analyzer = EnhancedDOMAnalyzer()
		self.service_manager = VisionServiceManager()
		self.profiler = PerformanceProfiler()
		self.performance_results = []
		self.load_test_results = []
		self.degradation_results = []
	
	def create_test_image(self, complexity: str = "medium", width: int = 800, height: int = 600) -> str:
		"""Create test images with different complexity levels"""
		img = Image.new('RGB', (width, height), color='white')
		
		if complexity == "simple":
			# Minimal content for fast processing
			from PIL import ImageDraw
			draw = ImageDraw.Draw(img)
			draw.rectangle([200, 200, 600, 400], fill='blue')
			draw.text((300, 300), "Simple", fill='white')
			
		elif complexity == "complex":
			# High complexity for stress testing
			from PIL import ImageDraw
			import random
			draw = ImageDraw.Draw(img)
			
			# Add many elements
			for i in range(50):
				x = random.randint(0, width-100)
				y = random.randint(0, height-30)
				draw.rectangle([x, y, x+80, y+25], 
							 fill=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
				draw.text((x+5, y+5), f"Btn{i}", fill='white')
		
		else:  # medium
			from PIL import ImageDraw
			draw = ImageDraw.Draw(img)
			# Standard form layout
			draw.text((300, 50), "Test Form", fill='black')
			for i in range(5):
				y = 100 + i * 60
				draw.rectangle([200, y, 600, y+30], outline='gray', width=2)
				draw.text((210, y+5), f"Field {i+1}", fill='gray')
		
		with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
			img.save(temp_file.name)
			return temp_file.name
	
	async def benchmark_single_analysis(self, image_path: str, analyzer_type: str = "vision_analyzer") -> PerformanceMetrics:
		"""Benchmark a single vision analysis operation"""
		test_id = f"{analyzer_type}_{int(time.time())}"
		
		with self.profiler.memory_profile() as mem_profile:
			start_time = time.time()
			mem_profile.update_peak()
			
			try:
				if analyzer_type == "vision_analyzer":
					result = await self.vision_analyzer.analyze(image_path, "https://test.com", "Test Page")
				elif analyzer_type == "dom_analyzer":
					from playwright.async_api import async_playwright
					async with async_playwright() as p:
						browser = await p.chromium.launch(headless=True)
						page = await browser.new_page()
						await page.goto("https://example.com")
						result = await self.dom_analyzer.analyze_page(page)
						await browser.close()
				elif analyzer_type == "multi_tier":
					request = VisionRequest(
						page_url="https://test.com",
						page_title="Test Page",
						screenshot_path=image_path,
						max_response_time=30.0
					)
					response = await self.multi_tier_system.analyze(request)
					result = response.vision_state
				else:
					raise ValueError(f"Unknown analyzer type: {analyzer_type}")
				
				mem_profile.update_peak()
				end_time = time.time()
				success = True
				error_message = None
				
			except Exception as e:
				end_time = time.time()
				success = False
				error_message = str(e)
		
		cpu_usage = self.profiler.get_cpu_usage()
		
		metrics = PerformanceMetrics(
			test_id=test_id,
			start_time=start_time,
			end_time=end_time,
			response_time=end_time - start_time,
			memory_before_mb=mem_profile.start_memory,
			memory_after_mb=mem_profile.end_memory,
			memory_peak_mb=mem_profile.peak_memory,
			cpu_percent=cpu_usage,
			success=success,
			error_message=error_message
		)
		
		self.performance_results.append(metrics)
		return metrics
	
	async def load_test_analyzer(self, analyzer_type: str, concurrent_requests: int = 5, 
								total_requests: int = 20, complexity: str = "medium") -> LoadTestResult:
		"""Perform load testing on vision analyzer"""
		test_name = f"load_test_{analyzer_type}_{concurrent_requests}x{total_requests}"
		
		# Create test image
		image_path = self.create_test_image(complexity)
		
		# Track memory at start
		initial_memory = self.profiler.get_memory_usage()
		
		try:
			start_time = time.time()
			
			# Create semaphore to limit concurrency
			semaphore = asyncio.Semaphore(concurrent_requests)
			
			async def single_request():
				async with semaphore:
					return await self.benchmark_single_analysis(image_path, analyzer_type)
			
			# Execute load test
			tasks = [single_request() for _ in range(total_requests)]
			results = await asyncio.gather(*tasks, return_exceptions=True)
			
			end_time = time.time()
			total_duration = end_time - start_time
			
			# Analyze results
			successful_results = [r for r in results if isinstance(r, PerformanceMetrics) and r.success]
			failed_results = [r for r in results if isinstance(r, Exception) or 
							(isinstance(r, PerformanceMetrics) and not r.success)]
			
			if successful_results:
				response_times = [r.response_time for r in successful_results]
				avg_response_time = sum(response_times) / len(response_times)
				min_response_time = min(response_times)
				max_response_time = max(response_times)
				
				# Calculate P95
				sorted_times = sorted(response_times)
				p95_index = int(0.95 * len(sorted_times))
				p95_response_time = sorted_times[p95_index] if sorted_times else 0.0
			else:
				avg_response_time = min_response_time = max_response_time = p95_response_time = 0.0
			
			# Memory and CPU metrics
			final_memory = self.profiler.get_memory_usage()
			memory_growth = final_memory - initial_memory
			cpu_usage = self.profiler.get_cpu_usage()
			
			# Calculate throughput and error rate
			throughput_rps = len(successful_results) / max(total_duration, 0.001)
			error_rate = len(failed_results) / total_requests
			
			result = LoadTestResult(
				test_name=test_name,
				total_requests=total_requests,
				successful_requests=len(successful_results),
				failed_requests=len(failed_results),
				avg_response_time=avg_response_time,
				min_response_time=min_response_time,
				max_response_time=max_response_time,
				p95_response_time=p95_response_time,
				throughput_rps=throughput_rps,
				memory_growth_mb=memory_growth,
				cpu_usage_percent=cpu_usage,
				error_rate=error_rate,
				timestamp=time.time()
			)
			
			self.load_test_results.append(result)
			return result
			
		finally:
			Path(image_path).unlink(missing_ok=True)
	
	async def test_degradation_over_time(self, analyzer_type: str = "vision_analyzer", 
									   iterations: int = 20, delay_between_runs: float = 1.0) -> DegradationTestResult:
		"""Test for performance degradation over time"""
		test_name = f"degradation_{analyzer_type}_{iterations}x"
		
		image_path = self.create_test_image("medium")
		
		try:
			response_times = []
			memory_usage = []
			success_count = 0
			
			initial_memory = self.profiler.get_memory_usage()
			start_time = time.time()
			
			for i in range(iterations):
				# Benchmark single operation
				metrics = await self.benchmark_single_analysis(image_path, analyzer_type)
				
				response_times.append(metrics.response_time)
				memory_usage.append(metrics.memory_after_mb)
				
				if metrics.success:
					success_count += 1
				
				# Small delay between iterations
				if i < iterations - 1:  # No delay after last iteration
					await asyncio.sleep(delay_between_runs)
			
			end_time = time.time()
			total_duration_hours = (end_time - start_time) / 3600
			
			# Calculate degradation metrics
			initial_response_time = response_times[0] if response_times else 0.0
			final_response_time = response_times[-1] if response_times else 0.0
			degradation_factor = final_response_time / max(initial_response_time, 0.001)
			
			# Memory leak detection
			final_memory = self.profiler.get_memory_usage()
			memory_growth = final_memory - initial_memory
			memory_leak_detected = memory_growth > 50.0  # 50MB threshold
			memory_growth_rate = memory_growth / max(total_duration_hours, 0.001)
			
			# Success rate degradation
			success_rate = success_count / iterations
			success_rate_degradation = 1.0 - success_rate
			
			result = DegradationTestResult(
				test_name=test_name,
				iterations=iterations,
				initial_response_time=initial_response_time,
				final_response_time=final_response_time,
				degradation_factor=degradation_factor,
				memory_leak_detected=memory_leak_detected,
				memory_growth_rate_mb_per_hour=memory_growth_rate,
				success_rate_degradation=success_rate_degradation,
				timestamp=time.time()
			)
			
			self.degradation_results.append(result)
			return result
			
		finally:
			Path(image_path).unlink(missing_ok=True)
	
	async def stress_test_memory_limits(self, analyzer_type: str = "vision_analyzer") -> Dict[str, Any]:
		"""Test memory behavior under extreme conditions"""
		test_results = {
			'test_name': f'stress_memory_{analyzer_type}',
			'max_concurrent_reached': 0,
			'memory_peak_mb': 0.0,
			'successful_operations': 0,
			'failed_operations': 0,
			'memory_exhaustion_detected': False
		}
		
		# Create large, complex test image
		large_image_path = self.create_test_image("complex", width=1920, height=1080)
		
		try:
			initial_memory = self.profiler.get_memory_usage()
			max_concurrent = 1
			
			# Gradually increase concurrent operations until failure
			while max_concurrent <= 20:  # Safety limit
				try:
					print(f"Testing {max_concurrent} concurrent operations...")
					
					# Create concurrent tasks
					tasks = []
					for _ in range(max_concurrent):
						task = self.benchmark_single_analysis(large_image_path, analyzer_type)
						tasks.append(task)
					
					# Run with timeout
					results = await asyncio.wait_for(
						asyncio.gather(*tasks, return_exceptions=True),
						timeout=60.0  # 1 minute timeout per batch
					)
					
					# Check memory usage
					current_memory = self.profiler.get_memory_usage()
					test_results['memory_peak_mb'] = max(test_results['memory_peak_mb'], current_memory)
					
					# Count successes/failures
					for result in results:
						if isinstance(result, PerformanceMetrics) and result.success:
							test_results['successful_operations'] += 1
						else:
							test_results['failed_operations'] += 1
					
					# Check for memory exhaustion (> 1GB growth)
					if current_memory - initial_memory > 1000:
						test_results['memory_exhaustion_detected'] = True
						break
					
					test_results['max_concurrent_reached'] = max_concurrent
					max_concurrent += 2
					
					# Small delay between batches
					await asyncio.sleep(2.0)
					
				except (asyncio.TimeoutError, MemoryError, Exception) as e:
					print(f"Failed at {max_concurrent} concurrent operations: {e}")
					test_results['failed_operations'] += max_concurrent
					break
			
			return test_results
			
		finally:
			Path(large_image_path).unlink(missing_ok=True)
	
	def generate_performance_report(self) -> Dict[str, Any]:
		"""Generate comprehensive performance report"""
		report = {
			'summary': {
				'total_performance_tests': len(self.performance_results),
				'total_load_tests': len(self.load_test_results), 
				'total_degradation_tests': len(self.degradation_results),
				'test_timestamp': time.time()
			},
			'performance_metrics': {},
			'load_test_results': [asdict(r) for r in self.load_test_results],
			'degradation_results': [asdict(r) for r in self.degradation_results],
			'sla_compliance': {},
			'recommendations': []
		}
		
		if self.performance_results:
			# Calculate aggregate performance metrics
			successful_results = [r for r in self.performance_results if r.success]
			failed_results = [r for r in self.performance_results if not r.success]
			
			if successful_results:
				response_times = [r.response_time for r in successful_results]
				memory_usage = [r.memory_peak_mb for r in successful_results]
				
				report['performance_metrics'] = {
					'avg_response_time': sum(response_times) / len(response_times),
					'p95_response_time': sorted(response_times)[int(0.95 * len(response_times))],
					'max_response_time': max(response_times),
					'min_response_time': min(response_times),
					'avg_memory_usage_mb': sum(memory_usage) / len(memory_usage),
					'peak_memory_usage_mb': max(memory_usage),
					'success_rate': len(successful_results) / len(self.performance_results),
					'total_tests': len(self.performance_results),
					'successful_tests': len(successful_results),
					'failed_tests': len(failed_results)
				}
		
		# SLA compliance checks
		report['sla_compliance'] = self._check_sla_compliance()
		
		# Generate recommendations
		report['recommendations'] = self._generate_performance_recommendations()
		
		return report
	
	def _check_sla_compliance(self) -> Dict[str, Any]:
		"""Check compliance against performance SLAs"""
		sla_targets = {
			'max_response_time': 30.0,  # seconds
			'p95_response_time': 15.0,  # seconds
			'min_success_rate': 0.95,   # 95%
			'max_memory_growth': 100.0, # MB per hour
			'max_degradation_factor': 2.0  # 2x slowdown acceptable
		}
		
		compliance = {}
		
		# Response time compliance
		if self.performance_results:
			successful_results = [r for r in self.performance_results if r.success]
			if successful_results:
				response_times = [r.response_time for r in successful_results]
				max_response = max(response_times)
				p95_response = sorted(response_times)[int(0.95 * len(response_times))]
				
				compliance['response_time'] = {
					'max_response_compliant': max_response <= sla_targets['max_response_time'],
					'p95_compliant': p95_response <= sla_targets['p95_response_time'],
					'max_response_actual': max_response,
					'p95_actual': p95_response
				}
		
		# Success rate compliance
		if self.performance_results:
			success_rate = len([r for r in self.performance_results if r.success]) / len(self.performance_results)
			compliance['success_rate'] = {
				'compliant': success_rate >= sla_targets['min_success_rate'],
				'actual': success_rate,
				'target': sla_targets['min_success_rate']
			}
		
		# Degradation compliance
		if self.degradation_results:
			worst_degradation = max((r.degradation_factor for r in self.degradation_results), default=1.0)
			compliance['degradation'] = {
				'compliant': worst_degradation <= sla_targets['max_degradation_factor'],
				'worst_degradation_factor': worst_degradation,
				'target': sla_targets['max_degradation_factor']
			}
		
		# Memory growth compliance
		if self.degradation_results:
			worst_memory_growth = max((r.memory_growth_rate_mb_per_hour for r in self.degradation_results), default=0.0)
			compliance['memory_growth'] = {
				'compliant': worst_memory_growth <= sla_targets['max_memory_growth'],
				'worst_growth_rate': worst_memory_growth,
				'target': sla_targets['max_memory_growth']
			}
		
		return compliance
	
	def _generate_performance_recommendations(self) -> List[str]:
		"""Generate performance recommendations based on test results"""
		recommendations = []
		
		# Analyze performance results
		if self.performance_results:
			successful_results = [r for r in self.performance_results if r.success]
			if successful_results:
				avg_response_time = sum(r.response_time for r in successful_results) / len(successful_results)
				max_response_time = max(r.response_time for r in successful_results)
				
				if avg_response_time > 10.0:
					recommendations.append("HIGH: Average response time exceeds 10s. Consider optimizing model or implementing caching.")
				
				if max_response_time > 30.0:
					recommendations.append("CRITICAL: Maximum response time exceeds 30s SLA. Implement timeouts and fallback mechanisms.")
		
		# Analyze load test results
		if self.load_test_results:
			high_error_tests = [r for r in self.load_test_results if r.error_rate > 0.1]
			if high_error_tests:
				recommendations.append("HIGH: High error rate under load detected. Implement better concurrency control and resource management.")
			
			low_throughput_tests = [r for r in self.load_test_results if r.throughput_rps < 0.5]
			if low_throughput_tests:
				recommendations.append("MEDIUM: Low throughput detected. Consider connection pooling and request batching.")
		
		# Analyze degradation results
		if self.degradation_results:
			memory_leaks = [r for r in self.degradation_results if r.memory_leak_detected]
			if memory_leaks:
				recommendations.append("CRITICAL: Memory leaks detected. Review resource cleanup and implement proper disposal patterns.")
			
			high_degradation = [r for r in self.degradation_results if r.degradation_factor > 2.0]
			if high_degradation:
				recommendations.append("HIGH: Performance degradation over time detected. Implement model refresh and cleanup mechanisms.")
		
		if not recommendations:
			recommendations.append("EXCELLENT: All performance tests passed. System meets performance requirements.")
		
		return recommendations


class TestVisionPerformance:
	"""Pytest test class for vision performance testing"""
	
	@pytest.fixture(autouse=True)
	async def setup_performance_tester(self):
		"""Set up performance tester for all tests"""
		self.tester = VisionPerformanceTester()
		yield
		# Generate and save performance report
		report = self.tester.generate_performance_report()
		report_path = Path("vision_performance_report.json")
		with open(report_path, 'w') as f:
			json.dump(report, f, indent=2)
	
	async def test_vision_analyzer_response_time(self):
		"""Test vision analyzer response time requirements"""
		image_path = self.tester.create_test_image("medium")
		
		try:
			metrics = await self.tester.benchmark_single_analysis(image_path, "vision_analyzer")
			
			# SLA requirements
			assert metrics.success, f"Vision analysis failed: {metrics.error_message}"
			assert metrics.response_time < 30.0, f"Response time too slow: {metrics.response_time:.2f}s (SLA: 30s)"
			assert metrics.memory_peak_mb < 1000.0, f"Memory usage too high: {metrics.memory_peak_mb:.1f}MB"
			
		finally:
			Path(image_path).unlink(missing_ok=True)
	
	async def test_dom_analyzer_performance(self):
		"""Test DOM analyzer performance (should be very fast)"""
		image_path = self.tester.create_test_image("simple")
		
		try:
			metrics = await self.tester.benchmark_single_analysis(image_path, "dom_analyzer")
			
			# DOM analyzer should be very fast
			assert metrics.success, f"DOM analysis failed: {metrics.error_message}"
			assert metrics.response_time < 5.0, f"DOM analyzer too slow: {metrics.response_time:.2f}s (should be <5s)"
			
		finally:
			Path(image_path).unlink(missing_ok=True)
	
	async def test_load_performance_vision_analyzer(self):
		"""Test vision analyzer under concurrent load"""
		result = await self.tester.load_test_analyzer("vision_analyzer", concurrent_requests=3, total_requests=9)
		
		# Load test requirements
		assert result.error_rate < 0.2, f"Error rate too high: {result.error_rate:.2%} (should be <20%)"
		assert result.avg_response_time < 45.0, f"Average response time under load too slow: {result.avg_response_time:.2f}s"
		assert result.throughput_rps > 0.1, f"Throughput too low: {result.throughput_rps:.3f} RPS"
		assert result.memory_growth_mb < 200.0, f"Memory growth too high: {result.memory_growth_mb:.1f}MB"
	
	async def test_load_performance_dom_analyzer(self):
		"""Test DOM analyzer under load (should handle high concurrency well)"""
		result = await self.tester.load_test_analyzer("dom_analyzer", concurrent_requests=5, total_requests=15)
		
		# DOM analyzer should handle load very well
		assert result.error_rate < 0.1, f"DOM analyzer error rate too high: {result.error_rate:.2%}"
		assert result.avg_response_time < 10.0, f"DOM analyzer slow under load: {result.avg_response_time:.2f}s"
		assert result.throughput_rps > 0.5, f"DOM analyzer throughput too low: {result.throughput_rps:.3f} RPS"
	
	async def test_performance_degradation_over_time(self):
		"""Test for performance degradation over repeated use"""
		result = await self.tester.test_degradation_over_time("vision_analyzer", iterations=10)
		
		# Degradation limits
		assert not result.memory_leak_detected, f"Memory leak detected: {result.memory_growth_rate_mb_per_hour:.1f}MB/hour"
		assert result.degradation_factor < 3.0, f"Severe performance degradation: {result.degradation_factor:.2f}x slower"
		assert result.success_rate_degradation < 0.1, f"Success rate degraded too much: {result.success_rate_degradation:.2%}"
		
		# Response time should not increase dramatically
		time_increase = result.final_response_time - result.initial_response_time
		assert time_increase < 20.0, f"Response time increased too much: +{time_increase:.2f}s"
	
	@pytest.mark.skip(reason="Intensive test - run manually for stress testing")
	async def test_memory_stress_limits(self):
		"""Stress test memory usage limits"""
		stress_result = await self.tester.stress_test_memory_limits("vision_analyzer")
		
		# Should handle at least some concurrent operations
		assert stress_result['max_concurrent_reached'] >= 2, f"Should handle at least 2 concurrent operations"
		assert stress_result['successful_operations'] > 0, "Should complete at least some operations"
		
		# Memory usage should be reasonable
		assert stress_result['memory_peak_mb'] < 2000, f"Memory usage too high: {stress_result['memory_peak_mb']:.1f}MB"
	
	async def test_multi_tier_performance_comparison(self):
		"""Compare performance across different vision tiers"""
		image_path = self.tester.create_test_image("medium")
		
		try:
			# Test DOM analyzer (Tier 1)
			dom_metrics = await self.tester.benchmark_single_analysis(image_path, "dom_analyzer")
			
			# Test Vision analyzer (Tier 3)
			vision_metrics = await self.tester.benchmark_single_analysis(image_path, "vision_analyzer")
			
			# DOM should be much faster
			if dom_metrics.success and vision_metrics.success:
				speed_ratio = vision_metrics.response_time / max(dom_metrics.response_time, 0.001)
				assert speed_ratio > 2.0, f"DOM analyzer should be significantly faster than vision analyzer, ratio: {speed_ratio:.2f}"
			
			# Both should succeed
			assert dom_metrics.success, f"DOM analyzer failed: {dom_metrics.error_message}"
			
		finally:
			Path(image_path).unlink(missing_ok=True)
	
	async def test_service_restart_recovery(self):
		"""Test performance after service restart"""
		# Note: This test requires actual service management
		# In a real environment, this would restart the Ollama service
		
		image_path = self.tester.create_test_image("medium")
		
		try:
			# Benchmark before restart
			metrics_before = await self.tester.benchmark_single_analysis(image_path, "vision_analyzer")
			
			# Simulate service restart by clearing performance stats
			self.tester.vision_analyzer.performance_stats = {
				'total_calls': 0,
				'successful_calls': 0,
				'timeout_calls': 0,
				'avg_response_time': 0.0,
				'last_successful_time': None
			}
			
			# Wait a moment
			await asyncio.sleep(2.0)
			
			# Benchmark after restart
			metrics_after = await self.tester.benchmark_single_analysis(image_path, "vision_analyzer")
			
			# Service should recover
			assert metrics_after.success, f"Service failed to recover after restart: {metrics_after.error_message}"
			
			# Performance should be reasonable (allow for cold start)
			if metrics_before.success:
				recovery_ratio = metrics_after.response_time / max(metrics_before.response_time, 0.001)
				assert recovery_ratio < 5.0, f"Service too slow after restart: {recovery_ratio:.2f}x slower"
			
		finally:
			Path(image_path).unlink(missing_ok=True)
	
	async def test_performance_report_generation(self):
		"""Test performance report generation"""
		# Run a few tests to populate data
		image_path = self.tester.create_test_image("medium")
		
		try:
			# Generate some test data
			await self.tester.benchmark_single_analysis(image_path, "vision_analyzer")
			await self.tester.load_test_analyzer("dom_analyzer", concurrent_requests=2, total_requests=4)
			
			# Generate report
			report = self.tester.generate_performance_report()
			
			# Validate report structure
			assert 'summary' in report, "Report missing summary"
			assert 'performance_metrics' in report, "Report missing performance metrics"
			assert 'sla_compliance' in report, "Report missing SLA compliance"
			assert 'recommendations' in report, "Report missing recommendations"
			
			# Check that recommendations are provided
			assert isinstance(report['recommendations'], list), "Recommendations should be a list"
			assert len(report['recommendations']) > 0, "Should have at least one recommendation"
			
		finally:
			Path(image_path).unlink(missing_ok=True)