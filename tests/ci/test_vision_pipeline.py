"""
Automated testing pipeline for vision system.
Orchestrates comprehensive testing across all test categories and generates unified reports.

Key Components:
- Test suite orchestration and scheduling
- Performance benchmarking and monitoring 
- Failure scenario testing coverage
- Automated report generation and analysis
- CI/CD integration capabilities
- Test result aggregation and trending
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import logging

import pytest

# Import test suites
from test_vision_consistency import VisionConsistencyTester
from test_vision_performance import VisionPerformanceTester  
from test_vision_reliability import VisionReliabilityTester
from test_vision_integration import VisionIntegrationTester


@dataclass
class PipelineTestResult:
	"""Results from a complete pipeline test run"""
	pipeline_id: str
	start_time: float
	end_time: float
	total_duration: float
	test_suites_run: List[str]
	test_suites_passed: List[str]
	test_suites_failed: List[str]
	overall_success_rate: float
	critical_issues_found: List[str]
	recommendations: List[str]
	report_files_generated: List[str]
	timestamp: float


@dataclass
class TestSuiteResult:
	"""Results from a single test suite"""
	suite_name: str
	tests_run: int
	tests_passed: int
	tests_failed: int
	success_rate: float
	duration: float
	critical_failures: List[str]
	performance_metrics: Dict[str, float]
	report_data: Dict[str, Any]


class VisionTestPipeline:
	"""Comprehensive automated testing pipeline for vision system"""
	
	def __init__(self):
		self.consistency_tester = VisionConsistencyTester()
		self.performance_tester = VisionPerformanceTester()
		self.reliability_tester = VisionReliabilityTester()
		self.integration_tester = VisionIntegrationTester()
		
		self.pipeline_results = []
		self.suite_results = []
		
		# Test configuration
		self.test_config = {
			'consistency_tests': {
				'enabled': True,
				'test_runs_per_scenario': 5,
				'scenarios': ['login', 'ecommerce', 'form'],
				'timeout_per_test': 60.0
			},
			'performance_tests': {
				'enabled': True,
				'load_test_configs': [
					{'concurrent': 3, 'total': 9, 'complexity': 'medium'},
					{'concurrent': 2, 'total': 6, 'complexity': 'simple'}
				],
				'degradation_test_iterations': 10,
				'timeout_per_test': 120.0
			},
			'reliability_tests': {
				'enabled': True,
				'fault_injection_scenarios': [
					'timeout', 'memory', 'connection', 'malformed_response'
				],
				'circuit_breaker_tests': True,
				'timeout_per_test': 60.0
			},
			'integration_tests': {
				'enabled': True,
				'page_scenarios': ['login', 'ecommerce', 'form', 'standard'],
				'cross_tier_comparisons': True,
				'timeout_per_test': 90.0
			}
		}
		
		# Setup logging
		logging.basicConfig(
			level=logging.INFO,
			format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
		)
		self.logger = logging.getLogger('VisionTestPipeline')
	
	async def run_complete_pipeline(self, pipeline_id: Optional[str] = None) -> PipelineTestResult:
		"""Run the complete vision testing pipeline"""
		if not pipeline_id:
			pipeline_id = f"vision_pipeline_{int(time.time())}"
		
		self.logger.info(f"Starting vision test pipeline: {pipeline_id}")
		start_time = time.time()
		
		test_suites_run = []
		test_suites_passed = []
		test_suites_failed = []
		critical_issues = []
		all_recommendations = []
		report_files = []
		
		# Run test suites in parallel where possible
		suite_tasks = []
		
		# Consistency tests
		if self.test_config['consistency_tests']['enabled']:
			suite_tasks.append(self._run_consistency_suite())
		
		# Performance tests  
		if self.test_config['performance_tests']['enabled']:
			suite_tasks.append(self._run_performance_suite())
		
		# Reliability tests
		if self.test_config['reliability_tests']['enabled']:
			suite_tasks.append(self._run_reliability_suite())
		
		# Integration tests
		if self.test_config['integration_tests']['enabled']:
			suite_tasks.append(self._run_integration_suite())
		
		# Execute test suites
		suite_results = await asyncio.gather(*suite_tasks, return_exceptions=True)
		
		# Process results
		for i, result in enumerate(suite_results):
			if isinstance(result, Exception):
				self.logger.error(f"Test suite {i} failed with exception: {result}")
				test_suites_failed.append(f"suite_{i}")
				critical_issues.append(f"Test suite {i} crashed: {str(result)}")
			elif isinstance(result, TestSuiteResult):
				test_suites_run.append(result.suite_name)
				
				if result.success_rate >= 0.8:  # 80% threshold
					test_suites_passed.append(result.suite_name)
				else:
					test_suites_failed.append(result.suite_name)
				
				# Collect critical failures
				critical_issues.extend(result.critical_failures)
				
				# Store suite result
				self.suite_results.append(result)
		
		# Generate unified reports
		unified_report = await self._generate_unified_report(pipeline_id)
		report_files.append(f"{pipeline_id}_unified_report.json")
		
		# Generate recommendations
		pipeline_recommendations = self._generate_pipeline_recommendations()
		all_recommendations.extend(pipeline_recommendations)
		
		# Calculate overall metrics
		end_time = time.time()
		total_duration = end_time - start_time
		overall_success_rate = len(test_suites_passed) / max(len(test_suites_run), 1)
		
		# Create pipeline result
		pipeline_result = PipelineTestResult(
			pipeline_id=pipeline_id,
			start_time=start_time,
			end_time=end_time,
			total_duration=total_duration,
			test_suites_run=test_suites_run,
			test_suites_passed=test_suites_passed,
			test_suites_failed=test_suites_failed,
			overall_success_rate=overall_success_rate,
			critical_issues_found=critical_issues,
			recommendations=all_recommendations,
			report_files_generated=report_files,
			timestamp=time.time()
		)
		
		self.pipeline_results.append(pipeline_result)
		
		# Save pipeline result
		await self._save_pipeline_result(pipeline_result, unified_report)
		
		self.logger.info(f"Pipeline {pipeline_id} completed in {total_duration:.2f}s")
		self.logger.info(f"Success rate: {overall_success_rate:.1%}")
		self.logger.info(f"Critical issues: {len(critical_issues)}")
		
		return pipeline_result
	
	async def _run_consistency_suite(self) -> TestSuiteResult:
		"""Run consistency test suite"""
		self.logger.info("Running consistency test suite...")
		start_time = time.time()
		
		config = self.test_config['consistency_tests']
		tests_run = 0
		tests_passed = 0
		tests_failed = 0
		critical_failures = []
		performance_metrics = {}
		
		try:
			# Run consistency tests for each scenario
			for scenario in config['scenarios']:
				for run_num in range(config['test_runs_per_scenario']):
					test_name = f"consistency_{scenario}_{run_num}"
					tests_run += 1
					
					try:
						# Create test image
						image_path = self.consistency_tester.create_test_image(scenario)
						
						# Run consistency test
						result = await asyncio.wait_for(
							self.consistency_tester.test_vision_analyzer_consistency(
								image_path, runs=3
							),
							timeout=config['timeout_per_test']
						)
						
						# Evaluate result
						if (result.consistency_score >= 0.7 and 
							result.schema_valid_count == result.total_runs):
							tests_passed += 1
						else:
							tests_failed += 1
							if result.consistency_score < 0.5:
								critical_failures.append(f"Low consistency in {test_name}: {result.consistency_score:.2f}")
						
						# Collect performance metrics
						performance_metrics[test_name] = {
							'consistency_score': result.consistency_score,
							'avg_response_time': result.avg_response_time,
							'schema_compliance': result.schema_valid_count / result.total_runs
						}
						
						# Cleanup
						Path(image_path).unlink(missing_ok=True)
						
					except asyncio.TimeoutError:
						tests_failed += 1
						critical_failures.append(f"Timeout in {test_name}")
					except Exception as e:
						tests_failed += 1
						critical_failures.append(f"Exception in {test_name}: {str(e)}")
			
			# Generate consistency report
			report_data = self.consistency_tester.generate_consistency_report()
			
		except Exception as e:
			self.logger.error(f"Consistency suite failed: {e}")
			critical_failures.append(f"Consistency suite crashed: {str(e)}")
		
		duration = time.time() - start_time
		success_rate = tests_passed / max(tests_run, 1)
		
		return TestSuiteResult(
			suite_name="consistency",
			tests_run=tests_run,
			tests_passed=tests_passed,
			tests_failed=tests_failed,
			success_rate=success_rate,
			duration=duration,
			critical_failures=critical_failures,
			performance_metrics=performance_metrics,
			report_data=report_data if 'report_data' in locals() else {}
		)
	
	async def _run_performance_suite(self) -> TestSuiteResult:
		"""Run performance test suite"""
		self.logger.info("Running performance test suite...")
		start_time = time.time()
		
		config = self.test_config['performance_tests']
		tests_run = 0
		tests_passed = 0
		tests_failed = 0
		critical_failures = []
		performance_metrics = {}
		
		try:
			# Single operation benchmarks
			for analyzer_type in ['vision_analyzer', 'dom_analyzer']:
				test_name = f"benchmark_{analyzer_type}"
				tests_run += 1
				
				try:
					image_path = self.performance_tester.create_test_image('medium')
					
					metrics = await asyncio.wait_for(
						self.performance_tester.benchmark_single_analysis(image_path, analyzer_type),
						timeout=config['timeout_per_test']
					)
					
					# Evaluate performance
					if metrics.success and metrics.response_time < 30.0:
						tests_passed += 1
					else:
						tests_failed += 1
						if metrics.response_time > 45.0:
							critical_failures.append(f"Slow response in {test_name}: {metrics.response_time:.2f}s")
					
					performance_metrics[test_name] = {
						'response_time': metrics.response_time,
						'memory_usage_mb': metrics.memory_peak_mb,
						'success': metrics.success
					}
					
					Path(image_path).unlink(missing_ok=True)
					
				except Exception as e:
					tests_failed += 1
					critical_failures.append(f"Exception in {test_name}: {str(e)}")
			
			# Load tests
			for load_config in config['load_test_configs']:
				test_name = f"load_test_{load_config['concurrent']}x{load_config['total']}"
				tests_run += 1
				
				try:
					result = await asyncio.wait_for(
						self.performance_tester.load_test_analyzer(
							'vision_analyzer',
							load_config['concurrent'],
							load_config['total'],
							load_config['complexity']
						),
						timeout=config['timeout_per_test']
					)
					
					# Evaluate load test
					if result.error_rate < 0.2 and result.avg_response_time < 45.0:
						tests_passed += 1
					else:
						tests_failed += 1
						if result.error_rate > 0.5:
							critical_failures.append(f"High error rate in {test_name}: {result.error_rate:.2%}")
					
					performance_metrics[test_name] = {
						'error_rate': result.error_rate,
						'avg_response_time': result.avg_response_time,
						'throughput_rps': result.throughput_rps
					}
					
				except Exception as e:
					tests_failed += 1
					critical_failures.append(f"Exception in {test_name}: {str(e)}")
			
			# Degradation test
			if config.get('degradation_test_iterations', 0) > 0:
				test_name = "degradation_test"
				tests_run += 1
				
				try:
					result = await asyncio.wait_for(
						self.performance_tester.test_degradation_over_time(
							'vision_analyzer',
							config['degradation_test_iterations']
						),
						timeout=config['timeout_per_test']
					)
					
					# Evaluate degradation
					if (not result.memory_leak_detected and 
						result.degradation_factor < 3.0):
						tests_passed += 1
					else:
						tests_failed += 1
						if result.memory_leak_detected:
							critical_failures.append(f"Memory leak detected in {test_name}")
						if result.degradation_factor > 5.0:
							critical_failures.append(f"Severe degradation in {test_name}: {result.degradation_factor:.2f}x")
					
					performance_metrics[test_name] = {
						'degradation_factor': result.degradation_factor,
						'memory_leak_detected': result.memory_leak_detected,
						'memory_growth_rate': result.memory_growth_rate_mb_per_hour
					}
					
				except Exception as e:
					tests_failed += 1
					critical_failures.append(f"Exception in {test_name}: {str(e)}")
			
			# Generate performance report
			report_data = self.performance_tester.generate_performance_report()
			
		except Exception as e:
			self.logger.error(f"Performance suite failed: {e}")
			critical_failures.append(f"Performance suite crashed: {str(e)}")
		
		duration = time.time() - start_time
		success_rate = tests_passed / max(tests_run, 1)
		
		return TestSuiteResult(
			suite_name="performance",
			tests_run=tests_run,
			tests_passed=tests_passed,
			tests_failed=tests_failed,
			success_rate=success_rate,
			duration=duration,
			critical_failures=critical_failures,
			performance_metrics=performance_metrics,
			report_data=report_data if 'report_data' in locals() else {}
		)
	
	async def _run_reliability_suite(self) -> TestSuiteResult:
		"""Run reliability test suite"""
		self.logger.info("Running reliability test suite...")
		start_time = time.time()
		
		config = self.test_config['reliability_tests']
		tests_run = 0
		tests_passed = 0
		tests_failed = 0
		critical_failures = []
		performance_metrics = {}
		
		try:
			# Fault injection tests
			for fault_scenario in config['fault_injection_scenarios']:
				test_name = f"fault_injection_{fault_scenario}"
				tests_run += 1
				
				try:
					if fault_scenario == 'timeout':
						result = await asyncio.wait_for(
							self.reliability_tester.test_timeout_fault_injection(),
							timeout=config['timeout_per_test']
						)
					elif fault_scenario == 'memory':
						result = await asyncio.wait_for(
							self.reliability_tester.test_memory_fault_injection(),
							timeout=config['timeout_per_test']
						)
					elif fault_scenario == 'connection':
						result = await asyncio.wait_for(
							self.reliability_tester.test_connection_fault_injection(),
							timeout=config['timeout_per_test']
						)
					elif fault_scenario == 'malformed_response':
						result = await asyncio.wait_for(
							self.reliability_tester.test_malformed_response_handling(),
							timeout=config['timeout_per_test']
						)
					else:
						continue
					
					# Evaluate fault injection result
					if result.graceful_degradation and result.error_handling_correct:
						tests_passed += 1
					else:
						tests_failed += 1
						if not result.error_handling_correct:
							critical_failures.append(f"Poor error handling in {test_name}")
					
					performance_metrics[test_name] = {
						'graceful_degradation': result.graceful_degradation,
						'error_handling_correct': result.error_handling_correct,
						'recovery_time': result.recovery_time_seconds
					}
					
				except Exception as e:
					tests_failed += 1
					critical_failures.append(f"Exception in {test_name}: {str(e)}")
			
			# Circuit breaker test
			if config.get('circuit_breaker_tests', False):
				test_name = "circuit_breaker"
				tests_run += 1
				
				try:
					result = await asyncio.wait_for(
						self.reliability_tester.test_circuit_breaker_behavior(),
						timeout=config['timeout_per_test']
					)
					
					# Evaluate circuit breaker
					if result.failures_injected > 0 and result.blocked_requests > 0:
						tests_passed += 1
					else:
						tests_failed += 1
						if result.failures_injected == 0:
							critical_failures.append("Circuit breaker test did not inject failures")
					
					performance_metrics[test_name] = {
						'circuit_opened_correctly': result.circuit_opened_correctly,
						'blocked_requests': result.blocked_requests,
						'failures_injected': result.failures_injected
					}
					
				except Exception as e:
					tests_failed += 1
					critical_failures.append(f"Exception in {test_name}: {str(e)}")
			
			# Multi-tier fallback test
			test_name = "multi_tier_fallback"
			tests_run += 1
			
			try:
				results = await asyncio.wait_for(
					self.reliability_tester.test_multi_tier_fallback_mechanisms(),
					timeout=config['timeout_per_test']
				)
				
				# Evaluate fallback mechanisms
				if results and any(r.fallback_triggered_correctly for r in results):
					tests_passed += 1
				else:
					tests_failed += 1
					critical_failures.append("Multi-tier fallback mechanisms not working")
				
				performance_metrics[test_name] = {
					'fallback_tests_run': len(results),
					'fallback_success_rate': sum(1 for r in results if r.fallback_triggered_correctly) / max(len(results), 1)
				}
				
			except Exception as e:
				tests_failed += 1
				critical_failures.append(f"Exception in {test_name}: {str(e)}")
			
			# Generate reliability report
			report_data = self.reliability_tester.generate_reliability_report()
			
		except Exception as e:
			self.logger.error(f"Reliability suite failed: {e}")
			critical_failures.append(f"Reliability suite crashed: {str(e)}")
		
		duration = time.time() - start_time
		success_rate = tests_passed / max(tests_run, 1)
		
		return TestSuiteResult(
			suite_name="reliability",
			tests_run=tests_run,
			tests_passed=tests_passed,
			tests_failed=tests_failed,
			success_rate=success_rate,
			duration=duration,
			critical_failures=critical_failures,
			performance_metrics=performance_metrics,
			report_data=report_data if 'report_data' in locals() else {}
		)
	
	async def _run_integration_suite(self) -> TestSuiteResult:
		"""Run integration test suite"""
		self.logger.info("Running integration test suite...")
		start_time = time.time()
		
		config = self.test_config['integration_tests']
		tests_run = 0
		tests_passed = 0
		tests_failed = 0
		critical_failures = []
		performance_metrics = {}
		
		try:
			from playwright.async_api import async_playwright
			
			async with async_playwright() as p:
				browser = await p.chromium.launch(headless=True)
				
				try:
					# Basic integration tests for each scenario
					for scenario in config['page_scenarios']:
						test_name = f"integration_{scenario}"
						tests_run += 1
						
						try:
							page = await browser.new_page()
							
							# Create test HTML and serve it
							html_content = self.integration_tester.create_test_html_page(scenario)
							await page.set_content(html_content)
							
							# Run integration test
							result = await asyncio.wait_for(
								self.integration_tester.capture_and_analyze_page(page, test_name),
								timeout=config['timeout_per_test']
							)
							
							# Evaluate integration result
							if (result.screenshot_captured and 
								(result.vision_analysis_success or result.dom_analysis_success)):
								tests_passed += 1
							else:
								tests_failed += 1
								if not result.screenshot_captured:
									critical_failures.append(f"Screenshot capture failed in {test_name}")
								if not result.vision_analysis_success and not result.dom_analysis_success:
									critical_failures.append(f"All analysis methods failed in {test_name}")
							
							performance_metrics[test_name] = {
								'screenshot_captured': result.screenshot_captured,
								'vision_analysis_success': result.vision_analysis_success,
								'dom_analysis_success': result.dom_analysis_success,
								'cross_tier_consistency': result.cross_tier_consistency,
								'total_time': result.total_test_time
							}
							
							await page.close()
							
						except Exception as e:
							tests_failed += 1
							critical_failures.append(f"Exception in {test_name}: {str(e)}")
					
					# Cross-tier comparison tests
					if config.get('cross_tier_comparisons', False):
						test_name = "cross_tier_comparison"
						tests_run += 1
						
						try:
							page = await browser.new_page()
							html_content = self.integration_tester.create_test_html_page('standard')
							await page.set_content(html_content)
							
							comparison = await asyncio.wait_for(
								self.integration_tester.cross_tier_comparison_test(page, "pipeline_comparison"),
								timeout=config['timeout_per_test']
							)
							
							# Evaluate comparison
							if (comparison.processing_time_dom > 0 and 
								comparison.consistency_score >= 0.0):
								tests_passed += 1
							else:
								tests_failed += 1
								critical_failures.append("Cross-tier comparison failed")
							
							performance_metrics[test_name] = {
								'dom_processing_time': comparison.processing_time_dom,
								'vision_processing_time': comparison.processing_time_vision,
								'multi_tier_processing_time': comparison.processing_time_multi_tier,
								'consistency_score': comparison.consistency_score
							}
							
							await page.close()
							
						except Exception as e:
							tests_failed += 1
							critical_failures.append(f"Exception in {test_name}: {str(e)}")
				
				finally:
					await browser.close()
			
			# Generate integration report
			report_data = self.integration_tester.generate_integration_report()
			
		except Exception as e:
			self.logger.error(f"Integration suite failed: {e}")
			critical_failures.append(f"Integration suite crashed: {str(e)}")
		
		duration = time.time() - start_time
		success_rate = tests_passed / max(tests_run, 1)
		
		return TestSuiteResult(
			suite_name="integration",
			tests_run=tests_run,
			tests_passed=tests_passed,
			tests_failed=tests_failed,
			success_rate=success_rate,
			duration=duration,
			critical_failures=critical_failures,
			performance_metrics=performance_metrics,
			report_data=report_data if 'report_data' in locals() else {}
		)
	
	async def _generate_unified_report(self, pipeline_id: str) -> Dict[str, Any]:
		"""Generate unified report across all test suites"""
		
		# Aggregate metrics from all suites
		total_tests = sum(suite.tests_run for suite in self.suite_results)
		total_passed = sum(suite.tests_passed for suite in self.suite_results)
		total_failed = sum(suite.tests_failed for suite in self.suite_results)
		overall_success_rate = total_passed / max(total_tests, 1)
		total_duration = sum(suite.duration for suite in self.suite_results)
		
		# Collect all critical failures
		all_critical_failures = []
		for suite in self.suite_results:
			all_critical_failures.extend([f"{suite.suite_name}: {failure}" for failure in suite.critical_failures])
		
		# Performance analysis
		performance_analysis = {}
		for suite in self.suite_results:
			if suite.performance_metrics:
				performance_analysis[suite.suite_name] = {
					'test_count': len(suite.performance_metrics),
					'metrics': suite.performance_metrics
				}
		
		# Success rate by suite
		suite_success_rates = {}
		for suite in self.suite_results:
			suite_success_rates[suite.suite_name] = suite.success_rate
		
		# Generate overall assessment
		overall_assessment = self._generate_overall_assessment(overall_success_rate, all_critical_failures)
		
		unified_report = {
			'pipeline_id': pipeline_id,
			'timestamp': datetime.now().isoformat(),
			'summary': {
				'total_tests': total_tests,
				'total_passed': total_passed,
				'total_failed': total_failed,
				'overall_success_rate': overall_success_rate,
				'total_duration_seconds': total_duration,
				'suites_tested': len(self.suite_results)
			},
			'suite_results': [asdict(suite) for suite in self.suite_results],
			'suite_success_rates': suite_success_rates,
			'critical_failures': all_critical_failures,
			'performance_analysis': performance_analysis,
			'overall_assessment': overall_assessment,
			'recommendations': self._generate_pipeline_recommendations(),
			'test_environment': {
				'python_version': '3.11+',
				'test_framework': 'pytest + asyncio',
				'browser_engine': 'playwright + chromium',
				'vision_models': ['moondream2', 'dom_analyzer', 'multi_tier']
			}
		}
		
		return unified_report
	
	def _generate_overall_assessment(self, success_rate: float, critical_failures: List[str]) -> Dict[str, Any]:
		"""Generate overall assessment of system health"""
		
		if success_rate >= 0.95 and len(critical_failures) == 0:
			health_status = "EXCELLENT"
			health_description = "Vision system is performing exceptionally well with no critical issues."
		elif success_rate >= 0.85 and len(critical_failures) <= 2:
			health_status = "GOOD"
			health_description = "Vision system is performing well with minor issues that should be addressed."
		elif success_rate >= 0.70 and len(critical_failures) <= 5:
			health_status = "FAIR"
			health_description = "Vision system has moderate issues that require attention."
		elif success_rate >= 0.50:
			health_status = "POOR"
			health_description = "Vision system has significant issues that need immediate attention."
		else:
			health_status = "CRITICAL"
			health_description = "Vision system is in critical condition and requires immediate intervention."
		
		# Readiness assessment
		if health_status in ["EXCELLENT", "GOOD"]:
			production_readiness = "READY"
		elif health_status == "FAIR":
			production_readiness = "READY_WITH_MONITORING"
		else:
			production_readiness = "NOT_READY"
		
		return {
			'health_status': health_status,
			'health_description': health_description,
			'production_readiness': production_readiness,
			'success_rate': success_rate,
			'critical_issue_count': len(critical_failures),
			'assessment_timestamp': datetime.now().isoformat()
		}
	
	def _generate_pipeline_recommendations(self) -> List[str]:
		"""Generate recommendations based on all test suite results"""
		recommendations = []
		
		if not self.suite_results:
			return ["No test results available for recommendations"]
		
		# Analyze success rates by suite
		failed_suites = [suite for suite in self.suite_results if suite.success_rate < 0.8]
		if failed_suites:
			suite_names = [suite.suite_name for suite in failed_suites]
			recommendations.append(f"HIGH: Test suites failing: {', '.join(suite_names)}. Focus on these areas immediately.")
		
		# Analyze critical failures
		total_critical = sum(len(suite.critical_failures) for suite in self.suite_results)
		if total_critical > 10:
			recommendations.append("CRITICAL: Large number of critical failures detected. System requires immediate attention.")
		elif total_critical > 5:
			recommendations.append("HIGH: Multiple critical failures detected. Review and address these issues.")
		
		# Performance analysis
		performance_issues = []
		for suite in self.suite_results:
			if suite.suite_name == "performance" and suite.success_rate < 0.7:
				performance_issues.append("Performance tests failing")
			if suite.duration > 300:  # 5 minutes
				performance_issues.append(f"{suite.suite_name} suite taking too long")
		
		if performance_issues:
			recommendations.append(f"MEDIUM: Performance concerns: {', '.join(performance_issues)}")
		
		# Reliability analysis
		reliability_suite = next((s for s in self.suite_results if s.suite_name == "reliability"), None)
		if reliability_suite and reliability_suite.success_rate < 0.8:
			recommendations.append("HIGH: Reliability issues detected. System may not be fault-tolerant.")
		
		# Integration analysis
		integration_suite = next((s for s in self.suite_results if s.suite_name == "integration"), None)
		if integration_suite and integration_suite.success_rate < 0.7:
			recommendations.append("HIGH: Integration issues detected. End-to-end workflows may be unreliable.")
		
		# Consistency analysis
		consistency_suite = next((s for s in self.suite_results if s.suite_name == "consistency"), None)
		if consistency_suite and consistency_suite.success_rate < 0.8:
			recommendations.append("MEDIUM: Consistency issues detected. Output quality may vary.")
		
		# Overall system assessment
		overall_success = sum(suite.tests_passed for suite in self.suite_results) / max(sum(suite.tests_run for suite in self.suite_results), 1)
		if overall_success >= 0.9:
			recommendations.append("EXCELLENT: Vision system is ready for production use.")
		elif overall_success >= 0.8:
			recommendations.append("GOOD: Vision system is mostly ready for production with monitoring.")
		elif overall_success >= 0.7:
			recommendations.append("FAIR: Vision system needs improvement before production use.")
		else:
			recommendations.append("POOR: Vision system requires significant work before production use.")
		
		return recommendations
	
	async def _save_pipeline_result(self, pipeline_result: PipelineTestResult, unified_report: Dict[str, Any]):
		"""Save pipeline results and reports to files"""
		
		# Save pipeline result
		pipeline_file = Path(f"{pipeline_result.pipeline_id}_result.json")
		with open(pipeline_file, 'w') as f:
			json.dump(asdict(pipeline_result), f, indent=2)
		
		# Save unified report
		report_file = Path(f"{pipeline_result.pipeline_id}_unified_report.json")
		with open(report_file, 'w') as f:
			json.dump(unified_report, f, indent=2)
		
		# Save summary for quick reference
		summary_file = Path(f"{pipeline_result.pipeline_id}_summary.txt")
		with open(summary_file, 'w') as f:
			f.write(f"Vision Test Pipeline Summary - {pipeline_result.pipeline_id}\n")
			f.write("=" * 60 + "\n\n")
			f.write(f"Overall Success Rate: {pipeline_result.overall_success_rate:.1%}\n")
			f.write(f"Total Duration: {pipeline_result.total_duration:.1f} seconds\n")
			f.write(f"Suites Passed: {len(pipeline_result.test_suites_passed)}/{len(pipeline_result.test_suites_run)}\n")
			f.write(f"Critical Issues: {len(pipeline_result.critical_issues_found)}\n\n")
			
			if pipeline_result.critical_issues_found:
				f.write("Critical Issues:\n")
				for issue in pipeline_result.critical_issues_found:
					f.write(f"- {issue}\n")
				f.write("\n")
			
			f.write("Recommendations:\n")
			for rec in pipeline_result.recommendations:
				f.write(f"- {rec}\n")
		
		self.logger.info(f"Results saved to: {pipeline_file}, {report_file}, {summary_file}")
	
	async def run_quick_health_check(self) -> Dict[str, Any]:
		"""Run a quick health check with minimal tests"""
		self.logger.info("Running quick health check...")
		
		# Simplified test configuration for health check
		original_config = self.test_config.copy()
		
		self.test_config['consistency_tests']['test_runs_per_scenario'] = 2
		self.test_config['consistency_tests']['scenarios'] = ['login']
		self.test_config['performance_tests']['load_test_configs'] = [
			{'concurrent': 2, 'total': 4, 'complexity': 'simple'}
		]
		self.test_config['performance_tests']['degradation_test_iterations'] = 5
		self.test_config['reliability_tests']['fault_injection_scenarios'] = ['timeout', 'connection']
		self.test_config['integration_tests']['page_scenarios'] = ['standard']
		self.test_config['integration_tests']['cross_tier_comparisons'] = False
		
		try:
			# Run quick pipeline
			result = await self.run_complete_pipeline("health_check_" + str(int(time.time())))
			
			# Generate health check summary
			health_summary = {
				'overall_health': result.overall_success_rate,
				'critical_issues': len(result.critical_issues_found),
				'test_duration': result.total_duration,
				'suites_passed': len(result.test_suites_passed),
				'suites_total': len(result.test_suites_run),
				'status': 'HEALTHY' if result.overall_success_rate >= 0.8 else 'UNHEALTHY',
				'recommendations': result.recommendations[:3],  # Top 3 recommendations
				'timestamp': datetime.now().isoformat()
			}
			
			return health_summary
			
		finally:
			# Restore original configuration
			self.test_config = original_config
	
	def get_pipeline_history(self) -> List[Dict[str, Any]]:
		"""Get history of pipeline runs"""
		return [asdict(result) for result in self.pipeline_results]


class TestVisionPipeline:
	"""Pytest test class for vision pipeline testing"""
	
	@pytest.fixture(autouse=True)
	async def setup_pipeline(self):
		"""Set up test pipeline"""
		self.pipeline = VisionTestPipeline()
		yield
		# Cleanup handled by pipeline itself
	
	@pytest.mark.asyncio
	async def test_quick_health_check(self):
		"""Test quick health check functionality"""
		health_result = await self.pipeline.run_quick_health_check()
		
		# Health check should complete
		assert 'overall_health' in health_result, "Health check missing overall_health"
		assert 'status' in health_result, "Health check missing status"
		assert 'test_duration' in health_result, "Health check missing duration"
		
		# Should complete in reasonable time
		assert health_result['test_duration'] < 300, f"Health check too slow: {health_result['test_duration']:.1f}s"
		
		# Should provide recommendations
		assert 'recommendations' in health_result, "Health check missing recommendations"
		assert len(health_result['recommendations']) > 0, "Should have recommendations"
	
	@pytest.mark.asyncio
	@pytest.mark.slow
	async def test_complete_pipeline_run(self):
		"""Test complete pipeline execution (slow test)"""
		# This is marked as slow and would typically be run separately
		result = await self.pipeline.run_complete_pipeline("test_complete_pipeline")
		
		# Pipeline should complete
		assert result.pipeline_id.startswith("test_complete_pipeline"), "Pipeline ID mismatch"
		assert result.total_duration > 0, "Pipeline should take some time"
		assert len(result.test_suites_run) > 0, "Should run some test suites"
		
		# Should generate reports
		assert len(result.report_files_generated) > 0, "Should generate report files"
		
		# Should provide assessment
		assert len(result.recommendations) > 0, "Should provide recommendations"
	
	@pytest.mark.asyncio  
	async def test_pipeline_configuration(self):
		"""Test pipeline configuration management"""
		# Test default configuration
		assert self.pipeline.test_config['consistency_tests']['enabled'], "Consistency tests should be enabled"
		assert self.pipeline.test_config['performance_tests']['enabled'], "Performance tests should be enabled"
		assert self.pipeline.test_config['reliability_tests']['enabled'], "Reliability tests should be enabled"
		assert self.pipeline.test_config['integration_tests']['enabled'], "Integration tests should be enabled"
		
		# Test configuration modification
		original_scenarios = self.pipeline.test_config['consistency_tests']['scenarios'].copy()
		self.pipeline.test_config['consistency_tests']['scenarios'] = ['test_scenario']
		
		assert self.pipeline.test_config['consistency_tests']['scenarios'] == ['test_scenario']
		
		# Restore original
		self.pipeline.test_config['consistency_tests']['scenarios'] = original_scenarios
	
	async def test_pipeline_history_tracking(self):
		"""Test pipeline history tracking"""
		# Initially no history
		history = self.pipeline.get_pipeline_history()
		initial_count = len(history)
		
		# Run health check to add to history
		await self.pipeline.run_quick_health_check()
		
		# Should have one more entry
		updated_history = self.pipeline.get_pipeline_history()
		assert len(updated_history) == initial_count + 1, "History should track pipeline runs"
		
		# Latest entry should be the health check
		latest = updated_history[-1]
		assert 'health_check' in latest['pipeline_id'], "Latest entry should be health check"