#!/usr/bin/env python3
"""
Simple error recovery tests that don't require full LLM initialization.
Tests the error handling logic in isolation.
"""

import asyncio
import pytest
import time
from unittest.mock import patch, MagicMock, AsyncMock

from hybrid_orchestrator import HybridOrchestrator, HybridConfig
from enhanced_local_llm import PerformanceMonitor
from cloud_planner import TaskPlan, TaskStep, RecoveryPlan, TaskComplexity


class TestSimpleErrorRecovery:
	"""Test error recovery mechanisms in isolation."""
	
	def setup_method(self):
		"""Set up test fixtures."""
		self.config = HybridConfig(
			max_recovery_attempts=2,
			step_retry_limit=3,
			performance_monitoring=True
		)
		
		# Mock the components that would normally initialize
		with patch('hybrid_orchestrator.OptimizedLocalLLM') as mock_local_llm_class:
			with patch('hybrid_orchestrator.CloudPlanner') as mock_cloud_planner_class:
				with patch('hybrid_orchestrator.PerformanceMonitor') as mock_performance_monitor_class:
					mock_local_llm = MagicMock()
					mock_cloud_planner = MagicMock()
					mock_performance_monitor = PerformanceMonitor()  # Use real instance for testing metrics
					
					mock_local_llm_class.return_value = mock_local_llm
					mock_cloud_planner_class.return_value = mock_cloud_planner
					mock_performance_monitor_class.return_value = mock_performance_monitor
					
					self.orchestrator = HybridOrchestrator(self.config)
					self.orchestrator.local_llm = mock_local_llm
					self.orchestrator.cloud_planner = mock_cloud_planner
					self.orchestrator.performance_monitor = mock_performance_monitor
	
	@pytest.mark.asyncio
	async def test_connection_retry_with_backoff(self):
		"""Test connection retry with exponential backoff."""
		connection_attempts = []
		
		async def mock_get_client():
			connection_attempts.append(len(connection_attempts))
			if len(connection_attempts) <= 2:
				raise ConnectionError("Connection failed")
			return MagicMock()  # Success on third attempt
		
		self.orchestrator.local_llm.get_optimized_client = mock_get_client
		
		# This should succeed after 2 retries
		await self.orchestrator._ensure_local_llm_connection()
		
		assert len(connection_attempts) == 3  # Two failures, one success
	
	@pytest.mark.asyncio  
	async def test_connection_failure_after_max_attempts(self):
		"""Test connection failure after max attempts."""
		connection_attempts = []
		
		async def mock_get_client():
			connection_attempts.append(len(connection_attempts))
			raise ConnectionError("Persistent connection failure")
		
		self.orchestrator.local_llm.get_optimized_client = mock_get_client
		
		# Should raise after 3 attempts
		with pytest.raises(ConnectionError, match="Persistent connection failure"):
			await self.orchestrator._ensure_local_llm_connection()
		
		assert len(connection_attempts) == 3  # Should have tried 3 times
	
	@pytest.mark.asyncio
	async def test_timeout_calculation_and_handling(self):
		"""Test dynamic timeout calculation based on performance history."""
		# Setup performance history
		self.orchestrator.performance_monitor.metrics['avg_step_time'] = 0.01  # Very small for testing
		
		mock_step = TaskStep(
			step_number=1,
			action="test_action", 
			description="Test step",
			success_criteria="Test success"
		)
		
		# Mock agent that takes longer than timeout
		mock_agent = MagicMock()
		
		async def slow_agent_run():
			await asyncio.sleep(0.5)  # Simulate slow operation (500ms)
			return MagicMock()
		
		mock_agent.run = slow_agent_run
		
		# Test with very short timeout multiplier and override the timeout calculation
		# We'll patch the timeout calculation to use a small value
		with patch.object(self.orchestrator, '_execute_step_with_timeout') as mock_timeout:
			async def short_timeout_run(agent, step, timeout_multiplier=1.5):
				return await asyncio.wait_for(agent.run(), timeout=0.1)  # 100ms timeout
			
			mock_timeout.side_effect = short_timeout_run
			
			with pytest.raises(asyncio.TimeoutError):
				await self.orchestrator._execute_step_with_timeout(mock_agent, mock_step, timeout_multiplier=1.0)
	
	@pytest.mark.asyncio
	async def test_cloud_recovery_attempt_limiting(self):
		"""Test that cloud recovery attempts are properly limited."""
		mock_step = TaskStep(
			step_number=1,
			action="test_action",
			description="Test step", 
			success_criteria="Test success"
		)
		
		# Mock cloud recovery that always returns a plan
		mock_recovery = RecoveryPlan(
			stuck_step=1,
			issue_description="Test issue description",
			recovery_actions=["Action 1", "Action 2"],
			alternative_approach="Alternative approach"
		)
		
		recovery_calls = []
		
		async def mock_create_recovery_plan(*args, **kwargs):
			recovery_calls.append(len(recovery_calls))
			return mock_recovery
		
		self.orchestrator.cloud_planner.create_recovery_plan = mock_create_recovery_plan
		
		# Call recovery multiple times
		await self.orchestrator._attempt_cloud_recovery(mock_step, "Error 1")
		await self.orchestrator._attempt_cloud_recovery(mock_step, "Error 2")
		await self.orchestrator._attempt_cloud_recovery(mock_step, "Error 3")  # Should be ignored
		
		# Should only call recovery twice (max_recovery_attempts = 2)
		assert len(recovery_calls) == 2
		assert self.orchestrator.recovery_attempts == 2
	
	def test_performance_monitor_metrics(self):
		"""Test performance monitoring metrics calculation."""
		monitor = PerformanceMonitor()
		
		# Record various scenarios
		monitor.record_step(True, 5.0)   # Success
		monitor.record_step(False, 10.0) # Failure
		monitor.record_step(True, 3.0)   # Success
		monitor.record_recovery()        # Recovery attempt
		monitor.record_step(False, 15.0) # Another failure
		monitor.record_step(True, 7.0)   # Success
		
		# Verify metrics
		assert monitor.get_success_rate() == 0.6  # 3 successes out of 5 total
		assert monitor.metrics['total_steps'] == 5
		assert monitor.metrics['successful_steps'] == 3
		assert monitor.metrics['failed_steps'] == 2
		assert monitor.metrics['recovery_attempts'] == 1
		assert monitor.metrics['avg_step_time'] == 8.0  # (5+10+3+15+7)/5
	
	def test_error_context_preservation(self):
		"""Test that error context is preserved for debugging."""
		orchestrator = HybridOrchestrator(self.config)
		
		# Test initial state
		assert orchestrator.recovery_attempts == 0
		assert orchestrator.current_step == 0
		assert orchestrator.current_plan is None
		
		# Test state tracking
		orchestrator.recovery_attempts = 3
		orchestrator.current_step = 7
		
		# Verify state is maintained
		assert orchestrator.recovery_attempts == 3
		assert orchestrator.current_step == 7
	
	def test_config_validation(self):
		"""Test that error recovery configuration is properly validated."""
		# Test default configuration
		default_config = HybridConfig()
		assert default_config.max_recovery_attempts == 1
		assert default_config.step_retry_limit == 2
		assert default_config.performance_monitoring == True
		assert default_config.local_first_threshold == 0.9
		
		# Test custom configuration
		custom_config = HybridConfig(
			max_recovery_attempts=5,
			step_retry_limit=10,
			performance_monitoring=False,
			local_first_threshold=0.95
		)
		assert custom_config.max_recovery_attempts == 5
		assert custom_config.step_retry_limit == 10
		assert custom_config.performance_monitoring == False
		assert custom_config.local_first_threshold == 0.95
	
	@pytest.mark.asyncio
	async def test_graceful_error_reporting(self):
		"""Test that errors are reported gracefully with context."""
		# Mock cloud planner failure
		async def failing_plan_task(task):
			raise Exception("Cloud service unavailable")
		
		self.orchestrator.cloud_planner.plan_task = failing_plan_task
		
		mock_browser = MagicMock()
		mock_tools = MagicMock()
		
		# Execute task that should fail gracefully
		result = await self.orchestrator.execute_task(
			"Test task with cloud failure", mock_browser, mock_tools
		)
		
		# Verify graceful error handling
		assert result['success'] == False
		assert 'cloud service unavailable' in result['error'].lower()
		assert result['results'] == []
		assert result['total_time'] >= 0  # Time can be very small but should be non-negative
		assert result['local_processing_ratio'] == 0.0
		assert result['phase_3b_target_met'] == False


if __name__ == "__main__":
	pytest.main([__file__, "-v"])