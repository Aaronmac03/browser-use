#!/usr/bin/env python3
"""
Tests for cloud planning call limits and fallback behavior.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import sys
import os

# Add the browser-use directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cloud_planner import CloudPlanner, CloudPlannerConfig, TaskComplexity, TaskPlan, TaskStep


class TestCloudPlanningCap:
    """Test suite for cloud planning call limits."""
    
    def test_cloud_planner_config_defaults(self):
        """Test that CloudPlannerConfig has correct defaults."""
        config = CloudPlannerConfig()
        assert config.model == "o3"
        assert config.max_planning_calls == 2
        assert config.planning_timeout == 30
        assert config.enable_recovery is True
    
    @pytest.mark.asyncio
    async def test_planning_cap_triggers_fallback(self):
        """Test that reaching max planning calls triggers fallback without cloud calls."""
        config = CloudPlannerConfig(max_planning_calls=1)
        planner = CloudPlanner(config)
        
        # Simulate that we've already used our quota
        planner.planning_calls_used = 1
        
        # Mock the cloud client to track if it gets called
        cloud_calls = []
        
        def mock_get_cloud_client():
            mock_client = MagicMock()
            async def mock_ainvoke(*args, **kwargs):
                cloud_calls.append(args)
                return MagicMock()
            mock_client.ainvoke = mock_ainvoke
            return mock_client
        
        planner._get_cloud_client = mock_get_cloud_client
        
        # Try to plan a task - should use fallback
        task = "Navigate to example.com"
        plan = await planner.plan_task(task)
        
        # Verify no cloud calls were made
        assert len(cloud_calls) == 0
        
        # Verify we got a fallback plan
        assert plan.original_task == task
        assert plan.complexity in [TaskComplexity.SIMPLE, TaskComplexity.MODERATE, TaskComplexity.COMPLEX]
        assert len(plan.steps) > 0
        assert "Fallback plan" in plan.privacy_notes
    
    @pytest.mark.asyncio
    async def test_recovery_cap_triggers_fallback(self):
        """Test that reaching max planning calls prevents recovery planning."""
        config = CloudPlannerConfig(max_planning_calls=1)
        planner = CloudPlanner(config)
        
        # Use up the quota
        planner.planning_calls_used = 1
        
        # Mock original plan
        original_plan = TaskPlan(
            original_task="Test task",
            complexity=TaskComplexity.SIMPLE,
            total_steps=1,
            steps=[TaskStep(step_number=1, action="test", description="test", success_criteria="test")],
            estimated_duration=30
        )
        
        # Mock cloud client to track calls
        cloud_calls = []
        
        def mock_get_cloud_client():
            mock_client = MagicMock()
            async def mock_ainvoke(*args, **kwargs):
                cloud_calls.append(args)
                return MagicMock()
            mock_client.ainvoke = mock_ainvoke
            return mock_client
        
        planner._get_cloud_client = mock_get_cloud_client
        
        # Try to create recovery plan - should use fallback
        recovery = await planner.create_recovery_plan(original_plan, 1, "Test error")
        
        # Verify no cloud calls were made
        assert len(cloud_calls) == 0
        
        # Verify we got a fallback recovery plan
        assert recovery.stuck_step == 1
        assert "Test error" in recovery.issue_description
        assert len(recovery.recovery_actions) > 0
    
    @pytest.mark.asyncio
    async def test_planning_calls_increment_correctly(self):
        """Test that planning calls are counted correctly."""
        config = CloudPlannerConfig(max_planning_calls=3)
        planner = CloudPlanner(config)
        
        assert planner.planning_calls_used == 0
        
        # Mock successful cloud response
        mock_response = MagicMock()
        mock_response.completion = TaskPlan(
            original_task="test",
            complexity=TaskComplexity.SIMPLE,
            total_steps=1,
            steps=[],
            estimated_duration=30
        )
        
        with patch.object(planner, '_get_cloud_client') as mock_client_getter:
            mock_client = MagicMock()
            mock_client.ainvoke = AsyncMock(return_value=mock_response)
            mock_client_getter.return_value = mock_client
            
            # First call should increment counter
            await planner.plan_task("Test task 1")
            assert planner.planning_calls_used == 1
            
            # Second call should increment counter
            await planner.plan_task("Test task 2")
            assert planner.planning_calls_used == 2
            
            # Third call should increment counter
            await planner.plan_task("Test task 3")
            assert planner.planning_calls_used == 3
            
            # Fourth call should not increment (should use fallback)
            await planner.plan_task("Test task 4")
            assert planner.planning_calls_used == 3  # Should not increment beyond max
    
    def test_usage_stats_accuracy(self):
        """Test that usage statistics are reported accurately."""
        config = CloudPlannerConfig(max_planning_calls=5)
        planner = CloudPlanner(config)
        
        # Initial state
        stats = planner.get_usage_stats()
        assert stats["planning_calls_used"] == 0
        assert stats["max_planning_calls"] == 5
        assert stats["remaining_calls"] == 5
        
        # After using some calls
        planner.planning_calls_used = 3
        stats = planner.get_usage_stats()
        assert stats["planning_calls_used"] == 3
        assert stats["max_planning_calls"] == 5
        assert stats["remaining_calls"] == 2
        
        # After reaching limit
        planner.planning_calls_used = 5
        stats = planner.get_usage_stats()
        assert stats["planning_calls_used"] == 5
        assert stats["max_planning_calls"] == 5
        assert stats["remaining_calls"] == 0
    
    @pytest.mark.asyncio
    async def test_recovery_disabled_uses_fallback(self):
        """Test that disabling recovery uses fallback without cloud calls."""
        config = CloudPlannerConfig(enable_recovery=False)
        planner = CloudPlanner(config)
        
        # Mock original plan
        original_plan = TaskPlan(
            original_task="Test task",
            complexity=TaskComplexity.SIMPLE,
            total_steps=1,
            steps=[TaskStep(step_number=1, action="test", description="test", success_criteria="test")],
            estimated_duration=30
        )
        
        # Mock cloud client to track calls
        cloud_calls = []
        
        def mock_get_cloud_client():
            mock_client = MagicMock()
            async def mock_ainvoke(*args, **kwargs):
                cloud_calls.append(args)
                return MagicMock()
            mock_client.ainvoke = mock_ainvoke
            return mock_client
        
        planner._get_cloud_client = mock_get_cloud_client
        
        # Try to create recovery plan - should use fallback immediately
        recovery = await planner.create_recovery_plan(original_plan, 1, "Test error")
        
        # Verify no cloud calls were made
        assert len(cloud_calls) == 0
        
        # Verify we got a fallback recovery plan
        assert recovery.stuck_step == 1
        assert len(recovery.recovery_actions) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])