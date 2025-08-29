"""
Model Router for intelligent model selection and task routing.

This module implements the ModelRouter class that decides which model to use
based on task complexity, resource availability, and performance requirements.
"""

import asyncio
import logging
import psutil
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

from config.models import ModelConfig, ModelConfigManager, ModelCapability, ModelProvider, TaskComplexity
from config.central_model_config import (
	CENTRAL_MODEL_CONFIG,
	get_planner_model,
	get_tier_models,
	get_escalation_chain,
	ModelTier
)
from models.local_handler import OllamaModelHandler
from models.cloud_handler import CloudModelManager, TokenUsage


class RoutingStrategy(str, Enum):
    """Model routing strategies."""
    COST_OPTIMIZED = "cost_optimized"      # Prefer cheapest option
    SPEED_OPTIMIZED = "speed_optimized"    # Prefer fastest option
    QUALITY_OPTIMIZED = "quality_optimized"  # Prefer highest quality
    BALANCED = "balanced"                  # Balance cost, speed, and quality
    LOCAL_FIRST = "local_first"           # Prefer local models when possible
    CLOUD_FIRST = "cloud_first"           # Prefer cloud models when possible


@dataclass
class TaskRequirements:
    """Requirements for a specific task."""
    requires_vision: bool = False
    requires_code: bool = False
    max_response_time: Optional[float] = None
    max_cost: Optional[float] = None
    preferred_providers: Optional[List[ModelProvider]] = None
    avoid_providers: Optional[List[ModelProvider]] = None
    is_planning_task: bool = False  # True for high-level planning tasks
    complexity: TaskComplexity = TaskComplexity.MODERATE  # Default complexity level


@dataclass
class ModelScore:
    """Scoring for model selection."""
    model_config: ModelConfig
    score: float
    cost_score: float
    speed_score: float
    quality_score: float
    availability_score: float
    reasoning: str


class SystemResourceMonitor:
    """Monitor system resources for local model decisions."""
    
    def __init__(self):
        """Initialize resource monitor."""
        self.logger = logging.getLogger(__name__)

    def get_available_memory_gb(self) -> float:
        """Get available system memory in GB."""
        try:
            memory = psutil.virtual_memory()
            return memory.available / (1024 ** 3)
        except Exception as e:
            self.logger.warning(f"Failed to get memory info: {e}")
            return 0.0

    def get_cpu_usage(self) -> float:
        """Get current CPU usage percentage."""
        try:
            return psutil.cpu_percent(interval=1)
        except Exception as e:
            self.logger.warning(f"Failed to get CPU usage: {e}")
            return 100.0

    def can_run_local_model(self, required_memory_gb: float) -> bool:
        """
        Check if system can run a local model.
        
        Args:
            required_memory_gb: Required memory in GB
            
        Returns:
            True if system can handle the model
        """
        available_memory = self.get_available_memory_gb()
        cpu_usage = self.get_cpu_usage()
        
        # Need at least 1GB buffer and CPU usage < 80%
        return (
            available_memory >= required_memory_gb + 1.0 and
            cpu_usage < 80.0
        )

    def get_system_load_factor(self) -> float:
        """
        Get system load factor (0.0 = no load, 1.0 = high load).
        
        Returns:
            Load factor between 0.0 and 1.0
        """
        try:
            cpu_usage = self.get_cpu_usage()
            memory = psutil.virtual_memory()
            memory_usage = memory.percent
            
            # Combine CPU and memory usage
            load_factor = (cpu_usage + memory_usage) / 200.0
            return min(1.0, max(0.0, load_factor))
            
        except Exception:
            return 0.5  # Default to medium load


class ModelRouter:
    """Intelligent model router for task-based model selection."""
    
    def __init__(
        self,
        model_config_manager: ModelConfigManager,
        local_handler: Optional[OllamaModelHandler] = None,
        cloud_manager: Optional[CloudModelManager] = None,
        default_strategy: RoutingStrategy = RoutingStrategy.LOCAL_FIRST
    ):
        """
        Initialize model router.
        
        Args:
            model_config_manager: Model configuration manager
            local_handler: Optional local model handler
            cloud_manager: Optional cloud model manager
            default_strategy: Default routing strategy
        """
        self.model_config_manager = model_config_manager
        self.local_handler = local_handler
        self.cloud_manager = cloud_manager
        self.default_strategy = default_strategy
        self.logger = logging.getLogger(__name__)
        
        # Resource monitoring
        self.resource_monitor = SystemResourceMonitor()
        
        # Performance tracking
        self._model_performance: Dict[str, Dict[str, Any]] = {}
        self._routing_history: List[Dict[str, Any]] = []
        
        # Use centralized model configuration
        self._central_config = CENTRAL_MODEL_CONFIG
        
        # Get planner and execution models from centralized config
        planner_config = get_planner_model()
        self._planning_model = planner_config.name
        
        # Build execution chain from tier progression
        text_models = get_tier_models(ModelTier.TEXT_LOCAL)
        vision_models = get_tier_models(ModelTier.VISION_LOCAL) 
        cloud_models = get_tier_models(ModelTier.CLOUD)
        
        # Create execution chain: primary from each tier
        execution_models = []
        if text_models:
            execution_models.append(text_models[0].name)  # Primary text model
        if vision_models:
            execution_models.append(vision_models[0].name)  # Primary vision model
        if cloud_models:
            execution_models.append(cloud_models[0].name)  # Primary cloud model
        
        self._execution_chain = execution_models or ["granite3.2-vision", "gemini-2.5-flash", "gpt-4o"]  # Fallback

    def get_model_for_task(self, task_requirements: TaskRequirements) -> str:
        """Get the appropriate model for a task using centralized configuration."""
        if task_requirements.is_planning_task:
            # Always use o3-2025-04-16 for planning
            return self._planning_model
        else:
            # Determine starting tier based on vision requirements
            escalation_chain = get_escalation_chain(requires_vision=task_requirements.requires_vision)
            
            if escalation_chain:
                # Get primary model from first tier in escalation chain
                first_tier = escalation_chain[0]
                primary_model = self._central_config.get_primary_model(first_tier)
                return primary_model.name
            else:
                # Fallback to first execution model
                return self._execution_chain[0] if self._execution_chain else "qwen3:8b"

    async def select_model(
        self,
        task_requirements: TaskRequirements,
        strategy: Optional[RoutingStrategy] = None
    ) -> ModelConfig:
        """
        Select the best model for a task.
        
        Args:
            task_requirements: Task requirements
            strategy: Optional routing strategy override
            
        Returns:
            Selected model configuration
            
        Raises:
            RuntimeError: If no suitable model is found
        """
        strategy = strategy or self.default_strategy
        
        # Use centralized configuration for model selection
        model_name = self.get_model_for_task(task_requirements)
        model_config = self.model_config_manager.get_model_config(model_name)
        
        if not model_config:
            # Try to create compatible config from centralized config
            central_model = self._central_config.get_model_by_name(model_name)
            if central_model:
                try:
                    model_config = self._create_compatible_model_config(central_model)
                except Exception as e:
                    raise RuntimeError(f"Model configuration not found for: {model_name}, failed to create compatible config: {e}")
            else:
                raise RuntimeError(f"Model configuration not found for: {model_name}")
        
        # Verify model meets basic requirements and escalate if needed
        if task_requirements.requires_vision and not model_config.specs.supports_vision:
            # Use centralized escalation logic
            if not task_requirements.is_planning_task:
                escalation_chain = get_escalation_chain(requires_vision=True)
                for tier in escalation_chain:
                    tier_models = get_tier_models(tier)
                    for central_model in tier_models:
                        if "vision" in [cap.value for cap in central_model.capabilities]:
                            esc_config = self.model_config_manager.get_model_config(central_model.name)
                            if not esc_config:
                                try:
                                    esc_config = self._create_compatible_model_config(central_model)
                                except Exception:
                                    continue
                            if esc_config:
                                model_config = esc_config
                                break
                    if model_config and model_config.specs.supports_vision:
                        break
        
        # Record routing decision
        self._record_simple_routing_decision(task_requirements, model_config)
        
        task_type = "planner" if task_requirements.is_planning_task else "executor"
        self.logger.info(f"Selected model: {model_config.name} ({task_type}) via centralized config")
        
        return model_config


    async def _score_models(
        self,
        candidates: List[ModelConfig],
        task_requirements: TaskRequirements,
        strategy: RoutingStrategy
    ) -> List[ModelScore]:
        """Score candidate models based on strategy."""
        scored_models = []
        
        for model in candidates:
            # Calculate individual scores
            cost_score = await self._calculate_cost_score(model, task_requirements)
            speed_score = await self._calculate_speed_score(model, task_requirements)
            quality_score = self._calculate_quality_score(model, task_requirements)
            availability_score = await self._calculate_availability_score(model)
            
            # Combine scores based on strategy
            if strategy == RoutingStrategy.COST_OPTIMIZED:
                final_score = cost_score * 0.6 + speed_score * 0.2 + quality_score * 0.1 + availability_score * 0.1
            elif strategy == RoutingStrategy.SPEED_OPTIMIZED:
                final_score = speed_score * 0.6 + availability_score * 0.2 + quality_score * 0.1 + cost_score * 0.1
            elif strategy == RoutingStrategy.QUALITY_OPTIMIZED:
                final_score = quality_score * 0.6 + availability_score * 0.2 + speed_score * 0.1 + cost_score * 0.1
            elif strategy == RoutingStrategy.LOCAL_FIRST:
                local_bonus = 0.3 if model.provider == ModelProvider.OLLAMA else 0.0
                final_score = (speed_score * 0.3 + quality_score * 0.3 + availability_score * 0.4) + local_bonus
            elif strategy == RoutingStrategy.CLOUD_FIRST:
                cloud_bonus = 0.3 if model.provider != ModelProvider.OLLAMA else 0.0
                final_score = (quality_score * 0.4 + speed_score * 0.3 + availability_score * 0.3) + cloud_bonus
            else:  # BALANCED
                final_score = cost_score * 0.25 + speed_score * 0.25 + quality_score * 0.25 + availability_score * 0.25
            
            reasoning = self._generate_scoring_reasoning(
                model, cost_score, speed_score, quality_score, availability_score, strategy
            )
            
            scored_models.append(ModelScore(
                model_config=model,
                score=final_score,
                cost_score=cost_score,
                speed_score=speed_score,
                quality_score=quality_score,
                availability_score=availability_score,
                reasoning=reasoning
            ))
        
        return scored_models

    async def _calculate_cost_score(
        self, 
        model: ModelConfig, 
        task_requirements: TaskRequirements
    ) -> float:
        """Calculate cost score (higher is better/cheaper)."""
        if model.provider == ModelProvider.OLLAMA:
            return 1.0  # Local models are "free" after setup
        
        if not model.specs.cost_per_1k_tokens:
            return 0.5  # Unknown cost
        
        # Estimate cost for typical request
        estimated_tokens = 1000  # Rough estimate
        estimated_cost = model.estimate_cost(estimated_tokens // 2, estimated_tokens // 2)
        
        if not estimated_cost:
            return 0.5
        
        # Check against budget constraints
        if task_requirements.max_cost and estimated_cost > task_requirements.max_cost:
            return 0.0
        
        # Score based on cost (lower cost = higher score)
        # Normalize against typical range of $0.001 to $0.05 per 1k tokens
        normalized_cost = min(1.0, estimated_cost / 0.05)
        return 1.0 - normalized_cost

    async def _calculate_speed_score(
        self, 
        model: ModelConfig, 
        task_requirements: TaskRequirements
    ) -> float:
        """Calculate speed score (higher is better/faster)."""
        if model.provider == ModelProvider.OLLAMA:
            # Check if we can run the model locally
            if model.specs.estimated_memory_gb:
                if not self.resource_monitor.can_run_local_model(model.specs.estimated_memory_gb):
                    return 0.0  # Can't run locally
            
            # Use tokens per second if available
            if model.specs.tokens_per_second:
                # Normalize against typical range of 10-100 tokens/sec
                normalized_speed = min(1.0, model.specs.tokens_per_second / 100.0)
                return normalized_speed
            
            return 0.7  # Default for local models
        
        # Cloud models - check historical performance
        perf_data = self._model_performance.get(model.name)
        if perf_data and "avg_tokens_per_second" in perf_data:
            # Normalize against typical range of 20-200 tokens/sec for cloud
            normalized_speed = min(1.0, perf_data["avg_tokens_per_second"] / 200.0)
            return normalized_speed
        
        # Default scores based on known model characteristics
        if "gpt-4o-mini" in model.model_id:
            return 0.9
        elif "gpt-4o" in model.model_id:
            return 0.7
        elif "claude" in model.model_id:
            return 0.8
        elif "gemini" in model.model_id:
            return 0.8
        
        return 0.6  # Default

    def _calculate_quality_score(
        self, 
        model: ModelConfig, 
        task_requirements: TaskRequirements
    ) -> float:
        """Calculate quality score based on model capabilities and reputation."""
        base_score = 0.5
        
        # Adjust based on model type and capabilities
        if ModelCapability.REASONING in model.capabilities:
            base_score += 0.2
        
        if ModelCapability.MULTIMODAL in model.capabilities:
            base_score += 0.1
        
        # Model-specific adjustments based on known performance
        if "gpt-4o" in model.model_id and "mini" not in model.model_id:
            base_score += 0.3
        elif "claude-3-5-sonnet" in model.model_id:
            base_score += 0.3
        elif "gemini-1.5-pro" in model.model_id:
            base_score += 0.2
        elif "gpt-4o-mini" in model.model_id:
            base_score += 0.1
        
        # Context length bonus for complex tasks
        if task_requirements.complexity in [TaskComplexity.COMPLEX, TaskComplexity.EXPERT]:
            if model.specs.context_length > 100000:
                base_score += 0.1
        
        return min(1.0, base_score)

    async def _calculate_availability_score(self, model: ModelConfig) -> float:
        """Calculate availability score."""
        if model.provider == ModelProvider.OLLAMA:
            if not self.local_handler:
                return 0.0
            
            # Check if Ollama is available
            if not await self.local_handler.is_available():
                return 0.0
            
            # Check system resources
            if model.specs.estimated_memory_gb:
                if not self.resource_monitor.can_run_local_model(model.specs.estimated_memory_gb):
                    return 0.3  # Might work but not ideal
            
            # Factor in system load
            load_factor = self.resource_monitor.get_system_load_factor()
            return 1.0 - (load_factor * 0.3)
        
        else:
            # Cloud models - check if we have the handler and API key
            if not self.cloud_manager:
                return 0.0
            
            # Check budget constraints
            if hasattr(self.cloud_manager, 'budget_manager'):
                budget_status = self.cloud_manager.budget_manager.get_budget_status()
                if budget_status['daily_remaining'] <= 0 or budget_status['monthly_remaining'] <= 0:
                    return 0.0
            
            # Check historical reliability
            perf_data = self._model_performance.get(model.name)
            if perf_data and "success_rate" in perf_data:
                return perf_data["success_rate"]
            
            return 0.9  # Default high availability for cloud

    def _generate_scoring_reasoning(
        self,
        model: ModelConfig,
        cost_score: float,
        speed_score: float,
        quality_score: float,
        availability_score: float,
        strategy: RoutingStrategy
    ) -> str:
        """Generate human-readable reasoning for model selection."""
        reasons = []
        
        if cost_score > 0.8:
            reasons.append("very cost-effective")
        elif cost_score > 0.6:
            reasons.append("reasonably priced")
        elif cost_score < 0.3:
            reasons.append("expensive")
        
        if speed_score > 0.8:
            reasons.append("very fast")
        elif speed_score > 0.6:
            reasons.append("good speed")
        elif speed_score < 0.3:
            reasons.append("slow")
        
        if quality_score > 0.8:
            reasons.append("high quality")
        elif quality_score > 0.6:
            reasons.append("good quality")
        
        if availability_score < 0.5:
            reasons.append("limited availability")
        elif availability_score > 0.9:
            reasons.append("highly available")
        
        if model.provider == ModelProvider.OLLAMA:
            reasons.append("runs locally")
        else:
            reasons.append("cloud-based")
        
        return f"Selected for {strategy.value} strategy: {', '.join(reasons)}"
    
    def _create_compatible_model_config(self, central_model) -> ModelConfig:
        """Create a compatible ModelConfig from central model configuration."""
        from config.central_model_config import ModelProvider as CentralProvider, ModelCapabilities
        from config.models import ModelSpecs as ConfigModelSpecs, ModelCapability
        
        # Map central providers to config providers
        provider_map = {
            CentralProvider.OLLAMA: ModelProvider.OLLAMA,
            CentralProvider.OPENAI: ModelProvider.OPENAI,
            CentralProvider.ANTHROPIC: ModelProvider.ANTHROPIC,
            CentralProvider.GOOGLE: ModelProvider.GOOGLE
        }
        
        # Map central capabilities to config capabilities
        capability_map = {
            ModelCapabilities.TEXT_ONLY: ModelCapability.TEXT_ONLY,
            ModelCapabilities.VISION: ModelCapability.VISION,
            ModelCapabilities.CODE: ModelCapability.CODE,
            ModelCapabilities.REASONING: ModelCapability.REASONING,
            ModelCapabilities.MULTIMODAL: ModelCapability.MULTIMODAL
        }
        
        # Convert capabilities
        capabilities = []
        for cap in central_model.capabilities:
            if cap in capability_map:
                capabilities.append(capability_map[cap])
        
        # Create compatible ModelSpecs
        specs = ConfigModelSpecs(
            context_length=central_model.specs.context_length,
            max_tokens=min(central_model.specs.context_length, 4096),  # Reasonable default
            supports_vision=ModelCapabilities.VISION in central_model.capabilities,
            supports_function_calling=ModelCapabilities.CODE in central_model.capabilities,
            estimated_memory_gb=central_model.specs.memory_gb,
            tokens_per_second=central_model.specs.tokens_per_second,
            cost_per_1k_tokens=central_model.specs.cost_per_1k_input
        )
        
        # Create a compatible ModelConfig
        return ModelConfig(
            name=central_model.name,
            provider=provider_map.get(central_model.provider, ModelProvider.OPENAI),
            model_id=central_model.model_id or central_model.name,
            specs=specs,
            capabilities=capabilities
        )

    def _record_simple_routing_decision(
        self,
        task_requirements: TaskRequirements,
        selected_model: ModelConfig
    ):
        """Record simplified routing decision for analysis."""
        decision = {
            "timestamp": datetime.now().isoformat(),
            "requires_vision": task_requirements.requires_vision,
            "requires_code": task_requirements.requires_code,
            "is_planning_task": task_requirements.is_planning_task,
            "selected_model": selected_model.name,
            "model_provider": selected_model.provider.value,
            "reasoning": "planner" if task_requirements.is_planning_task else "executor"
        }
        
        self._routing_history.append(decision)
        
        # Keep only last 1000 decisions
        if len(self._routing_history) > 1000:
            self._routing_history = self._routing_history[-1000:]

    async def execute_with_fallback(
        self,
        task_requirements: TaskRequirements,
        prompt: str,
        system_prompt: Optional[str] = None,
        strategy: Optional[RoutingStrategy] = None
    ) -> Tuple[str, TokenUsage, ModelConfig]:
        """
        Execute a task with automatic fallback to alternative models.
        
        Args:
            task_requirements: Task requirements
            prompt: Input prompt
            system_prompt: Optional system prompt
            strategy: Optional routing strategy
            
        Returns:
            Generated text, token usage, and used model config
        """
        # Use centralized configuration for fallbacks
        if task_requirements.is_planning_task:
            fallback_models = [self._planning_model]
        else:
            # Build comprehensive fallback chain using centralized escalation
            escalation_chain = get_escalation_chain(requires_vision=task_requirements.requires_vision)
            fallback_models = []
            
            for tier in escalation_chain:
                tier_models = get_tier_models(tier)
                fallback_models.extend([m.name for m in tier_models])
            
            # Fallback to old execution chain if centralized config fails
            if not fallback_models:
                fallback_models = self._execution_chain
        
        last_error = None
        
        for model_name in fallback_models:
            try:
                model_config = self.model_config_manager.get_model_config(model_name)
                if not model_config:
                    continue
                
                # Check if model meets basic requirements
                if task_requirements.requires_vision and not model_config.specs.supports_vision:
                    continue
                if task_requirements.requires_code and not model_config.supports_capability(ModelCapability.CODE):
                    continue
                
                # Try to execute with this model
                if model_config.provider == ModelProvider.OLLAMA and self.local_handler:
                    response = await self.local_handler.generate_text(
                        model_name=model_config.model_id,
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=model_config.temperature,
                        max_tokens=model_config.max_tokens
                    )
                    # Create token usage for local model (estimated)
                    token_usage = TokenUsage(
                        input_tokens=len(prompt.split()) * 1.3,  # Rough estimate
                        output_tokens=len(response.split()) * 1.3,
                        total_tokens=len((prompt + response).split()) * 1.3
                    )
                    return response, token_usage, model_config
                
                elif model_config.provider != ModelProvider.OLLAMA and self.cloud_manager:
                    response, token_usage = await self.cloud_manager.generate_text(
                        model_config=model_config,
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=model_config.temperature,
                        max_tokens=model_config.max_tokens
                    )
                    return response, token_usage, model_config
                
            except Exception as e:
                last_error = e
                self.logger.warning(f"Failed to use model {model_name}: {e}")
                continue
        
        # If all fallbacks failed
        raise RuntimeError(f"All fallback models failed. Last error: {last_error}")

    def update_model_performance(
        self, 
        model_name: str, 
        metrics: Dict[str, Any]
    ):
        """
        Update performance metrics for a model.
        
        Args:
            model_name: Name of the model
            metrics: Performance metrics
        """
        if model_name not in self._model_performance:
            self._model_performance[model_name] = {}
        
        self._model_performance[model_name].update(metrics)

    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics and insights."""
        if not self._routing_history:
            return {"message": "No routing history available"}
        
        # Analyze routing patterns
        total_decisions = len(self._routing_history)
        
        # Count by strategy
        strategy_counts = {}
        for decision in self._routing_history:
            strategy = decision["strategy"]
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
        
        # Count by model
        model_counts = {}
        for decision in self._routing_history:
            model = decision["selected_model"]
            model_counts[model] = model_counts.get(model, 0) + 1
        
        # Count by provider
        provider_counts = {}
        for decision in self._routing_history:
            provider = decision["model_provider"]
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
        
        return {
            "total_routing_decisions": total_decisions,
            "strategy_distribution": strategy_counts,
            "model_usage": model_counts,
            "provider_distribution": provider_counts,
            "recent_decisions": self._routing_history[-10:],
            "model_performance": self._model_performance
        }