#!/usr/bin/env python3
"""
Test error handling and recovery mechanisms for the hybrid orchestrator.
Validates robustness for complex multi-step automation workflows.
"""

import asyncio
import pytest
import time
from unittest.mock import patch, MagicMock, AsyncMock

from hybrid_orchestrator import HybridOrchestrator, HybridConfig
from enhanced_local_llm import LocalLLMConfig, PerformanceMonitor
from cloud_planner import CloudPlannerConfig, TaskPlan, TaskStep, RecoveryPlan, TaskComplexity


class TestErrorHandlingRecovery:
	"""Test error handling and recovery mechanisms."""
	
	def setup_method(self):
		"""Set up test fixtures."""
		self.config = HybridConfig(
			max_recovery_attempts=2,
			step_retry_limit=3,
			performance_monitoring=True,
			local_first_threshold=0.9,
			cloud_sees_content=False,
			log_cloud_usage=True
		)
		self.orchestrator = HybridOrchestrator(self.config)
	
	@pytest.mark.asyncio
	async def test_step_timeout_recovery(self):
		"""Test recovery from step timeouts."""
		# Mock browser and tools
		mock_browser = MagicMock()
		mock_tools = MagicMock()
		
		# Mock task plan with timeout-prone step
		mock_step = TaskStep(
			step_number=1,
			action="navigate_to_url",
			description="Navigate to slow-loading website",
			success_criteria="Website loaded successfully",
			expected_duration=5  # Short timeout to trigger recovery
		)
		
		mock_plan = TaskPlan(
			original_task="Test timeout handling",
			complexity=TaskComplexity.SIMPLE,
			total_steps=1,
			steps=[mock_step],
			estimated_duration=10
		)
		
		# Mock cloud planner to return our test plan
		with patch.object(self.orchestrator.cloud_planner, 'plan_task') as mock_plan_task:
			mock_plan_task.return_value = mock_plan
			
			# Mock local LLM to timeout on first attempt, succeed on retry
			attempts = []
			
			async def mock_agent_run():
				attempts.append(len(attempts))
				if len(attempts) == 1:
					# First attempt - timeout
					await asyncio.sleep(6)  # Longer than timeout
					raise asyncio.TimeoutError("Operation timed out")
				else:
					# Retry - succeed
					mock_result = MagicMock()
					mock_result.all_model_outputs = [
						MagicMock(message="Website loaded successfully", actions=['navigate'])
					]
					return mock_result
			
			mock_agent = MagicMock()
			mock_agent.run = mock_agent_run
			
			with patch.object(self.orchestrator.local_llm, 'create_optimized_agent') as mock_create_agent:
				mock_create_agent.return_value = mock_agent
				
				# Execute task
				result = await self.orchestrator.execute_task(
					"Navigate to slow website", mock_browser, mock_tools
				)
				
				# Verify timeout was handled and recovery succeeded
				assert result['success'] == True
				assert len(attempts) >= 2  # Should have retried
				assert result['results'][0]['retries'] >= 1
	
	@pytest.mark.asyncio
	async def test_llm_connection_failure_recovery(self):
		"""Test recovery from local LLM connection failures."""
		mock_browser = MagicMock()
		mock_tools = MagicMock()
		
		# Mock task plan
		mock_step = TaskStep(
			step_number=1,
			action="click_element",
			description="Click on element",
			success_criteria="Element clicked successfully"
		)
		
		mock_plan = TaskPlan(
			original_task="Test LLM connection failure",
			complexity=TaskComplexity.SIMPLE,
			total_steps=1,
			steps=[mock_step],
			estimated_duration=5
		)
		
		with patch.object(self.orchestrator.cloud_planner, 'plan_task') as mock_plan_task:
			mock_plan_task.return_value = mock_plan
			
			# Mock connection failures then success
			connection_attempts = []
			
			async def mock_get_client():
				connection_attempts.append(len(connection_attempts))
				if len(connection_attempts) <= 2:
					raise ConnectionError("llama.cpp server not responding")
				return MagicMock()  # Successful connection
			
			with patch.object(self.orchestrator.local_llm, 'get_optimized_client', side_effect=mock_get_client):
				
				# Mock successful agent creation after connection recovery
				async def mock_agent_run():
					mock_result = MagicMock()
					mock_result.all_model_outputs = [
						MagicMock(message="Element clicked successfully", actions=['click'])
					]
					return mock_result
				
				mock_agent = MagicMock()
				mock_agent.run = mock_agent_run
				
				with patch.object(self.orchestrator.local_llm, 'create_optimized_agent') as mock_create_agent:
					mock_create_agent.return_value = mock_agent
					
					# Execute task
					result = await self.orchestrator.execute_task(
						"Click on element", mock_browser, mock_tools
					)
					
					# Verify connection recovery worked
					assert result['success'] == True
					assert len(connection_attempts) >= 3  # Should have retried connections
	
	@pytest.mark.asyncio
	async def test_cloud_recovery_mechanism(self):
		"""Test cloud-assisted recovery when local execution fails."""
		mock_browser = MagicMock()
		mock_tools = MagicMock()
		
		# Mock complex step that fails locally
		mock_step = TaskStep(
			step_number=1,
			action="complex_navigation",
			description="Navigate complex multi-step process",
			success_criteria="Complex navigation completed"
		)
		
		mock_plan = TaskPlan(
			original_task="Test cloud recovery assistance",
			complexity=TaskComplexity.COMPLEX,
			total_steps=1,
			steps=[mock_step],
			estimated_duration=15
		)
		
		with patch.object(self.orchestrator.cloud_planner, 'plan_task') as mock_plan_task:
			mock_plan_task.return_value = mock_plan
			
			# Mock local LLM failing initially
			local_attempts = []
			
			async def mock_agent_run():
				local_attempts.append(len(local_attempts))
				if len(local_attempts) <= 2:
					# Fail initially to trigger cloud recovery
					mock_result = MagicMock()
					mock_result.all_model_outputs = [
						MagicMock(message="Navigation failed", actions=[])
					]
					return mock_result
				else:
					# Success after cloud recovery
					mock_result = MagicMock()
					mock_result.all_model_outputs = [
						MagicMock(message="Complex navigation completed", actions=['navigate', 'click'])
					]
					return mock_result
			
			mock_agent = MagicMock()
			mock_agent.run = mock_agent_run
			
			with patch.object(self.orchestrator.local_llm, 'create_optimized_agent') as mock_create_agent:
				mock_create_agent.return_value = mock_agent
				
				# Mock cloud recovery plan
				mock_recovery = RecoveryPlan(
					original_step=mock_step.step_number,
					alternative_approach="Break down into smaller steps",
					recovery_actions=[
						"Try clicking elements more slowly",
						"Wait for page load between actions",
						"Use alternative selectors"
					],
					confidence=0.8
				)
				
				with patch.object(self.orchestrator.cloud_planner, 'create_recovery_plan') as mock_recovery_plan:
					mock_recovery_plan.return_value = mock_recovery
					
					# Execute task
					result = await self.orchestrator.execute_task(
						"Navigate complex process", mock_browser, mock_tools
					)
					
					# Verify cloud recovery was used
					assert result['success'] == True
					assert len(local_attempts) >= 3  # Should have retried after cloud assistance
					assert self.orchestrator.recovery_attempts >= 1  # Cloud recovery was called
	
	@pytest.mark.asyncio
	async def test_max_recovery_attempts_limit(self):
		"""Test that recovery attempts respect the configured limit."""
		# Configure lower limits for faster testing
		self.config.max_recovery_attempts = 1
		self.config.step_retry_limit = 2
		orchestrator = HybridOrchestrator(self.config)
		
		mock_browser = MagicMock()
		mock_tools = MagicMock()
		
		# Mock step that always fails
		mock_step = TaskStep(
			step_number=1,
			action="impossible_action",
			description="Action that always fails",
			success_criteria="This will never succeed"
		)
		
		mock_plan = TaskPlan(
			original_task="Test max recovery attempts",
			complexity=TaskComplexity.SIMPLE,
			total_steps=1,
			steps=[mock_step],
			estimated_duration=5
		)
		
		with patch.object(orchestrator.cloud_planner, 'plan_task') as mock_plan_task:
			mock_plan_task.return_value = mock_plan
			
			# Mock always-failing agent
			async def mock_failing_agent_run():
				raise Exception("Persistent failure")
			
			mock_agent = MagicMock()
			mock_agent.run = mock_failing_agent_run
			
			with patch.object(orchestrator.local_llm, 'create_optimized_agent') as mock_create_agent:
				mock_create_agent.return_value = mock_agent
				
				# Mock cloud recovery (should be called only once due to limit)
				recovery_calls = []
				
				async def mock_recovery_plan(*args):
					recovery_calls.append(len(recovery_calls))
					return RecoveryPlan(
						original_step=1,
						alternative_approach="Alternative that also fails",
						recovery_actions=["Try different approach"],
						confidence=0.5
					)
				
				with patch.object(orchestrator.cloud_planner, 'create_recovery_plan', side_effect=mock_recovery_plan):
					
					# Execute task
					result = await orchestrator.execute_task(
						"Impossible task", mock_browser, mock_tools
					)
					
					# Verify limits were respected
					assert result['success'] == False
					assert orchestrator.recovery_attempts <= self.config.max_recovery_attempts
					assert len(recovery_calls) <= self.config.max_recovery_attempts
	
	@pytest.mark.asyncio
	async def test_performance_degradation_detection(self):
		"""Test detection and handling of performance degradation."""
		mock_browser = MagicMock()
		mock_tools = MagicMock()
		
		# Mock multiple steps to test performance monitoring
		steps = [
			TaskStep(
				step_number=i,
				action=f"action_{i}",
				description=f"Description {i}",
				success_criteria=f"Result {i}"
			) for i in range(1, 4)
		]
		
		mock_plan = TaskPlan(
			original_task="Test performance monitoring",
			complexity=TaskComplexity.MODERATE,
			total_steps=3,
			steps=steps,
			estimated_duration=30
		)
		
		with patch.object(self.orchestrator.cloud_planner, 'plan_task') as mock_plan_task:
			mock_plan_task.return_value = mock_plan
			
			# Mock performance monitor to detect degradation
			step_times = []
			
			async def mock_agent_run():
				# Simulate increasing execution times (performance degradation)
				current_step = len(step_times) + 1
				execution_time = current_step * 10.0  # 10s, 20s, 30s
				
				start = time.time()
				step_times.append(execution_time)
				
				# Simulate work
				await asyncio.sleep(0.1)
				
				mock_result = MagicMock()
				mock_result.all_model_outputs = [
					MagicMock(message=f"Step {current_step} completed", actions=[f'action_{current_step}'])
				]
				return mock_result
			
			mock_agent = MagicMock()
			mock_agent.run = mock_agent_run
			
			with patch.object(self.orchestrator.local_llm, 'create_optimized_agent') as mock_create_agent:
				mock_create_agent.return_value = mock_agent
				
				# Mock performance monitor to trigger cloud help
				with patch.object(self.orchestrator.performance_monitor, 'should_request_cloud_help') as mock_should_help:
					mock_should_help.side_effect = [False, True, True]  # Trigger help after first step
					
					# Mock cloud recovery
					with patch.object(self.orchestrator.cloud_planner, 'create_recovery_plan') as mock_recovery:
						mock_recovery.return_value = RecoveryPlan(
							original_step=2,
							alternative_approach="Optimize for performance",
							recovery_actions=["Use simpler selectors", "Reduce timeout"],
							confidence=0.9
						)
						
						# Execute task
						result = await self.orchestrator.execute_task(
							"Multi-step performance test", mock_browser, mock_tools
						)
						
						# Verify performance monitoring triggered recovery
						assert result['success'] == True
						assert mock_recovery.call_count >= 1  # Cloud help was requested
	
	def test_error_monitoring_metrics(self):
		"""Test that error monitoring collects proper metrics."""
		monitor = PerformanceMonitor()
		
		# Record various scenarios
		monitor.record_step(True, 5.0)   # Success
		monitor.record_step(False, 10.0) # Failure
		monitor.record_step(True, 3.0)   # Success
		monitor.record_recovery()        # Recovery attempt
		monitor.record_step(False, 15.0) # Another failure
		
		# Check metrics calculation
		success_rate = monitor.get_success_rate()
		assert success_rate == 0.5  # 2 successes out of 4 attempts
		
		assert monitor.metrics['total_steps'] == 4
		assert monitor.metrics['successful_steps'] == 2
		assert monitor.metrics['failed_steps'] == 2
		assert monitor.metrics['recovery_attempts'] == 1
		assert monitor.metrics['avg_step_time'] == 8.25  # (5+10+3+15)/4
	
	def test_error_context_preservation(self):
		"""Test that error context is preserved for debugging."""
		config = HybridConfig(log_cloud_usage=True)
		orchestrator = HybridOrchestrator(config)
		
		# Test that orchestrator maintains error state
		assert orchestrator.recovery_attempts == 0
		assert orchestrator.current_step == 0
		assert orchestrator.current_plan is None
		
		# Test error state tracking
		orchestrator.recovery_attempts = 2
		orchestrator.current_step = 5
		
		assert orchestrator.recovery_attempts == 2
		assert orchestrator.current_step == 5
	
	@pytest.mark.asyncio
	async def test_graceful_degradation(self):
		"""Test graceful degradation when both local and cloud systems fail."""
		# Configure minimal retries for faster testing
		config = HybridConfig(
			max_recovery_attempts=1,
			step_retry_limit=1
		)
		orchestrator = HybridOrchestrator(config)
		
		mock_browser = MagicMock()
		mock_tools = MagicMock()
		
		# Mock cloud planner failure
		with patch.object(orchestrator.cloud_planner, 'plan_task') as mock_plan:
			mock_plan.side_effect = Exception("Cloud service unavailable")
			
			# Execute task
			result = await orchestrator.execute_task(
				"Task when cloud fails", mock_browser, mock_tools
			)
			
			# Should fail gracefully
			assert result['success'] == False
			assert 'cloud service unavailable' in str(result).lower() or result['results'] == []
	
	def test_error_recovery_configuration(self):
		"""Test that error recovery can be properly configured."""
		# Test default configuration
		default_config = HybridConfig()
		assert default_config.max_recovery_attempts == 1
		assert default_config.step_retry_limit == 2
		assert default_config.performance_monitoring == True
		
		# Test custom configuration
		custom_config = HybridConfig(
			max_recovery_attempts=5,
			step_retry_limit=10,
			performance_monitoring=False
		)
		assert custom_config.max_recovery_attempts == 5
		assert custom_config.step_retry_limit == 10
		assert custom_config.performance_monitoring == False


if __name__ == "__main__":
	pytest.main([__file__, "-v"])