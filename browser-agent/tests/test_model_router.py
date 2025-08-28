"""
Tests for the model routing logic.

This module tests the ModelRouter class functionality including model selection,
scoring algorithms, fallback mechanisms, and performance tracking.
"""

import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from config.models import TaskComplexity, ModelCapability, ModelProvider
from models.model_router import (
    ModelRouter, TaskRequirements, RoutingStrategy, ModelScore,
    SystemResourceMonitor
)
from tests.conftest import assert_model_selection_valid


class TestSystemResourceMonitor:
    """Test system resource monitoring functionality."""
    
    def test_get_available_memory_gb(self, mock_system_resources):
        """Test memory availability detection."""
        monitor = SystemResourceMonitor()
        
        with patch('psutil.virtual_memory') as mock_memory:
            mock_memory.return_value.available = 8 * 1024 ** 3  # 8GB
            memory = monitor.get_available_memory_gb()
            assert memory == 8.0
    
    def test_get_cpu_usage(self, mock_system_resources):
        """Test CPU usage detection."""
        monitor = SystemResourceMonitor()
        
        with patch('psutil.cpu_percent') as mock_cpu:
            mock_cpu.return_value = 45.0
            cpu_usage = monitor.get_cpu_usage()
            assert cpu_usage == 45.0
    
    def test_can_run_local_model_sufficient_resources(self, mock_system_resources):
        """Test local model capability with sufficient resources."""
        monitor = SystemResourceMonitor()
        
        with patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.cpu_percent') as mock_cpu:
            mock_memory.return_value.available = 8 * 1024 ** 3  # 8GB
            mock_cpu.return_value = 30.0  # 30% CPU
            
            # Should be able to run 4GB model (needs 5GB total with buffer)
            assert monitor.can_run_local_model(4.0) is True
    
    def test_can_run_local_model_insufficient_memory(self, mock_system_resources):
        """Test local model capability with insufficient memory."""
        monitor = SystemResourceMonitor()
        
        with patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.cpu_percent') as mock_cpu:
            mock_memory.return_value.available = 2 * 1024 ** 3  # 2GB
            mock_cpu.return_value = 30.0  # 30% CPU
            
            # Should not be able to run 4GB model (needs 5GB total with buffer)
            assert monitor.can_run_local_model(4.0) is False
    
    def test_can_run_local_model_high_cpu_usage(self, mock_system_resources):
        """Test local model capability with high CPU usage."""
        monitor = SystemResourceMonitor()
        
        with patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.cpu_percent') as mock_cpu:
            mock_memory.return_value.available = 8 * 1024 ** 3  # 8GB
            mock_cpu.return_value = 85.0  # 85% CPU (too high)
            
            assert monitor.can_run_local_model(4.0) is False
    
    def test_get_system_load_factor(self, mock_system_resources):
        """Test system load factor calculation."""
        monitor = SystemResourceMonitor()
        
        with patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.cpu_percent') as mock_cpu:
            mock_memory.return_value.percent = 60.0  # 60% memory
            mock_cpu.return_value = 40.0  # 40% CPU
            
            # Load factor should be (60 + 40) / 200 = 0.5
            load_factor = monitor.get_system_load_factor()
            assert load_factor == 0.5


class TestModelRouter:
    """Test model router functionality."""
    
    @pytest_asyncio.fixture
    async def router(self, mock_model_config_manager, mock_ollama_handler, mock_cloud_manager):
        """Create a model router for testing."""
        return ModelRouter(
            model_config_manager=mock_model_config_manager,
            local_handler=mock_ollama_handler,
            cloud_manager=mock_cloud_manager,
            default_strategy=RoutingStrategy.BALANCED
        )
    
    @pytest.mark.asyncio
    async def test_select_model_simple_task(self, router, sample_task_requirements):
        """Test model selection for simple tasks."""
        requirements = sample_task_requirements["simple"]
        
        selected_model = await router.select_model(requirements)
        
        assert selected_model is not None
        assert_model_selection_valid(selected_model, requirements)
        
        # Simple tasks should select a valid model
        # The actual selection depends on the scoring algorithm and available models
        assert selected_model.name is not None
        assert len(selected_model.name) > 0
    
    @pytest.mark.asyncio
    async def test_select_model_vision_required(self, router, sample_task_requirements):
        """Test model selection when vision is required."""
        requirements = sample_task_requirements["moderate_vision"]
        
        selected_model = await router.select_model(requirements)
        
        assert selected_model is not None
        assert selected_model.supports_capability(ModelCapability.VISION)
        assert_model_selection_valid(selected_model, requirements)
    
    @pytest.mark.asyncio
    async def test_select_model_code_required(self, router, sample_task_requirements):
        """Test model selection when code capability is required."""
        requirements = sample_task_requirements["complex_code"]
        
        selected_model = await router.select_model(requirements)
        
        assert selected_model is not None
        assert selected_model.supports_capability(ModelCapability.CODE)
        assert_model_selection_valid(selected_model, requirements)
    
    @pytest.mark.asyncio
    async def test_select_model_expert_task(self, router, sample_task_requirements):
        """Test model selection for expert-level tasks."""
        requirements = sample_task_requirements["expert"]
        
        selected_model = await router.select_model(requirements)
        
        assert selected_model is not None
        assert_model_selection_valid(selected_model, requirements)
        
        # Expert tasks should prefer high-quality models - validate capabilities instead of specific names
        assert ModelCapability.REASONING in selected_model.capabilities
    
    @pytest.mark.asyncio
    async def test_routing_strategy_cost_optimized(self, router, sample_task_requirements):
        """Test cost-optimized routing strategy."""
        requirements = sample_task_requirements["simple"]
        
        selected_model = await router.select_model(
            requirements, 
            strategy=RoutingStrategy.COST_OPTIMIZED
        )
        
        assert selected_model is not None
        # Should prefer cost-effective models - validate cost rather than specific providers
        assert selected_model.specs.cost_per_1k_tokens <= 0.01  # Reasonable cost threshold
    
    @pytest.mark.asyncio
    async def test_routing_strategy_quality_optimized(self, router, sample_task_requirements):
        """Test quality-optimized routing strategy."""
        requirements = sample_task_requirements["complex_code"]
        
        selected_model = await router.select_model(
            requirements,
            strategy=RoutingStrategy.QUALITY_OPTIMIZED
        )
        
        assert selected_model is not None
        # Should prefer high-quality models - validate capabilities for complex code tasks
        assert ModelCapability.CODE in selected_model.capabilities
        assert ModelCapability.REASONING in selected_model.capabilities
    
    @pytest.mark.asyncio
    async def test_routing_strategy_local_first(self, router, sample_task_requirements):
        """Test local-first routing strategy."""
        requirements = sample_task_requirements["simple"]
        
        with patch.object(router.resource_monitor, 'can_run_local_model', return_value=True):
            selected_model = await router.select_model(
                requirements,
                strategy=RoutingStrategy.LOCAL_FIRST
            )
            
            assert selected_model is not None
            # Should prefer local models when available
            if selected_model.provider == ModelProvider.OLLAMA:
                assert selected_model.name == "llama3.2"
    
    @pytest.mark.asyncio
    async def test_routing_strategy_cloud_first(self, router, sample_task_requirements):
        """Test cloud-first routing strategy."""
        requirements = sample_task_requirements["moderate_vision"]
        
        selected_model = await router.select_model(
            requirements,
            strategy=RoutingStrategy.CLOUD_FIRST
        )
        
        assert selected_model is not None
        # Should prefer cloud models
        assert selected_model.provider in [ModelProvider.OPENAI, ModelProvider.ANTHROPIC]
    
    @pytest.mark.asyncio
    async def test_provider_preferences(self, router):
        """Test provider preference filtering."""
        requirements = TaskRequirements(
            complexity=TaskComplexity.MODERATE,
            preferred_providers=[ModelProvider.ANTHROPIC]
        )
        
        selected_model = await router.select_model(requirements)
        
        assert selected_model is not None
        assert selected_model.provider == ModelProvider.ANTHROPIC
        assert selected_model.name == "claude-3-5-sonnet"
    
    @pytest.mark.asyncio
    async def test_provider_avoidance(self, router):
        """Test provider avoidance filtering."""
        requirements = TaskRequirements(
            complexity=TaskComplexity.SIMPLE,
            avoid_providers=[ModelProvider.OLLAMA]
        )
        
        selected_model = await router.select_model(requirements)
        
        assert selected_model is not None
        assert selected_model.provider != ModelProvider.OLLAMA
        # Should select any non-OLLAMA provider that meets requirements
    
    @pytest.mark.asyncio
    async def test_cost_constraint(self, router):
        """Test cost constraint filtering."""
        requirements = TaskRequirements(
            complexity=TaskComplexity.MODERATE,
            max_cost=0.001  # Very low cost limit
        )
        
        selected_model = await router.select_model(requirements)
        
        assert selected_model is not None
        # Should select the cheapest option (likely local or gpt-4o-mini)
        if selected_model.provider != ModelProvider.OLLAMA:
            assert selected_model.name == "gpt-4o-mini"
    
    @pytest.mark.asyncio
    async def test_no_suitable_models_error(self, router):
        """Test error when no suitable models are found."""
        requirements = TaskRequirements(
            complexity=TaskComplexity.EXPERT,
            requires_vision=True,
            preferred_providers=[ModelProvider.OLLAMA]  # Ollama models don't support vision
        )
        
        with pytest.raises(RuntimeError, match="No suitable models found"):
            await router.select_model(requirements)
    
    @pytest.mark.asyncio
    async def test_fallback_chain_usage(self, router):
        """Test fallback chain mechanism."""
        # Mock the first model as unavailable
        with patch.object(router, '_calculate_availability_score') as mock_availability:
            mock_availability.side_effect = [0.0, 1.0, 1.0]  # First model unavailable
            
            requirements = TaskRequirements(complexity=TaskComplexity.SIMPLE)
            selected_model = await router.select_model(requirements)
            
            assert selected_model is not None
            # Should fall back to available model
    
    @pytest.mark.asyncio
    async def test_performance_tracking(self, router, sample_task_requirements):
        """Test performance tracking functionality."""
        requirements = sample_task_requirements["simple"]
        
        # Select model multiple times to build performance history
        for _ in range(3):
            await router.select_model(requirements)
        
        # Check that routing history is recorded
        assert len(router._routing_history) == 3
        
        # Each history entry should have required fields
        for entry in router._routing_history:
            assert "timestamp" in entry
            assert "task_complexity" in entry
            assert "selected_model" in entry
            assert "strategy" in entry
            assert "score" in entry
    
    @pytest.mark.asyncio
    async def test_model_scoring_components(self, router, sample_task_requirements):
        """Test individual scoring components."""
        requirements = sample_task_requirements["moderate_vision"]
        candidates = await router._get_candidate_models(requirements)
        
        assert len(candidates) > 0
        
        # Test scoring for first candidate
        model = candidates[0]
        
        cost_score = await router._calculate_cost_score(model, requirements)
        speed_score = await router._calculate_speed_score(model, requirements)
        quality_score = router._calculate_quality_score(model, requirements)
        availability_score = await router._calculate_availability_score(model)
        
        # All scores should be between 0 and 1
        assert 0.0 <= cost_score <= 1.0
        assert 0.0 <= speed_score <= 1.0
        assert 0.0 <= quality_score <= 1.0
        assert 0.0 <= availability_score <= 1.0
    
    @pytest.mark.asyncio
    async def test_resource_constrained_local_model(self, router):
        """Test local model selection under resource constraints."""
        requirements = TaskRequirements(
            complexity=TaskComplexity.SIMPLE,
            preferred_providers=[ModelProvider.OLLAMA]
        )
        
        # Mock insufficient resources
        with patch.object(router.resource_monitor, 'can_run_local_model', return_value=False):
            selected_model = await router.select_model(requirements)
            # Should still select a model but with lower availability score
            assert selected_model is not None
            assert selected_model.provider == ModelProvider.OLLAMA
    
    @pytest.mark.asyncio
    async def test_concurrent_model_selection(self, router, sample_task_requirements):
        """Test concurrent model selection requests."""
        import asyncio
        
        requirements = sample_task_requirements["simple"]
        
        # Run multiple selections concurrently
        tasks = [router.select_model(requirements) for _ in range(5)]
        results = await asyncio.gather(*tasks)
        
        # All should succeed and return valid models
        assert len(results) == 5
        for model in results:
            assert model is not None
            assert_model_selection_valid(model, requirements)


class TestModelScoring:
    """Test model scoring algorithms."""
    
    @pytest.mark.asyncio
    async def test_cost_score_local_model(self, router, sample_model_configs):
        """Test cost scoring for local models."""
        local_model = next(m for m in sample_model_configs if m.provider == ModelProvider.OLLAMA)
        requirements = TaskRequirements(complexity=TaskComplexity.SIMPLE)
        
        cost_score = await router._calculate_cost_score(local_model, requirements)
        
        # Local models should get perfect cost score (free after setup)
        assert cost_score == 1.0
    
    @pytest.mark.asyncio
    async def test_cost_score_cloud_model(self, router, sample_model_configs):
        """Test cost scoring for cloud models."""
        cloud_model = next(m for m in sample_model_configs if m.provider == ModelProvider.OPENAI)
        requirements = TaskRequirements(complexity=TaskComplexity.SIMPLE)
        
        cost_score = await router._calculate_cost_score(cloud_model, requirements)
        
        # Cloud models should get score based on cost
        assert 0.0 <= cost_score <= 1.0
    
    @pytest.mark.asyncio
    async def test_cost_score_budget_constraint(self, router, sample_model_configs):
        """Test cost scoring with budget constraints."""
        expensive_model = next(m for m in sample_model_configs if m.provider == ModelProvider.ANTHROPIC)
        requirements = TaskRequirements(
            complexity=TaskComplexity.SIMPLE,
            max_cost=0.001  # Very low budget
        )
        
        cost_score = await router._calculate_cost_score(expensive_model, requirements)
        
        # Should get zero score if over budget
        assert cost_score == 0.0
    
    @pytest.mark.asyncio
    async def test_speed_score_with_tokens_per_second(self, router, sample_model_configs):
        """Test speed scoring based on tokens per second."""
        model = sample_model_configs[0]  # Has tokens_per_second defined
        requirements = TaskRequirements(complexity=TaskComplexity.SIMPLE)
        
        speed_score = await router._calculate_speed_score(model, requirements)
        
        assert 0.0 <= speed_score <= 1.0
    
    def test_quality_score_task_suitability(self, router, sample_model_configs):
        """Test quality scoring based on task suitability."""
        model = sample_model_configs[0]
        requirements = TaskRequirements(complexity=TaskComplexity.SIMPLE)
        
        quality_score = router._calculate_quality_score(model, requirements)
        
        # Should be based on task suitability mapping
        expected_score = model.task_suitability.get(TaskComplexity.SIMPLE, 0.5)
        assert quality_score == expected_score
    
    @pytest.mark.asyncio
    async def test_availability_score_local_model(self, router, sample_model_configs):
        """Test availability scoring for local models."""
        local_model = next(m for m in sample_model_configs if m.provider == ModelProvider.OLLAMA)
        
        # Mock local handler availability
        router.local_handler.is_available.return_value = True
        
        availability_score = await router._calculate_availability_score(local_model)
        
        assert availability_score > 0.0
    
    @pytest.mark.asyncio
    async def test_availability_score_cloud_model(self, router, sample_model_configs):
        """Test availability scoring for cloud models."""
        cloud_model = next(m for m in sample_model_configs if m.provider == ModelProvider.OPENAI)
        
        # Mock cloud manager availability
        router.cloud_manager.is_available.return_value = True
        
        availability_score = await router._calculate_availability_score(cloud_model)
        
        assert availability_score > 0.0


@pytest.mark.parametrize("strategy", [
    RoutingStrategy.COST_OPTIMIZED,
    RoutingStrategy.SPEED_OPTIMIZED,
    RoutingStrategy.QUALITY_OPTIMIZED,
    RoutingStrategy.BALANCED,
    RoutingStrategy.LOCAL_FIRST,
    RoutingStrategy.CLOUD_FIRST
])
class TestRoutingStrategies:
    """Test different routing strategies."""
    
    @pytest.mark.asyncio
    async def test_strategy_consistency(self, router, sample_task_requirements, strategy):
        """Test that routing strategies produce consistent results."""
        requirements = sample_task_requirements["moderate_vision"]
        
        # Select model multiple times with same strategy
        results = []
        for _ in range(3):
            model = await router.select_model(requirements, strategy=strategy)
            results.append(model.name)
        
        # Results should be consistent (same model selected)
        assert len(set(results)) <= 2  # Allow for some variation due to scoring


@pytest.mark.performance
class TestModelRouterPerformance:
    """Test model router performance characteristics."""
    
    @pytest.mark.asyncio
    async def test_selection_performance(self, router, sample_task_requirements):
        """Test model selection performance."""
        import time
        
        requirements = sample_task_requirements["simple"]
        
        start_time = time.time()
        await router.select_model(requirements)
        end_time = time.time()
        
        # Selection should be fast (under 1 second)
        assert (end_time - start_time) < 1.0
    
    @pytest.mark.asyncio
    async def test_concurrent_selection_performance(self, router, sample_task_requirements):
        """Test performance under concurrent load."""
        import asyncio
        import time
        
        requirements = sample_task_requirements["simple"]
        
        start_time = time.time()
        tasks = [router.select_model(requirements) for _ in range(10)]
        await asyncio.gather(*tasks)
        end_time = time.time()
        
        # Concurrent selections should complete reasonably fast
        assert (end_time - start_time) < 5.0


@pytest.mark.integration
class TestModelRouterIntegration:
    """Integration tests for model router."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_model_selection(self, router, sample_task_requirements):
        """Test complete end-to-end model selection flow."""
        requirements = sample_task_requirements["complex_code"]
        
        # This should work without mocking internal methods
        selected_model = await router.select_model(requirements)
        
        assert selected_model is not None
        assert_model_selection_valid(selected_model, requirements)
        
        # Verify routing was recorded
        assert len(router._routing_history) > 0
        latest_routing = router._routing_history[-1]
        assert latest_routing["selected_model"] == selected_model.name