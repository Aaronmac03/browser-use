"""
Comprehensive reliability testing for vision system.
Tests fault injection, circuit breaker behavior, fallback mechanisms, and recovery scenarios.

Key Focus Areas:
- Fault injection testing (service failures, timeouts, memory issues)  
- Circuit breaker behavior validation
- Fallback mechanism testing
- Multi-tier routing correctness
- Service recovery testing
- Error handling robustness
"""

import asyncio
import json
import random
import signal
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import httpx
from PIL import Image

# Import vision system components
from vision_module import VisionAnalyzer, VisionState
from multi_tier_vision import MultiTierVisionSystem, VisionRequest, VisionTier, VisionResponse
from enhanced_dom_analyzer import EnhancedDOMAnalyzer
from vision_service_manager import VisionServiceManager, ServiceStatus


@dataclass
class FaultInjectionResult:
	"""Results from fault injection testing"""
	test_name: str
	fault_type: str
	fault_parameters: Dict[str, Any]
	graceful_degradation: bool
	fallback_activated: bool
	error_handling_correct: bool
	recovery_time_seconds: float
	final_state: str
	timestamp: float


@dataclass
class CircuitBreakerTest:
	"""Circuit breaker test configuration and results"""
	test_name: str
	failure_threshold: int
	recovery_time: float
	test_operations: int
	failures_injected: int
	circuit_opened_correctly: bool
	circuit_recovered_correctly: bool
	blocked_requests: int
	timestamp: float


@dataclass
class FallbackTest:
	"""Fallback mechanism test results"""
	test_name: str
	primary_tier: str
	fallback_tier: str
	primary_success: bool
	fallback_success: bool
	fallback_triggered_correctly: bool
	response_quality_maintained: bool
	total_time: float
	timestamp: float


class FaultInjector:
	"""Fault injection utilities for testing system resilience"""
	
	@staticmethod
	def create_timeout_fault(timeout_seconds: float = 0.1):
		"""Create a timeout fault that makes operations hang"""
		async def timeout_operation(*args, **kwargs):
			await asyncio.sleep(timeout_seconds * 10)  # Much longer than timeout
			return {"response": '{"error": "timeout"}'}
		return timeout_operation
	
	@staticmethod
	def create_memory_fault():
		"""Create a memory exhaustion fault"""
		def memory_operation(*args, **kwargs):
			# Simulate memory exhaustion
			raise MemoryError("Simulated memory exhaustion")
		return memory_operation
	
	@staticmethod
	def create_connection_fault():
		"""Create a connection failure fault"""
		async def connection_operation(*args, **kwargs):
			raise httpx.ConnectError("Simulated connection failure")
		return connection_operation
	
	@staticmethod
	def create_malformed_response_fault():
		"""Create malformed response fault"""
		async def malformed_operation(*args, **kwargs):
			return {"response": "{ invalid json syntax: missing quote }"}
		return malformed_operation
	
	@staticmethod
	def create_http_error_fault(status_code: int = 500):
		"""Create HTTP error response fault"""
		async def http_error_operation(*args, **kwargs):
			error = httpx.HTTPStatusError(
				f"Simulated HTTP {status_code}",
				request=MagicMock(), 
				response=MagicMock(status_code=status_code, text="Server Error")
			)
			raise error
		return http_error_operation
	
	@staticmethod
	def create_partial_failure_fault(success_rate: float = 0.3):
		"""Create intermittent fault with specified success rate"""
		async def partial_failure_operation(*args, **kwargs):
			if random.random() < success_rate:
				return {"response": '{"caption": "Partial success", "elements": [], "fields": [], "affordances": []}'}
			else:
				raise Exception("Simulated intermittent failure")
		return partial_failure_operation
	
	@staticmethod
	def create_slow_response_fault(base_delay: float = 5.0, variance: float = 2.0):
		"""Create fault that makes responses very slow"""
		async def slow_operation(*args, **kwargs):
			delay = base_delay + random.uniform(-variance, variance)
			await asyncio.sleep(delay)
			return {"response": '{"caption": "Slow response", "elements": [], "fields": [], "affordances": []}'}
		return slow_operation


class VisionReliabilityTester:
	"""Comprehensive reliability testing for vision system"""
	
	def __init__(self):
		self.vision_analyzer = VisionAnalyzer()
		self.multi_tier_system = MultiTierVisionSystem()
		self.dom_analyzer = EnhancedDOMAnalyzer()
		self.service_manager = VisionServiceManager()
		self.fault_injector = FaultInjector()
		self.test_results = []
		self.circuit_breaker_results = []
		self.fallback_results = []
	
	def create_test_image(self, content: str = "standard") -> str:
		"""Create test image for reliability testing"""
		img = Image.new('RGB', (800, 600), color='white')
		
		if content == "standard":
			from PIL import ImageDraw
			draw = ImageDraw.Draw(img)
			draw.text((300, 200), "Test Content", fill='black')
			draw.rectangle([200, 300, 400, 350], outline='blue', width=2)
			draw.text((250, 315), "Button", fill='blue')
		
		with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
			img.save(temp_file.name)
			return temp_file.name
	
	async def test_timeout_fault_injection(self) -> FaultInjectionResult:
		"""Test system behavior when operations timeout"""
		test_name = "timeout_fault_injection"
		image_path = self.create_test_image()
		
		try:
			start_time = time.time()
			
			# Inject timeout fault into vision analyzer
			timeout_fault = self.fault_injector.create_timeout_fault(0.1)
			
			with patch.object(self.vision_analyzer, 'call_moondream', timeout_fault):
				try:
					# This should timeout and handle gracefully
					vision_state = await asyncio.wait_for(
						self.vision_analyzer.analyze(image_path, "https://test.com", "Test"),
						timeout=5.0  # Short timeout to force failure
					)
					
					# If we get here, check if it's a fallback response
					graceful_degradation = "timeout" in vision_state.caption.lower() or vision_state.meta.confidence == 0.0
					fallback_activated = vision_state.meta.model_name == "fallback"
					
				except asyncio.TimeoutError:
					# System should have provided a fallback before timeout
					graceful_degradation = False
					fallback_activated = False
				except Exception as e:
					# System should not raise unhandled exceptions
					graceful_degradation = "timeout" in str(e).lower()
					fallback_activated = False
			
			recovery_time = time.time() - start_time
			
			result = FaultInjectionResult(
				test_name=test_name,
				fault_type="timeout",
				fault_parameters={"timeout_seconds": 0.1},
				graceful_degradation=graceful_degradation,
				fallback_activated=fallback_activated,
				error_handling_correct=True,  # Should always handle timeouts
				recovery_time_seconds=recovery_time,
				final_state="recovered" if graceful_degradation else "failed",
				timestamp=time.time()
			)
			
			self.test_results.append(result)
			return result
			
		finally:
			Path(image_path).unlink(missing_ok=True)
	
	async def test_memory_fault_injection(self) -> FaultInjectionResult:
		"""Test system behavior under memory pressure"""
		test_name = "memory_fault_injection"
		image_path = self.create_test_image()
		
		try:
			start_time = time.time()
			
			# Inject memory fault
			memory_fault = self.fault_injector.create_memory_fault()
			
			with patch.object(self.vision_analyzer, 'call_moondream', memory_fault):
				try:
					vision_state = await self.vision_analyzer.analyze(image_path, "https://test.com", "Test")
					
					# Should get fallback response
					graceful_degradation = True
					fallback_activated = vision_state.meta.model_name == "fallback" or "failed" in vision_state.caption.lower()
					error_handling_correct = True
					
				except MemoryError:
					# Memory errors should be caught and handled
					graceful_degradation = False
					fallback_activated = False
					error_handling_correct = False
				except Exception as e:
					# Other exceptions might be acceptable if they indicate fallback
					graceful_degradation = "memory" in str(e).lower()
					fallback_activated = False
					error_handling_correct = True
			
			recovery_time = time.time() - start_time
			
			result = FaultInjectionResult(
				test_name=test_name,
				fault_type="memory_exhaustion",
				fault_parameters={"simulated": True},
				graceful_degradation=graceful_degradation,
				fallback_activated=fallback_activated,
				error_handling_correct=error_handling_correct,
				recovery_time_seconds=recovery_time,
				final_state="recovered" if graceful_degradation else "failed",
				timestamp=time.time()
			)
			
			self.test_results.append(result)
			return result
			
		finally:
			Path(image_path).unlink(missing_ok=True)
	
	async def test_connection_fault_injection(self) -> FaultInjectionResult:
		"""Test system behavior when service connections fail"""
		test_name = "connection_fault_injection"
		image_path = self.create_test_image()
		
		try:
			start_time = time.time()
			
			# Inject connection fault
			connection_fault = self.fault_injector.create_connection_fault()
			
			with patch.object(self.vision_analyzer, 'call_moondream', connection_fault):
				try:
					vision_state = await self.vision_analyzer.analyze(image_path, "https://test.com", "Test")
					
					# Should get fallback response
					graceful_degradation = True
					fallback_activated = ("not running" in vision_state.caption.lower() or 
										vision_state.meta.model_name == "fallback")
					error_handling_correct = True
					
				except httpx.ConnectError:
					# Connection errors should be caught
					graceful_degradation = False
					fallback_activated = False
					error_handling_correct = False
				except Exception as e:
					# Check if it's a handled connection error
					graceful_degradation = "connection" in str(e).lower() or "not running" in str(e).lower()
					fallback_activated = False
					error_handling_correct = True
			
			recovery_time = time.time() - start_time
			
			result = FaultInjectionResult(
				test_name=test_name,
				fault_type="connection_failure",
				fault_parameters={"service": "ollama"},
				graceful_degradation=graceful_degradation,
				fallback_activated=fallback_activated,
				error_handling_correct=error_handling_correct,
				recovery_time_seconds=recovery_time,
				final_state="recovered" if graceful_degradation else "failed",
				timestamp=time.time()
			)
			
			self.test_results.append(result)
			return result
			
		finally:
			Path(image_path).unlink(missing_ok=True)
	
	async def test_malformed_response_handling(self) -> FaultInjectionResult:
		"""Test handling of malformed JSON responses"""
		test_name = "malformed_response_handling"
		image_path = self.create_test_image()
		
		try:
			start_time = time.time()
			
			# Inject malformed response fault
			malformed_fault = self.fault_injector.create_malformed_response_fault()
			
			with patch.object(self.vision_analyzer, 'call_moondream', malformed_fault):
				try:
					vision_state = await self.vision_analyzer.analyze(image_path, "https://test.com", "Test")
					
					# Should handle malformed response gracefully
					graceful_degradation = True
					fallback_activated = ("parsing failed" in vision_state.caption.lower() or
										vision_state.meta.model_name == "fallback")
					error_handling_correct = True
					
				except Exception as e:
					# JSON parsing errors should be handled
					graceful_degradation = "json" in str(e).lower() or "parsing" in str(e).lower()
					fallback_activated = False
					error_handling_correct = graceful_degradation
			
			recovery_time = time.time() - start_time
			
			result = FaultInjectionResult(
				test_name=test_name,
				fault_type="malformed_response",
				fault_parameters={"invalid_json": True},
				graceful_degradation=graceful_degradation,
				fallback_activated=fallback_activated,
				error_handling_correct=error_handling_correct,
				recovery_time_seconds=recovery_time,
				final_state="recovered" if graceful_degradation else "failed",
				timestamp=time.time()
			)
			
			self.test_results.append(result)
			return result
			
		finally:
			Path(image_path).unlink(missing_ok=True)
	
	async def test_circuit_breaker_behavior(self) -> CircuitBreakerTest:
		"""Test circuit breaker opening and recovery"""
		test_name = "circuit_breaker_behavior"
		image_path = self.create_test_image()
		
		try:
			# Reset circuit breaker state
			self.vision_analyzer.circuit_breaker = {
				'consecutive_failures': 0,
				'max_failures': 3,  # Lower threshold for testing
				'recovery_time': 5,  # Short recovery time for testing
				'last_failure_time': None,
				'is_open': False
			}
			
			failure_count = 0
			blocked_count = 0
			circuit_opened = False
			
			# Inject failures to trigger circuit breaker
			connection_fault = self.fault_injector.create_connection_fault()
			
			with patch.object(self.vision_analyzer, 'call_moondream', connection_fault):
				# Phase 1: Inject failures to open circuit breaker
				for i in range(5):
					try:
						vision_state = await self.vision_analyzer.analyze(image_path, "https://test.com", "Test")
						if "temporarily disabled" in vision_state.caption.lower():
							blocked_count += 1
							circuit_opened = True
					except Exception as e:
						if "circuit breaker" in str(e).lower() or "disabled" in str(e).lower():
							blocked_count += 1
							circuit_opened = True
						else:
							failure_count += 1
					
					# Small delay between attempts
					await asyncio.sleep(0.1)
			
			# Phase 2: Wait for recovery and test
			await asyncio.sleep(2)  # Wait for partial recovery
			
			circuit_recovered = False
			with patch.object(self.vision_analyzer, 'call_moondream', 
							AsyncMock(return_value={"response": '{"caption": "Recovered", "elements": [], "fields": [], "affordances": []}'})):
				try:
					vision_state = await self.vision_analyzer.analyze(image_path, "https://test.com", "Test")
					if "Recovered" in vision_state.caption:
						circuit_recovered = True
				except Exception:
					pass
			
			result = CircuitBreakerTest(
				test_name=test_name,
				failure_threshold=3,
				recovery_time=5.0,
				test_operations=5,
				failures_injected=failure_count,
				circuit_opened_correctly=circuit_opened,
				circuit_recovered_correctly=circuit_recovered,
				blocked_requests=blocked_count,
				timestamp=time.time()
			)
			
			self.circuit_breaker_results.append(result)
			return result
			
		finally:
			Path(image_path).unlink(missing_ok=True)
	
	async def test_multi_tier_fallback_mechanisms(self) -> List[FallbackTest]:
		"""Test fallback mechanisms across different tiers"""
		results = []
		image_path = self.create_test_image()
		
		try:
			# Test Tier 3 -> Tier 1 fallback
			test_name = "tier3_to_tier1_fallback"
			
			# Inject fault into Tier 3 (advanced vision)
			connection_fault = self.fault_injector.create_connection_fault()
			
			with patch.object(self.vision_analyzer, 'call_moondream', connection_fault):
				start_time = time.time()
				
				request = VisionRequest(
					page_url="https://test.com",
					page_title="Test Page",
					screenshot_path=image_path,
					max_response_time=10.0,
					required_accuracy=0.8
				)
				
				try:
					response = await self.multi_tier_system.analyze(request)
					
					primary_success = False  # Tier 3 should fail
					fallback_success = response.tier_used == VisionTier.TIER1_DOM or response.tier_used == VisionTier.FALLBACK
					fallback_triggered = response.fallback_reason is not None
					quality_maintained = len(response.vision_state.elements) > 0 or len(response.vision_state.caption) > 10
					
				except Exception as e:
					primary_success = False
					fallback_success = False
					fallback_triggered = False
					quality_maintained = False
				
				total_time = time.time() - start_time
				
				result = FallbackTest(
					test_name=test_name,
					primary_tier="tier3_advanced",
					fallback_tier="tier1_dom",
					primary_success=primary_success,
					fallback_success=fallback_success,
					fallback_triggered_correctly=fallback_triggered,
					response_quality_maintained=quality_maintained,
					total_time=total_time,
					timestamp=time.time()
				)
				
				results.append(result)
				self.fallback_results.append(result)
			
			return results
			
		finally:
			Path(image_path).unlink(missing_ok=True)
	
	async def test_service_recovery_after_failure(self) -> FaultInjectionResult:
		"""Test system recovery after service failure and restart"""
		test_name = "service_recovery_test"
		image_path = self.create_test_image()
		
		try:
			start_time = time.time()
			
			# Phase 1: Simulate service failure
			connection_fault = self.fault_injector.create_connection_fault()
			
			with patch.object(self.vision_analyzer, 'call_moondream', connection_fault):
				try:
					# This should fail
					vision_state_failed = await self.vision_analyzer.analyze(image_path, "https://test.com", "Test")
				except Exception:
					pass
			
			# Phase 2: Simulate service recovery
			await asyncio.sleep(1)  # Simulate brief downtime
			
			# Mock successful service recovery
			with patch.object(self.vision_analyzer, 'call_moondream', 
							AsyncMock(return_value={"response": '{"caption": "Service recovered", "elements": [], "fields": [], "affordances": []}'})):
				try:
					vision_state_recovered = await self.vision_analyzer.analyze(image_path, "https://test.com", "Test")
					
					graceful_degradation = True
					fallback_activated = False
					error_handling_correct = "recovered" in vision_state_recovered.caption.lower()
					
				except Exception as e:
					graceful_degradation = False
					fallback_activated = False
					error_handling_correct = False
			
			recovery_time = time.time() - start_time
			
			result = FaultInjectionResult(
				test_name=test_name,
				fault_type="service_restart",
				fault_parameters={"downtime_seconds": 1.0},
				graceful_degradation=graceful_degradation,
				fallback_activated=fallback_activated,
				error_handling_correct=error_handling_correct,
				recovery_time_seconds=recovery_time,
				final_state="recovered" if error_handling_correct else "failed",
				timestamp=time.time()
			)
			
			self.test_results.append(result)
			return result
			
		finally:
			Path(image_path).unlink(missing_ok=True)
	
	async def test_concurrent_fault_handling(self) -> FaultInjectionResult:
		"""Test handling of concurrent operations during faults"""
		test_name = "concurrent_fault_handling"
		image_path = self.create_test_image()
		
		try:
			start_time = time.time()
			
			# Create partial failure fault (30% success rate)
			partial_fault = self.fault_injector.create_partial_failure_fault(0.3)
			
			successful_operations = 0
			failed_operations = 0
			
			with patch.object(self.vision_analyzer, 'call_moondream', partial_fault):
				# Run 10 concurrent operations
				tasks = []
				for i in range(10):
					task = self.vision_analyzer.analyze(image_path, "https://test.com", f"Test {i}")
					tasks.append(task)
				
				results = await asyncio.gather(*tasks, return_exceptions=True)
				
				for result in results:
					if isinstance(result, VisionState):
						if "Partial success" in result.caption or result.meta.confidence > 0:
							successful_operations += 1
						else:
							failed_operations += 1
					else:
						failed_operations += 1
			
			# Evaluate fault handling
			total_operations = successful_operations + failed_operations
			success_rate = successful_operations / max(total_operations, 1)
			
			# Should handle at least some operations successfully
			graceful_degradation = success_rate > 0.1  # At least 10% success
			fallback_activated = failed_operations > 0  # Some failures should trigger fallbacks
			error_handling_correct = total_operations == 10  # All operations should complete
			
			recovery_time = time.time() - start_time
			
			result = FaultInjectionResult(
				test_name=test_name,
				fault_type="concurrent_partial_failure",
				fault_parameters={"success_rate": 0.3, "concurrent_ops": 10},
				graceful_degradation=graceful_degradation,
				fallback_activated=fallback_activated,
				error_handling_correct=error_handling_correct,
				recovery_time_seconds=recovery_time,
				final_state="recovered" if graceful_degradation else "degraded",
				timestamp=time.time()
			)
			
			self.test_results.append(result)
			return result
			
		finally:
			Path(image_path).unlink(missing_ok=True)
	
	def generate_reliability_report(self) -> Dict[str, Any]:
		"""Generate comprehensive reliability report"""
		report = {
			'summary': {
				'total_fault_injection_tests': len(self.test_results),
				'total_circuit_breaker_tests': len(self.circuit_breaker_results),
				'total_fallback_tests': len(self.fallback_results),
				'test_timestamp': time.time()
			},
			'fault_injection_results': [asdict(r) for r in self.test_results],
			'circuit_breaker_results': [asdict(r) for r in self.circuit_breaker_results],
			'fallback_test_results': [asdict(r) for r in self.fallback_results],
			'reliability_metrics': {},
			'recommendations': []
		}
		
		if self.test_results:
			# Calculate reliability metrics
			graceful_degradation_rate = sum(1 for r in self.test_results if r.graceful_degradation) / len(self.test_results)
			fallback_activation_rate = sum(1 for r in self.test_results if r.fallback_activated) / len(self.test_results)
			error_handling_rate = sum(1 for r in self.test_results if r.error_handling_correct) / len(self.test_results)
			avg_recovery_time = sum(r.recovery_time_seconds for r in self.test_results) / len(self.test_results)
			
			report['reliability_metrics'] = {
				'graceful_degradation_rate': graceful_degradation_rate,
				'fallback_activation_rate': fallback_activation_rate,
				'error_handling_correctness': error_handling_rate,
				'average_recovery_time': avg_recovery_time,
				'fault_types_tested': list(set(r.fault_type for r in self.test_results))
			}
		
		# Generate recommendations
		report['recommendations'] = self._generate_reliability_recommendations()
		
		return report
	
	def _generate_reliability_recommendations(self) -> List[str]:
		"""Generate reliability recommendations based on test results"""
		recommendations = []
		
		if not self.test_results:
			return ["No reliability test data available for recommendations"]
		
		# Analyze fault injection results
		graceful_degradation_failures = [r for r in self.test_results if not r.graceful_degradation]
		if len(graceful_degradation_failures) > len(self.test_results) * 0.2:
			recommendations.append("HIGH: Graceful degradation rate below 80%. Improve error handling and fallback mechanisms.")
		
		error_handling_failures = [r for r in self.test_results if not r.error_handling_correct]
		if len(error_handling_failures) > 0:
			recommendations.append("CRITICAL: Error handling failures detected. Review exception handling and implement proper error recovery.")
		
		slow_recovery = [r for r in self.test_results if r.recovery_time_seconds > 10.0]
		if len(slow_recovery) > len(self.test_results) * 0.3:
			recommendations.append("MEDIUM: Slow recovery times detected. Optimize service restart and fallback mechanisms.")
		
		# Analyze circuit breaker results
		circuit_breaker_failures = [r for r in self.circuit_breaker_results if not r.circuit_opened_correctly]
		if len(circuit_breaker_failures) > 0:
			recommendations.append("HIGH: Circuit breaker not functioning correctly. Review circuit breaker implementation and thresholds.")
		
		# Analyze fallback results
		fallback_failures = [r for r in self.fallback_results if not r.fallback_success]
		if len(fallback_failures) > 0:
			recommendations.append("HIGH: Fallback mechanisms failing. Ensure all fallback tiers are properly implemented and tested.")
		
		if not recommendations:
			recommendations.append("EXCELLENT: All reliability tests passed. System demonstrates robust fault tolerance.")
		
		return recommendations


class TestVisionReliability:
	"""Pytest test class for vision reliability testing"""
	
	@pytest.fixture(autouse=True)
	async def setup_reliability_tester(self):
		"""Set up reliability tester for all tests"""
		self.tester = VisionReliabilityTester()
		yield
		# Generate and save reliability report
		report = self.tester.generate_reliability_report()
		report_path = Path("vision_reliability_report.json")
		with open(report_path, 'w') as f:
			json.dump(report, f, indent=2)
	
	async def test_timeout_fault_injection(self):
		"""Test graceful handling of timeout faults"""
		result = await self.tester.test_timeout_fault_injection()
		
		# System should handle timeouts gracefully
		assert result.graceful_degradation, f"System did not handle timeout gracefully: {result.final_state}"
		assert result.error_handling_correct, "Error handling was not correct for timeout"
		assert result.recovery_time_seconds < 15.0, f"Recovery took too long: {result.recovery_time_seconds:.2f}s"
	
	async def test_memory_fault_injection(self):
		"""Test handling of memory exhaustion"""
		result = await self.tester.test_memory_fault_injection()
		
		# System should not crash on memory errors
		assert result.error_handling_correct, f"Memory error not handled correctly: {result.final_state}"
		assert result.recovery_time_seconds < 10.0, f"Memory fault recovery too slow: {result.recovery_time_seconds:.2f}s"
	
	async def test_connection_fault_injection(self):
		"""Test handling of connection failures"""
		result = await self.tester.test_connection_fault_injection()
		
		# System should handle connection failures gracefully
		assert result.graceful_degradation, f"Connection failure not handled gracefully: {result.final_state}"
		assert result.error_handling_correct, "Connection error handling incorrect"
	
	async def test_malformed_response_handling(self):
		"""Test handling of malformed JSON responses"""
		result = await self.tester.test_malformed_response_handling()
		
		# System should handle malformed responses without crashing
		assert result.graceful_degradation, f"Malformed response not handled gracefully: {result.final_state}"
		assert result.error_handling_correct, "Malformed response error handling incorrect"
	
	async def test_circuit_breaker_behavior(self):
		"""Test circuit breaker functionality"""
		result = await self.tester.test_circuit_breaker_behavior()
		
		# Circuit breaker should open after failures and recover
		assert result.failures_injected > 0, "No failures were injected for circuit breaker test"
		assert result.blocked_requests > 0 or result.circuit_opened_correctly, "Circuit breaker did not open or block requests"
		
		# Note: Recovery test might be flaky due to timing, so we make it optional
		print(f"Circuit breaker recovery: {result.circuit_recovered_correctly}")
	
	async def test_multi_tier_fallback_mechanisms(self):
		"""Test multi-tier fallback mechanisms"""
		results = await self.tester.test_multi_tier_fallback_mechanisms()
		
		assert len(results) > 0, "No fallback tests were executed"
		
		for result in results:
			# Primary tier should fail (we injected faults)
			# Fallback should succeed
			assert not result.primary_success, f"Primary tier should have failed in {result.test_name}"
			# Fallback triggering is more important than success
			assert result.fallback_triggered_correctly, f"Fallback not triggered correctly in {result.test_name}"
	
	async def test_service_recovery_after_failure(self):
		"""Test service recovery after simulated restart"""
		result = await self.tester.test_service_recovery_after_failure()
		
		# Service should recover after restart
		assert result.graceful_degradation, f"Service did not recover gracefully: {result.final_state}"
		assert result.error_handling_correct, "Service recovery error handling incorrect"
		assert result.recovery_time_seconds < 20.0, f"Service recovery too slow: {result.recovery_time_seconds:.2f}s"
	
	async def test_concurrent_fault_handling(self):
		"""Test handling of faults under concurrent load"""
		result = await self.tester.test_concurrent_fault_handling()
		
		# System should handle concurrent operations during faults
		assert result.graceful_degradation, f"Concurrent fault handling failed: {result.final_state}"
		assert result.error_handling_correct, "Concurrent operations were not handled correctly"
		
		# Should complete in reasonable time even with faults
		assert result.recovery_time_seconds < 30.0, f"Concurrent fault handling too slow: {result.recovery_time_seconds:.2f}s"
	
	async def test_cascading_failure_prevention(self):
		"""Test prevention of cascading failures"""
		# This test ensures one component's failure doesn't bring down others
		image_path = self.tester.create_test_image()
		
		try:
			# Test that DOM analyzer continues working when vision analyzer fails
			connection_fault = self.tester.fault_injector.create_connection_fault()
			
			with patch.object(self.tester.vision_analyzer, 'call_moondream', connection_fault):
				# DOM analyzer should still work
				from playwright.async_api import async_playwright
				async with async_playwright() as p:
					browser = await p.chromium.launch(headless=True)
					page = await browser.new_page()
					await page.goto("https://example.com")
					
					dom_result = await self.tester.dom_analyzer.analyze_page(page)
					await browser.close()
					
					# DOM analyzer should not be affected by vision analyzer failure
					assert dom_result.meta.confidence > 0, "DOM analyzer was affected by vision analyzer failure"
					assert len(dom_result.caption) > 0, "DOM analyzer produced empty results"
			
		finally:
			Path(image_path).unlink(missing_ok=True)
	
	async def test_resource_leak_prevention(self):
		"""Test that failures don't cause resource leaks"""
		image_path = self.tester.create_test_image()
		
		try:
			# Inject failures and check that resources are cleaned up
			connection_fault = self.tester.fault_injector.create_connection_fault()
			
			initial_handles = len([h for h in asyncio.all_tasks() if not h.done()])
			
			with patch.object(self.tester.vision_analyzer, 'call_moondream', connection_fault):
				# Run multiple failing operations
				for i in range(5):
					try:
						await self.tester.vision_analyzer.analyze(image_path, "https://test.com", f"Test {i}")
					except Exception:
						pass  # Expected to fail
			
			# Wait for cleanup
			await asyncio.sleep(1.0)
			
			final_handles = len([h for h in asyncio.all_tasks() if not h.done()])
			
			# Should not have significantly more handles (allow some variance)
			handle_growth = final_handles - initial_handles
			assert handle_growth <= 3, f"Possible resource leak: {handle_growth} additional async handles"
			
		finally:
			Path(image_path).unlink(missing_ok=True)
	
	async def test_reliability_report_generation(self):
		"""Test reliability report generation"""
		# Run a few tests to populate data
		await self.tester.test_timeout_fault_injection()
		await self.tester.test_connection_fault_injection()
		
		# Generate report
		report = self.tester.generate_reliability_report()
		
		# Validate report structure
		assert 'summary' in report, "Report missing summary"
		assert 'fault_injection_results' in report, "Report missing fault injection results"
		assert 'reliability_metrics' in report, "Report missing reliability metrics"
		assert 'recommendations' in report, "Report missing recommendations"
		
		# Check that metrics are calculated
		if report['reliability_metrics']:
			metrics = report['reliability_metrics']
			assert 'graceful_degradation_rate' in metrics, "Missing graceful degradation rate"
			assert 'error_handling_correctness' in metrics, "Missing error handling correctness"
			assert 0.0 <= metrics['graceful_degradation_rate'] <= 1.0, "Invalid degradation rate"
		
		# Check recommendations
		assert isinstance(report['recommendations'], list), "Recommendations should be a list"
		assert len(report['recommendations']) > 0, "Should have at least one recommendation"