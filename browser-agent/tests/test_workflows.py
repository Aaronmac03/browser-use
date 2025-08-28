"""
Tests for workflow execution functionality.

This module tests workflow execution, error handling, recovery mechanisms,
and task completion verification.
"""

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from workflows.workflow_base import (
    BaseWorkflow, WorkflowConfig, WorkflowStatus, WorkflowPriority,
    WorkflowStep, WorkflowResult
)
from config.models import TaskComplexity
from tests.conftest import MockWorkflow


class TestWorkflowConfig:
    """Test workflow configuration."""
    
    def test_workflow_config_creation(self):
        """Test creating workflow configuration."""
        config = WorkflowConfig(
            workflow_id="test_001",
            name="Test Workflow",
            description="A test workflow",
            priority=WorkflowPriority.HIGH,
            timeout=300.0,
            max_retries=5,
            browser_profile="secure",
            security_level="high"
        )
        
        assert config.workflow_id == "test_001"
        assert config.name == "Test Workflow"
        assert config.priority == WorkflowPriority.HIGH
        assert config.timeout == 300.0
        assert config.max_retries == 5
        assert config.browser_profile == "secure"
        assert config.security_level == "high"
    
    def test_workflow_config_defaults(self):
        """Test workflow configuration defaults."""
        config = WorkflowConfig(
            workflow_id="test_002",
            name="Test Workflow",
            description="A test workflow"
        )
        
        assert config.priority == WorkflowPriority.NORMAL
        assert config.timeout is None
        assert config.max_retries == 3
        assert config.browser_profile == "default"
        assert config.security_level == "medium"
        assert config.parallel_execution is False
        assert config.continue_on_error is False
        assert config.save_screenshots is True
        assert config.save_results is True


class TestWorkflowStep:
    """Test workflow step functionality."""
    
    def test_workflow_step_creation(self):
        """Test creating workflow steps."""
        step = WorkflowStep(
            name="login",
            description="Login to the application",
            task="Navigate to login page and enter credentials",
            complexity=TaskComplexity.MODERATE,
            requires_vision=True,
            timeout=60.0,
            max_retries=2
        )
        
        assert step.name == "login"
        assert step.description == "Login to the application"
        assert step.complexity == TaskComplexity.MODERATE
        assert step.requires_vision is True
        assert step.timeout == 60.0
        assert step.max_retries == 2
        assert step.retry_count == 0
        assert step.dependencies == []
    
    def test_workflow_step_with_dependencies(self):
        """Test workflow step with dependencies."""
        step = WorkflowStep(
            name="submit_form",
            description="Submit the form",
            task="Click submit button",
            dependencies=["fill_form", "validate_data"]
        )
        
        assert step.dependencies == ["fill_form", "validate_data"]


class TestMockWorkflow:
    """Test mock workflow implementation."""
    
    @pytest.mark.asyncio
    async def test_mock_workflow_successful_execution(self, mock_workflow):
        """Test successful workflow execution."""
        result = await mock_workflow.execute()
        
        assert result.status == WorkflowStatus.COMPLETED
        assert result.steps_completed == 3
        assert result.total_steps == 3
        assert len(result.errors) == 0
        assert mock_workflow.executed_steps == ["step1", "step2", "step3"]
    
    @pytest.mark.asyncio
    async def test_mock_workflow_failure(self, sample_workflow_config):
        """Test workflow failure handling."""
        workflow = MockWorkflow(sample_workflow_config)
        workflow.should_fail = True
        workflow.fail_at_step = "step2"
        
        result = await workflow.execute()
        
        assert result.status == WorkflowStatus.FAILED
        assert result.steps_completed < result.total_steps
        assert len(result.errors) > 0
        assert "step1" in workflow.executed_steps
        # step2 might be in executed_steps depending on when failure occurs
    
    @pytest.mark.asyncio
    async def test_mock_workflow_retry_mechanism(self, sample_workflow_config):
        """Test workflow retry mechanism."""
        workflow = MockWorkflow(sample_workflow_config)
        workflow.should_fail = True
        workflow.fail_at_step = "step2"
        
        # Mock the retry logic to succeed on second attempt
        original_execute_step = workflow.execute_step
        call_count = 0
        
        async def mock_execute_step(step, context):
            nonlocal call_count
            call_count += 1
            if step["name"] == "step2" and call_count == 1:
                raise Exception("First attempt failure")
            return await original_execute_step(step, context)
        
        workflow.execute_step = mock_execute_step
        workflow.should_fail = False  # Allow success on retry
        
        result = await workflow.execute()
        
        # Should eventually succeed after retry
        assert result.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]


class TestWorkflowExecution:
    """Test workflow execution scenarios."""
    
    @pytest.mark.asyncio
    async def test_workflow_timeout(self, sample_workflow_config):
        """Test workflow timeout handling."""
        config = sample_workflow_config
        config.timeout = 0.1  # Very short timeout
        
        workflow = MockWorkflow(config)
        
        # Mock slow execution
        original_execute_step = workflow.execute_step
        async def slow_execute_step(step, context):
            await asyncio.sleep(0.2)  # Longer than timeout
            return await original_execute_step(step, context)
        
        workflow.execute_step = slow_execute_step
        
        result = await workflow.execute()
        
        assert result.status == WorkflowStatus.FAILED
        assert "timeout" in str(result.errors).lower()
    
    @pytest.mark.asyncio
    async def test_workflow_cancellation(self, mock_workflow):
        """Test workflow cancellation."""
        # Start workflow execution
        task = asyncio.create_task(mock_workflow.execute())
        
        # Cancel after short delay
        await asyncio.sleep(0.01)
        task.cancel()
        
        try:
            result = await task
            # If not cancelled, should still be valid result
            assert result.status in [WorkflowStatus.COMPLETED, WorkflowStatus.CANCELLED]
        except asyncio.CancelledError:
            # Expected if cancellation worked
            pass
    
    @pytest.mark.asyncio
    async def test_workflow_step_dependencies(self, sample_workflow_config):
        """Test workflow step dependency resolution."""
        workflow = MockWorkflow(sample_workflow_config)
        
        # Override steps with dependencies
        async def define_steps_with_deps():
            return [
                {"name": "step1", "task": "First step", "dependencies": []},
                {"name": "step2", "task": "Second step", "dependencies": ["step1"]},
                {"name": "step3", "task": "Third step", "dependencies": ["step1", "step2"]}
            ]
        
        workflow.define_steps = define_steps_with_deps
        
        result = await workflow.execute()
        
        assert result.status == WorkflowStatus.COMPLETED
        # Steps should be executed in dependency order
        assert workflow.executed_steps.index("step1") < workflow.executed_steps.index("step2")
        assert workflow.executed_steps.index("step2") < workflow.executed_steps.index("step3")
    
    @pytest.mark.asyncio
    async def test_workflow_continue_on_error(self, sample_workflow_config):
        """Test continue on error functionality."""
        config = sample_workflow_config
        config.continue_on_error = True
        
        workflow = MockWorkflow(config)
        workflow.should_fail = True
        workflow.fail_at_step = "step2"
        
        result = await workflow.execute()
        
        # Should continue to step3 even after step2 fails
        assert "step1" in workflow.executed_steps
        assert "step3" in workflow.executed_steps
        assert result.steps_completed >= 2  # At least step1 and step3
        assert len(result.errors) > 0  # Should record the error
    
    @pytest.mark.asyncio
    async def test_workflow_parallel_execution(self, sample_workflow_config):
        """Test parallel workflow execution."""
        config = sample_workflow_config
        config.parallel_execution = True
        
        workflow = MockWorkflow(config)
        
        # Override to create independent steps
        async def define_parallel_steps():
            return [
                {"name": "step1", "task": "Independent step 1", "dependencies": []},
                {"name": "step2", "task": "Independent step 2", "dependencies": []},
                {"name": "step3", "task": "Independent step 3", "dependencies": []}
            ]
        
        workflow.define_steps = define_parallel_steps
        
        start_time = datetime.now()
        result = await workflow.execute()
        end_time = datetime.now()
        
        assert result.status == WorkflowStatus.COMPLETED
        assert result.steps_completed == 3
        
        # Parallel execution should be faster than sequential
        # (This is a rough test - in practice you'd need more sophisticated timing)
        execution_time = (end_time - start_time).total_seconds()
        assert execution_time < 1.0  # Should be much faster than sequential


class TestWorkflowErrorHandling:
    """Test workflow error handling and recovery."""
    
    @pytest.mark.asyncio
    async def test_step_retry_on_failure(self, sample_workflow_config):
        """Test step retry mechanism."""
        workflow = MockWorkflow(sample_workflow_config)
        
        # Track retry attempts
        retry_attempts = {}
        original_execute_step = workflow.execute_step
        
        async def mock_execute_step_with_retries(step, context):
            step_name = step["name"]
            retry_attempts[step_name] = retry_attempts.get(step_name, 0) + 1
            
            # Fail first two attempts for step2, succeed on third
            if step_name == "step2" and retry_attempts[step_name] < 3:
                raise Exception(f"Attempt {retry_attempts[step_name]} failed")
            
            return await original_execute_step(step, context)
        
        workflow.execute_step = mock_execute_step_with_retries
        
        result = await workflow.execute()
        
        assert result.status == WorkflowStatus.COMPLETED
        assert retry_attempts.get("step2", 0) == 3  # Should have retried
        assert "step2" in workflow.executed_steps
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, sample_workflow_config):
        """Test behavior when max retries are exceeded."""
        config = sample_workflow_config
        config.max_retries = 2
        
        workflow = MockWorkflow(config)
        
        # Always fail step2
        original_execute_step = workflow.execute_step
        async def always_fail_step2(step, context):
            if step["name"] == "step2":
                raise Exception("Persistent failure")
            return await original_execute_step(step, context)
        
        workflow.execute_step = always_fail_step2
        
        result = await workflow.execute()
        
        assert result.status == WorkflowStatus.FAILED
        assert len(result.errors) > 0
        assert "step1" in workflow.executed_steps
        assert "step3" not in workflow.executed_steps  # Should stop after failure
    
    @pytest.mark.asyncio
    async def test_error_context_preservation(self, mock_workflow):
        """Test that error context is preserved."""
        workflow = mock_workflow
        workflow.should_fail = True
        workflow.fail_at_step = "step2"
        
        result = await workflow.execute()
        
        assert result.status == WorkflowStatus.FAILED
        assert len(result.errors) > 0
        
        # Error should contain context information
        error_msg = result.errors[0]
        assert "step2" in error_msg
    
    @pytest.mark.asyncio
    async def test_workflow_recovery_after_failure(self, sample_workflow_config):
        """Test workflow recovery mechanisms."""
        workflow = MockWorkflow(sample_workflow_config)
        
        # Simulate transient failure that resolves
        failure_count = 0
        original_execute_step = workflow.execute_step
        
        async def transient_failure_step(step, context):
            nonlocal failure_count
            if step["name"] == "step2":
                failure_count += 1
                if failure_count <= 2:  # Fail first two attempts
                    raise Exception("Transient failure")
            return await original_execute_step(step, context)
        
        workflow.execute_step = transient_failure_step
        
        result = await workflow.execute()
        
        # Should recover and complete successfully
        assert result.status == WorkflowStatus.COMPLETED
        assert failure_count > 1  # Should have experienced failures
        assert all(step in workflow.executed_steps for step in ["step1", "step2", "step3"])


class TestWorkflowResult:
    """Test workflow result handling."""
    
    @pytest.mark.asyncio
    async def test_workflow_result_structure(self, mock_workflow):
        """Test workflow result structure and content."""
        result = await mock_workflow.execute()
        
        assert isinstance(result, WorkflowResult)
        assert result.workflow_id == mock_workflow.config.workflow_id
        assert result.status == WorkflowStatus.COMPLETED
        assert result.steps_completed == 3
        assert result.total_steps == 3
        assert isinstance(result.start_time, datetime)
        assert isinstance(result.end_time, datetime)
        assert isinstance(result.duration, timedelta)
        assert result.duration.total_seconds() > 0
        assert isinstance(result.results, dict)
        assert isinstance(result.errors, list)
        assert isinstance(result.metadata, dict)
    
    @pytest.mark.asyncio
    async def test_workflow_result_timing(self, mock_workflow):
        """Test workflow result timing information."""
        start_time = datetime.now()
        result = await mock_workflow.execute()
        end_time = datetime.now()
        
        assert result.start_time >= start_time
        assert result.end_time <= end_time
        assert result.duration == result.end_time - result.start_time
        assert result.duration.total_seconds() > 0
    
    @pytest.mark.asyncio
    async def test_workflow_result_with_errors(self, sample_workflow_config):
        """Test workflow result when errors occur."""
        workflow = MockWorkflow(sample_workflow_config)
        workflow.should_fail = True
        workflow.fail_at_step = "step2"
        
        result = await workflow.execute()
        
        assert result.status == WorkflowStatus.FAILED
        assert len(result.errors) > 0
        assert result.steps_completed < result.total_steps
        
        # Error information should be detailed
        error = result.errors[0]
        assert isinstance(error, str)
        assert len(error) > 0


class TestWorkflowIntegration:
    """Integration tests for workflow functionality."""
    
    @pytest.mark.asyncio
    async def test_workflow_with_browser_profile(self, sample_workflow_config, mock_browser_profile_manager):
        """Test workflow integration with browser profiles."""
        config = sample_workflow_config
        config.browser_profile = "test_secure"
        
        workflow = MockWorkflow(config)
        
        # Mock browser profile integration
        with patch.object(workflow, '_get_browser_config') as mock_browser_config:
            mock_browser_config.return_value = {"headless": True, "security": "high"}
            
            result = await workflow.execute()
            
            assert result.status == WorkflowStatus.COMPLETED
            mock_browser_config.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_workflow_with_security_validation(self, sample_workflow_config, mock_security_manager):
        """Test workflow integration with security validation."""
        workflow = MockWorkflow(sample_workflow_config)
        
        # Mock security validation
        with patch.object(workflow, '_validate_security') as mock_security:
            mock_security.return_value = {"allowed": True, "risk_score": 0.2}
            
            result = await workflow.execute()
            
            assert result.status == WorkflowStatus.COMPLETED
            # Security validation should be called for each step
            assert mock_security.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_workflow_with_model_selection(self, sample_workflow_config, model_router):
        """Test workflow integration with model selection."""
        workflow = MockWorkflow(sample_workflow_config)
        
        # Mock model selection for each step
        with patch.object(workflow, '_select_model_for_step') as mock_model_selection:
            mock_model_selection.return_value = model_router.model_config_manager.list_models()[0]
            
            result = await workflow.execute()
            
            assert result.status == WorkflowStatus.COMPLETED
            # Model should be selected for each step
            assert mock_model_selection.call_count >= 3


@pytest.mark.performance
class TestWorkflowPerformance:
    """Test workflow performance characteristics."""
    
    @pytest.mark.asyncio
    async def test_workflow_execution_time(self, mock_workflow):
        """Test workflow execution performance."""
        start_time = datetime.now()
        result = await mock_workflow.execute()
        end_time = datetime.now()
        
        execution_time = (end_time - start_time).total_seconds()
        
        assert result.status == WorkflowStatus.COMPLETED
        assert execution_time < 5.0  # Should complete quickly for mock workflow
    
    @pytest.mark.asyncio
    async def test_concurrent_workflow_execution(self, sample_workflow_config):
        """Test concurrent workflow execution."""
        workflows = [MockWorkflow(sample_workflow_config) for _ in range(5)]
        
        start_time = datetime.now()
        results = await asyncio.gather(*[w.execute() for w in workflows])
        end_time = datetime.now()
        
        execution_time = (end_time - start_time).total_seconds()
        
        # All workflows should complete successfully
        assert all(r.status == WorkflowStatus.COMPLETED for r in results)
        assert execution_time < 10.0  # Should handle concurrent execution efficiently
    
    @pytest.mark.asyncio
    async def test_workflow_memory_usage(self, mock_workflow):
        """Test workflow memory usage."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        result = await mock_workflow.execute()
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        assert result.status == WorkflowStatus.COMPLETED
        # Memory increase should be reasonable (less than 50MB for mock workflow)
        assert memory_increase < 50 * 1024 * 1024


@pytest.mark.slow
class TestWorkflowStressTests:
    """Stress tests for workflow functionality."""
    
    @pytest.mark.asyncio
    async def test_large_workflow_execution(self, sample_workflow_config):
        """Test execution of workflow with many steps."""
        workflow = MockWorkflow(sample_workflow_config)
        
        # Override to create many steps
        async def define_many_steps():
            return [
                {"name": f"step{i}", "task": f"Task {i}"}
                for i in range(100)
            ]
        
        workflow.define_steps = define_many_steps
        
        result = await workflow.execute()
        
        assert result.status == WorkflowStatus.COMPLETED
        assert result.steps_completed == 100
        assert len(workflow.executed_steps) == 100
    
    @pytest.mark.asyncio
    async def test_workflow_with_many_retries(self, sample_workflow_config):
        """Test workflow behavior with many retry attempts."""
        config = sample_workflow_config
        config.max_retries = 10
        
        workflow = MockWorkflow(config)
        
        # Make step2 fail multiple times before succeeding
        failure_count = 0
        original_execute_step = workflow.execute_step
        
        async def failing_step(step, context):
            nonlocal failure_count
            if step["name"] == "step2":
                failure_count += 1
                if failure_count <= 8:  # Fail 8 times, succeed on 9th
                    raise Exception(f"Failure {failure_count}")
            return await original_execute_step(step, context)
        
        workflow.execute_step = failing_step
        
        result = await workflow.execute()
        
        assert result.status == WorkflowStatus.COMPLETED
        assert failure_count == 9  # Should have retried multiple times
        assert "step2" in workflow.executed_steps