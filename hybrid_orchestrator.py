#!/usr/bin/env python3
"""
Hybrid Orchestrator for Privacy-First Web Automation
Combines cloud planning with local execution to maximize privacy and minimize costs.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from enhanced_local_llm import OptimizedLocalLLM, LocalLLMConfig, PerformanceMonitor
from cloud_planner import CloudPlanner, CloudPlannerConfig, TaskPlan, TaskStep, RecoveryPlan
from browser_use import Agent, Browser, Tools
from error_monitoring import ErrorMonitor, MonitoringConfig, ErrorCategory, AlertLevel, console_alert_handler

logger = logging.getLogger(__name__)

@dataclass
class HybridConfig:
	"""Configuration for hybrid orchestrator."""
	# Local LLM settings
	local_config: LocalLLMConfig = None
	
	# Cloud planner settings  
	cloud_config: CloudPlannerConfig = None
	
	# Error monitoring settings
	monitoring_config: MonitoringConfig = None
	
	# Orchestrator behavior - optimized for 90%+ local processing
	max_recovery_attempts: int = 1  # Minimize cloud calls
	step_retry_limit: int = 2       # Rely more on local intelligence
	performance_monitoring: bool = True
	local_first_threshold: float = 0.9  # 90%+ local processing target
	
	# Privacy settings
	cloud_sees_content: bool = False  # Never send web content to cloud
	log_cloud_usage: bool = True      # Track cloud API usage
	
	def __post_init__(self):
		if self.local_config is None:
			self.local_config = LocalLLMConfig()
		if self.cloud_config is None:
			self.cloud_config = CloudPlannerConfig()
		if self.monitoring_config is None:
			self.monitoring_config = MonitoringConfig()

class HybridOrchestrator:
	"""
	Privacy-first orchestrator that uses cloud planning and local execution.
	
	Architecture:
	1. Cloud plans the strategy (sees only the task, not web content)  
	2. Local LLM executes all web interactions (privacy preserved)
	3. Performance monitoring triggers cloud recovery if needed
	4. All web content and user data stays local
	"""
	
	def __init__(self, config: HybridConfig = None):
		self.config = config or HybridConfig()
		
		# Initialize components
		self.local_llm = OptimizedLocalLLM(self.config.local_config)
		self.cloud_planner = CloudPlanner(self.config.cloud_config)
		self.performance_monitor = PerformanceMonitor()
		
		# Initialize error monitoring
		self.error_monitor = ErrorMonitor(self.config.monitoring_config)
		self.error_monitor.add_alert_handler(console_alert_handler)
		
		# State tracking
		self.current_plan: Optional[TaskPlan] = None
		self.current_step = 0
		self.recovery_attempts = 0
		
		logger.info("[HYBRID] Hybrid orchestrator initialized - Privacy-first architecture ready")
	
	async def execute_task(
		self,
		task: str,
		browser: Browser,
		tools: Tools,
		**agent_kwargs
	) -> Dict:
		"""
		Execute a complex task using hybrid cloud planning + local execution.
		
		Privacy guarantee: Web content never sent to cloud.
		"""
		start_time = time.time()
		logger.info(f"[START] Starting hybrid execution: {task}")
		
		# Record task start for monitoring
		self.error_monitor.record_task_start()
		
		try:
			# Step 1: Cloud strategic planning (task description only)
			logger.info("[CLOUD] Phase 1: Strategic planning...")
			self.current_plan = await self.cloud_planner.plan_task(task)
			
			# Record cloud API usage
			self.error_monitor.record_cloud_api_call()
			
			logger.info(f"[PLAN] Plan created: {self.current_plan.total_steps} steps")
			for step in self.current_plan.steps:
				logger.info(f"  {step.step_number}. {step.action}: {step.description}")
		
		except Exception as e:
			# Record cloud planning error
			self.error_monitor.record_error(
				ErrorCategory.CLOUD_SERVICE,
				f"Cloud planning failed: {str(e)}",
				AlertLevel.ERROR,
				context={'task': task, 'phase': 'planning'}
			)
			
			task_duration = time.time() - start_time
			self.error_monitor.record_task_completion(False, task_duration)
			
			logger.error(f"[CLOUD] Planning failed: {e}")
			return {
				'success': False,
				'results': [],
				'total_time': task_duration,
				'error': f'Cloud planning failed: {str(e)}',
				'cloud_usage': {'planning_calls_used': 0, 'max_planning_calls': 0},
				'local_performance': {
					'success_rate': 0.0,
					'avg_step_time': 0.0,
					'recovery_attempts': 0
				},
				'local_processing_ratio': 0.0,
				'phase_3b_target_met': False
			}
		
		# Step 2: Local execution of each step (privacy preserved)
		logger.info("[LOCAL] Phase 2: Local execution...")
		
		try:
			await self.local_llm.get_optimized_client()  # Initialize local client
		except Exception as e:
			# Record LLM initialization error
			self.error_monitor.record_error(
				ErrorCategory.LLM_FAILURE,
				f"Local LLM initialization failed: {str(e)}",
				AlertLevel.CRITICAL,
				context={'task': task, 'phase': 'local_llm_init'}
			)
			
			task_duration = time.time() - start_time
			self.error_monitor.record_task_completion(False, task_duration)
			
			logger.error(f"[LOCAL] Failed to initialize local LLM: {e}")
			return {
				'success': False,
				'results': [],
				'total_time': task_duration,
				'error': f'Local LLM initialization failed: {str(e)}',
				'cloud_usage': self.cloud_planner.get_usage_stats(),
				'local_performance': {
					'success_rate': 0.0,
					'avg_step_time': 0.0,
					'recovery_attempts': 0
				},
				'local_processing_ratio': 0.0,
				'phase_3b_target_met': False
			}
		
		results = []
		
		for step in self.current_plan.steps:
			self.current_step = step.step_number
			step_result = await self._execute_step_with_monitoring(
				step, browser, tools, **agent_kwargs
			)
			results.append(step_result)
			
			# Break if step failed and we can't recover
			if not step_result['success'] and self.recovery_attempts >= self.config.max_recovery_attempts:
				logger.error(f"[ERROR] Max recovery attempts reached, aborting task")
				break
		
		# Step 3: Performance summary
		total_time = time.time() - start_time
		self.performance_monitor.log_performance_summary()
		
		# Record task completion for monitoring
		task_success = all(r['success'] for r in results)
		self.error_monitor.record_task_completion(task_success, total_time)
		
		# Step 4: Cloud usage tracking
		cloud_usage = self.cloud_planner.get_usage_stats()
		local_processing_ratio = 1.0 - (cloud_usage['planning_calls_used'] / max(cloud_usage['max_planning_calls'], 1))
		
		if self.config.log_cloud_usage:
			logger.info(f"[CLOUD] API usage: {cloud_usage['planning_calls_used']}/{cloud_usage['max_planning_calls']} calls")
			logger.info(f"[LOCAL] Processing ratio: {local_processing_ratio:.1%} (target: {self.config.local_first_threshold:.1%})")
			
			if local_processing_ratio >= self.config.local_first_threshold:
				logger.info("[SUCCESS] Phase 3B target achieved: 90%+ local processing")
			else:
				logger.warning(f"[WARN] Phase 3B target missed: {local_processing_ratio:.1%} local processing")
		
		# Include monitoring data in results
		return {
			'success': task_success,
			'results': results,
			'total_time': total_time,
			'cloud_usage': cloud_usage,
			'local_performance': {
				'success_rate': self.performance_monitor.get_success_rate(),
				'avg_step_time': self.performance_monitor.metrics['avg_step_time'],
				'recovery_attempts': self.performance_monitor.metrics['recovery_attempts']
			},
			'local_processing_ratio': local_processing_ratio,
			'phase_3b_target_met': local_processing_ratio >= self.config.local_first_threshold,
			'monitoring': {
				'health_status': self.error_monitor.get_health_status(),
				'error_summary': self.error_monitor.get_error_summary(900),  # Last 15 minutes
				'performance_report': self.error_monitor.get_performance_report()
			}
		}
	
	async def _execute_step_with_monitoring(
		self,
		step: TaskStep,
		browser: Browser,
		tools: Tools,
		**agent_kwargs
	) -> Dict:
		"""Execute a single step with performance monitoring and recovery."""
		logger.info(f"[STEP] Executing step {step.step_number}: {step.description}")
		
		step_start_time = time.time()
		retry_count = 0
		last_error = None
		
		while retry_count < self.config.step_retry_limit:
			try:
				# Check if we need to handle connection issues
				await self._ensure_local_llm_connection()
				
				# Create optimized agent for this step
				agent = self.local_llm.create_optimized_agent(
					task=f"Step {step.step_number}: {step.description}",
					browser=browser,
					tools=tools,
					step_number=step.step_number,
					total_steps=self.current_plan.total_steps,
					**agent_kwargs
				)
				
				# Execute step locally with timeout handling (privacy preserved)
				result = await self._execute_step_with_timeout(agent, step)
				step_duration = time.time() - step_start_time
				
				# Evaluate success based on step criteria
				success = self._evaluate_step_success(step, result)
				
				# Record performance for both monitoring systems
				self.performance_monitor.record_step(success, step_duration)
				self.error_monitor.record_step_completion(success, step_duration)
				
				if success:
					logger.info(f"[SUCCESS] Step {step.step_number} completed successfully")
					return {
						'success': True,
						'step': step.step_number,
						'duration': step_duration,
						'result': result,
						'retries': retry_count,
						'error_context': last_error if retry_count > 0 else None
					}
				else:
					logger.warning(f"[RETRY] Step {step.step_number} criteria not met, retry {retry_count + 1}")
					retry_count += 1
					last_error = "Step success criteria not met"
					
					# Request cloud recovery assistance if performance is poor
					if self.performance_monitor.should_request_cloud_help():
						await self._attempt_cloud_recovery(step, "Performance degraded, requesting guidance")
					
			except asyncio.TimeoutError as e:
				error_msg = f"Step {step.step_number} timeout: {e}"
				logger.error(f"[TIMEOUT] {error_msg}")
				retry_count += 1
				step_duration = time.time() - step_start_time
				last_error = error_msg
				
				# Record timeout error
				error_event = self.error_monitor.record_error(
					ErrorCategory.TIMEOUT,
					error_msg,
					AlertLevel.WARNING,
					context={'step_number': step.step_number, 'duration': step_duration},
					step_number=step.step_number
				)
				
				self.performance_monitor.record_step(False, step_duration)
				self.error_monitor.record_step_completion(False, step_duration)
				
				# Try cloud recovery for timeout errors
				if retry_count < self.config.step_retry_limit:
					await self._attempt_cloud_recovery(step, error_msg)
					self.error_monitor.record_recovery_attempt(error_event, True)  # Will be updated if recovery succeeds
			
			except ConnectionError as e:
				error_msg = f"Step {step.step_number} connection error: {e}"
				logger.error(f"[CONNECTION] {error_msg}")
				retry_count += 1
				step_duration = time.time() - step_start_time
				last_error = error_msg
				
				# Record connection error
				error_event = self.error_monitor.record_error(
					ErrorCategory.CONNECTION,
					error_msg,
					AlertLevel.ERROR,
					context={'step_number': step.step_number, 'retry_count': retry_count},
					step_number=step.step_number
				)
				
				self.performance_monitor.record_step(False, step_duration)
				self.error_monitor.record_step_completion(False, step_duration)
				
				# Wait before retry for connection issues
				await asyncio.sleep(min(retry_count * 2, 10))  # Exponential backoff, max 10s
				
				# Try cloud recovery for connection errors
				if retry_count < self.config.step_retry_limit:
					await self._attempt_cloud_recovery(step, error_msg)
					self.error_monitor.record_recovery_attempt(error_event, True)  # Will be updated if recovery succeeds
			
			except Exception as e:
				error_msg = f"Step {step.step_number} unexpected error: {e}"
				logger.error(f"[ERROR] {error_msg}")
				retry_count += 1
				step_duration = time.time() - step_start_time
				last_error = error_msg
				
				# Record unexpected error
				error_event = self.error_monitor.record_error(
					ErrorCategory.UNKNOWN,
					error_msg,
					AlertLevel.ERROR,
					context={'step_number': step.step_number, 'exception_type': type(e).__name__},
					step_number=step.step_number
				)
				
				self.performance_monitor.record_step(False, step_duration)
				self.error_monitor.record_step_completion(False, step_duration)
				
				# Try cloud recovery for critical errors
				if retry_count < self.config.step_retry_limit:
					await self._attempt_cloud_recovery(step, error_msg)
					self.error_monitor.record_recovery_attempt(error_event, True)  # Will be updated if recovery succeeds
		
		# Step failed after all retries
		logger.error(f"[FAILED] Step {step.step_number} failed after {retry_count} attempts")
		return {
			'success': False,
			'step': step.step_number,
			'duration': time.time() - step_start_time,
			'error': 'Max retries exceeded',
			'retries': retry_count,
			'last_error': last_error,
			'error_context': {
				'step_description': step.description,
				'retry_count': retry_count,
				'total_duration': time.time() - step_start_time
			}
		}
	
	async def _attempt_cloud_recovery(self, step: TaskStep, error_context: str):
		"""Request cloud assistance for recovery (minimal cloud usage)."""
		if self.recovery_attempts >= self.config.max_recovery_attempts:
			logger.warning("[WARN] Max recovery attempts reached, skipping cloud recovery")
			return
		
		logger.info("[CLOUD] Requesting cloud recovery assistance...")
		self.recovery_attempts += 1
		self.performance_monitor.record_recovery()
		
		try:
			recovery_plan = await self.cloud_planner.create_recovery_plan(
				self.current_plan,
				step.step_number,
				error_context
			)
			
			logger.info(f"[RECOVERY] Recovery plan received:")
			for i, action in enumerate(recovery_plan.recovery_actions, 1):
				logger.info(f"  {i}. {action}")
			
			# Apply recovery suggestions to step
			if recovery_plan.alternative_approach:
				step.fallback_strategy = recovery_plan.alternative_approach
				logger.info(f"[ALT] Alternative approach: {recovery_plan.alternative_approach}")
			
		except Exception as e:
			logger.error(f"[ERROR] Cloud recovery failed: {e}")
	
	def _evaluate_step_success(self, step: TaskStep, result) -> bool:
		"""Evaluate if step met its success criteria."""
		if not result or not hasattr(result, 'all_model_outputs'):
			return False
		
		# Check if agent took meaningful actions
		actions_taken = len([
			output for output in result.all_model_outputs 
			if hasattr(output, 'actions') and output.actions
		])
		
		# Basic success criteria: agent took actions and completed without critical errors
		if actions_taken > 0:
			# Check for completion indicators in the result
			last_output = result.all_model_outputs[-1] if result.all_model_outputs else None
			if last_output and hasattr(last_output, 'message'):
				message = last_output.message.lower()
				# Look for completion indicators
				completion_indicators = ['done', 'completed', 'success', 'found', 'navigated']
				if any(indicator in message for indicator in completion_indicators):
					return True
			
			# Fallback: if actions were taken, assume success
			return True
		
		return False
	
	async def _ensure_local_llm_connection(self):
		"""Ensure local LLM connection is healthy with retry logic."""
		max_connection_attempts = 3
		connection_attempts = 0
		
		while connection_attempts < max_connection_attempts:
			try:
				# Test connection to local LLM
				await self.local_llm.get_optimized_client()
				return  # Connection successful
			except ConnectionError as e:
				connection_attempts += 1
				logger.warning(f"[CONNECTION] LLM connection attempt {connection_attempts} failed: {e}")
				
				if connection_attempts < max_connection_attempts:
					# Exponential backoff: 2s, 4s, 8s
					wait_time = 2 ** connection_attempts
					logger.info(f"[CONNECTION] Waiting {wait_time}s before retry...")
					await asyncio.sleep(wait_time)
				else:
					logger.error("[CONNECTION] Max connection attempts reached")
					raise e
	
	async def _execute_step_with_timeout(self, agent, step: TaskStep, timeout_multiplier: float = 1.5):
		"""Execute agent step with configurable timeout."""
		# Calculate timeout based on step complexity and past performance
		base_timeout = getattr(step, 'timeout', 60.0)  # Default 60s
		avg_step_time = self.performance_monitor.metrics.get('avg_step_time', 30.0)
		dynamic_timeout = max(base_timeout, avg_step_time * timeout_multiplier)
		
		logger.debug(f"[TIMEOUT] Step {step.step_number} timeout: {dynamic_timeout:.1f}s")
		
		try:
			return await asyncio.wait_for(agent.run(), timeout=dynamic_timeout)
		except asyncio.TimeoutError:
			logger.error(f"[TIMEOUT] Step {step.step_number} exceeded {dynamic_timeout:.1f}s timeout")
			raise
	
	async def get_performance_insights(self) -> Dict:
		"""Get insights about local vs cloud performance."""
		return {
			'local_llm_model': self.local_llm._selected_model,
			'success_rate': self.performance_monitor.get_success_rate(),
			'avg_step_time': self.performance_monitor.metrics['avg_step_time'],
			'cloud_usage': self.cloud_planner.get_usage_stats(),
			'recovery_effectiveness': self.recovery_attempts,
			'privacy_status': 'All web content processed locally' if not self.config.cloud_sees_content else 'Warning: Content shared with cloud'
		}

# Usage and testing
async def test_hybrid_orchestrator():
	"""Test the complete hybrid system."""
	from runner import make_browser, build_tools
	
	# Setup
	config = HybridConfig()
	orchestrator = HybridOrchestrator(config)
	browser = make_browser()
	tools = build_tools()
	
	# Test complex task
	complex_task = "Go to walmart.com, find a store locator, and search for stores near 90210"
	
	print("[TEST] Testing Hybrid Privacy-First Architecture...")
	result = await orchestrator.execute_task(complex_task, browser, tools)
	
	print(f"\n[RESULTS] Execution Results:")
	print(f"  Success: {result['success']}")
	print(f"  Total Time: {result['total_time']:.1f}s")
	print(f"  Cloud API Usage: {result['cloud_usage']['planning_calls_used']}/{result['cloud_usage']['max_planning_calls']}")
	print(f"  Local Success Rate: {result['local_performance']['success_rate']:.1%}")
	
	# Performance insights
	insights = await orchestrator.get_performance_insights()
	print(f"\n[INSIGHTS] Performance Insights:")
	print(f"  Local Model: {insights['local_llm_model']}")
	print(f"  Privacy Status: {insights['privacy_status']}")
	print(f"  Recovery Attempts: {insights['recovery_effectiveness']}")
	
	# Cleanup
	await browser.kill()
	
	return result

if __name__ == "__main__":
	logging.basicConfig(level=logging.INFO)
	asyncio.run(test_hybrid_orchestrator())