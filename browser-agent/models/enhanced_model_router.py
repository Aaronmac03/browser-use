"""
Enhanced Model Router with Three-Tier Routing Strategy.

This module extends the base ModelRouter to implement intelligent routing between:
1. Local text-only models (fastest, cheapest)
2. Local vision models (medium speed, free) 
3. Cloud models (slowest, most expensive, highest quality)
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from models.model_router import ModelRouter, TaskRequirements, RoutingStrategy, SystemResourceMonitor
from models.action_classifier import ActionClassifier, ActionAnalysis, ActionType, TaskComplexity
from models.task_planner import TaskPlanner, TaskPlan, PlanningStrategy, ActionType as PlanActionType
from config.models import ModelConfig, ModelConfigManager, ModelCapability, ModelProvider
from config.central_model_config import (
	CENTRAL_MODEL_CONFIG,
	ModelTier as CentralModelTier,
	get_planner_model,
	get_tier_models,
	get_escalation_chain,
	get_primary_model
)
from models.local_handler import OllamaModelHandler
from models.cloud_handler import CloudModelManager
from utils.serper import SerperAPI


# Use centralized ModelTier definition
ModelTier = CentralModelTier


@dataclass
class EnhancedTaskRequirements(TaskRequirements):
    """Enhanced task requirements with additional context."""
    task_description: str = ""
    has_dom_state: bool = False
    browser_state: Optional[Dict[str, Any]] = None
    action_context: Optional[Dict[str, Any]] = None
    
    # Performance preferences
    prefer_speed: bool = True
    prefer_cost: bool = True
    max_tier: Optional[ModelTier] = None  # Don't escalate beyond this tier
    
    # Planning preferences
    requires_planning: bool = False  # Force use of task planner
    enable_search_coordination: bool = True  # Allow Serper API coordination
    current_url: Optional[str] = None  # Current browser context


@dataclass
class RoutingDecision:
    """Result of routing decision."""
    selected_model: ModelConfig
    selected_tier: ModelTier
    action_analysis: ActionAnalysis
    reasoning: str
    confidence: float
    estimated_cost: float
    estimated_time: float
    fallback_models: List[ModelConfig] = field(default_factory=list)
    task_plan: Optional[TaskPlan] = None  # Optional task plan for complex queries


class EnhancedModelRouter(ModelRouter):
    """Enhanced model router with three-tier routing strategy."""
    
    def __init__(
        self,
        model_config_manager: ModelConfigManager,
        local_handler: Optional[OllamaModelHandler] = None,
        cloud_manager: Optional[CloudModelManager] = None,
        serper_api: Optional[SerperAPI] = None,
        default_strategy: RoutingStrategy = RoutingStrategy.BALANCED
    ):
        """Initialize enhanced model router."""
        super().__init__(model_config_manager, local_handler, cloud_manager, default_strategy)
        
        # Initialize action classifier
        self.action_classifier = ActionClassifier()
        
        # Initialize task planner with o3-2025-04-16
        self.task_planner = None
        if cloud_manager:
            self.task_planner = TaskPlanner(
                cloud_manager=cloud_manager,
                serper_api=serper_api,
                model_config_manager=model_config_manager
            )
        
        # Use centralized model configuration - no hardcoded model lists!
        self._central_config = CENTRAL_MODEL_CONFIG
        
        # Performance tracking for three-tier routing
        self._tier_performance: Dict[ModelTier, Dict[str, float]] = {
            ModelTier.TEXT_LOCAL: {"avg_time": 0.5, "success_rate": 0.95, "cost": 0.0},
            ModelTier.VISION_LOCAL: {"avg_time": 3.0, "success_rate": 0.90, "cost": 0.0},
            ModelTier.CLOUD: {"avg_time": 4.0, "success_rate": 0.98, "cost": 0.02},
        }
        
        # Escalation tracking
        self._escalation_stats = {
            "text_to_vision": 0,
            "vision_to_cloud": 0, 
            "text_to_cloud": 0,
            "total_decisions": 0
        }
    
    async def route_task(
        self, 
        task_requirements: EnhancedTaskRequirements,
        strategy: Optional[RoutingStrategy] = None
    ) -> RoutingDecision:
        """
        Route a task using the three-tier strategy with optional planning.
        
        Args:
            task_requirements: Enhanced task requirements
            strategy: Optional routing strategy override
            
        Returns:
            RoutingDecision with selected model and reasoning
        """
        strategy = strategy or self.default_strategy
        self._escalation_stats["total_decisions"] += 1
        
        # Step 0: Always use o3-2025-04-16 for single-shot planning (universal planning)
        task_plan = None
        if self.task_planner:
            planner_model = get_planner_model()
            self.logger.info(f"Using {planner_model.name} for universal task planning")
            task_plan = await self._create_task_plan(task_requirements)
            
            # If planning succeeded, use clarified intent for better local LLM understanding
            if task_plan and task_plan.steps:
                self.logger.info(f"{planner_model.name} created plan with {len(task_plan.steps)} steps")
                # Use clarified intent for subsequent routing - this makes local LLMs more effective
                task_requirements.task_description = task_plan.clarified_intent
            else:
                self.logger.info(f"{planner_model.name} planning not available, using original query")
        
        # Step 1: Analyze the action to determine vision requirements
        action_analysis = self.action_classifier.classify_action(
            task_requirements.task_description,
            task_requirements.has_dom_state,
            task_requirements.action_context
        )
        
        self.logger.debug(
            f"Action analysis: {action_analysis.action_type.value}, "
            f"vision_required={action_analysis.requires_vision}, "
            f"confidence={action_analysis.confidence_score:.2f}"
        )
        
        # Step 2: Determine target tier based on analysis and constraints
        target_tier = self._determine_target_tier(action_analysis, task_requirements, strategy)
        
        # Step 3: Select model from target tier
        selected_model, actual_tier = await self._select_model_from_tier(
            target_tier, task_requirements, action_analysis
        )
        
        # Step 4: Prepare fallback models
        fallback_models = await self._prepare_fallbacks(actual_tier, task_requirements)
        
        # Step 5: Calculate estimates
        estimated_cost = self._estimate_cost(selected_model, task_requirements)
        estimated_time = self._estimate_time(selected_model, actual_tier)
        
        # Step 6: Generate reasoning
        reasoning = self._generate_routing_reasoning(
            action_analysis, target_tier, actual_tier, selected_model, strategy
        )
        
        # Record the decision
        decision = RoutingDecision(
            selected_model=selected_model,
            selected_tier=actual_tier,
            action_analysis=action_analysis,
            reasoning=reasoning,
            confidence=action_analysis.confidence_score,
            estimated_cost=estimated_cost,
            estimated_time=estimated_time,
            fallback_models=fallback_models,
            task_plan=task_plan
        )
        
        self._record_routing_decision(decision)
        
        self.logger.info(
            f"Routed to {actual_tier.value}: {selected_model.name} "
            f"(cost: ${estimated_cost:.4f}, time: {estimated_time:.1f}s)"
        )
        
        return decision
    
    def _determine_target_tier(
        self, 
        action_analysis: ActionAnalysis, 
        task_requirements: EnhancedTaskRequirements,
        strategy: RoutingStrategy
    ) -> ModelTier:
        """Determine the target tier using centralized escalation chain."""
        
        # Check for explicit tier limits
        if task_requirements.max_tier:
            max_allowed = task_requirements.max_tier
        else:
            max_allowed = ModelTier.CLOUD
        
        # Use centralized escalation chain logic
        escalation_chain = get_escalation_chain(requires_vision=action_analysis.requires_vision)
        
        # Return the first tier in the chain that's allowed
        for tier in escalation_chain:
            if tier.value <= max_allowed.value:
                return tier
        
        # Fallback to text local if nothing else works
        return ModelTier.TEXT_LOCAL
    
    async def _select_model_from_tier(
        self,
        target_tier: ModelTier,
        task_requirements: EnhancedTaskRequirements,
        action_analysis: ActionAnalysis
    ) -> Tuple[ModelConfig, ModelTier]:
        """Select the best model from the target tier."""
        
        # Get available models for this tier
        tier_models = await self._get_tier_models(target_tier)
        
        if not tier_models:
            # Escalate to next tier if no models available
            return await self._escalate_tier(target_tier, task_requirements, action_analysis)
        
        # Filter models based on requirements
        suitable_models = []
        for model in tier_models:
            if self._is_model_suitable(model, task_requirements, action_analysis):
                suitable_models.append(model)
        
        if not suitable_models:
            # No suitable models in this tier - escalate
            return await self._escalate_tier(target_tier, task_requirements, action_analysis)
        
        # Select the best model from suitable candidates
        best_model = await self._select_best_model(suitable_models, task_requirements)
        
        return best_model, target_tier
    
    async def _get_tier_models(self, tier: ModelTier) -> List[ModelConfig]:
        """Get available models for a specific tier from centralized config."""
        # Get models from centralized configuration
        tier_model_configs = get_tier_models(tier)
        
        # Convert to compatible ModelConfig objects and check availability
        available_models = []
        for central_model in tier_model_configs:
            # Try to get model config from manager
            model_config = self.model_config_manager.get_model_config(central_model.name)
            if model_config:
                # Check availability
                if await self._is_model_available(model_config):
                    available_models.append(model_config)
            else:
                # Create compatible ModelConfig from central config
                try:
                    compatible_config = self._create_compatible_model_config(central_model)
                    if await self._is_model_available(compatible_config):
                        available_models.append(compatible_config)
                except Exception as e:
                    self.logger.warning(f"Could not create compatible config for {central_model.name}: {e}")
        
        return available_models
    
    async def _is_model_available(self, model: ModelConfig) -> bool:
        """Check if a model is currently available."""
        if model.provider == ModelProvider.OLLAMA:
            if not self.local_handler:
                return False
            return await self.local_handler.is_available()
        else:
            # For cloud models, assume available if we have credentials
            return self.cloud_manager is not None
    
    def _is_model_suitable(
        self, 
        model: ModelConfig, 
        task_requirements: EnhancedTaskRequirements,
        action_analysis: ActionAnalysis
    ) -> bool:
        """Check if a model is suitable for the task requirements."""
        
        # Check vision requirements
        if action_analysis.requires_vision and not model.specs.supports_vision:
            return False
        
        # Check code requirements
        if task_requirements.requires_code and not model.supports_capability(ModelCapability.CODE):
            return False
        
        # Check resource constraints for local models
        if model.provider == ModelProvider.OLLAMA:
            if model.specs.estimated_memory_gb:
                if not self.resource_monitor.can_run_local_model(model.specs.estimated_memory_gb):
                    return False
        
        # Check cost constraints
        if task_requirements.max_cost:
            estimated_cost = self._estimate_cost(model, task_requirements)
            if estimated_cost > task_requirements.max_cost:
                return False
        
        # Check response time constraints
        if task_requirements.max_response_time:
            estimated_time = self._estimate_time(model, ModelTier.CLOUD if model.provider != ModelProvider.OLLAMA else ModelTier.TEXT_LOCAL)
            if estimated_time > task_requirements.max_response_time:
                return False
        
        return True
    
    async def _escalate_tier(
        self,
        current_tier: ModelTier,
        task_requirements: EnhancedTaskRequirements,
        action_analysis: ActionAnalysis
    ) -> Tuple[ModelConfig, ModelTier]:
        """Escalate to the next available tier using centralized escalation logic."""
        
        # Get full escalation chain based on vision requirements
        full_chain = get_escalation_chain(requires_vision=action_analysis.requires_vision)
        
        # Find current tier in chain and get next tier
        try:
            current_index = full_chain.index(current_tier)
            if current_index + 1 >= len(full_chain):
                raise RuntimeError(f"No models available and cannot escalate from {current_tier}")
            next_tier = full_chain[current_index + 1]
        except ValueError:
            # Current tier not in chain - fall back to standard escalation
            if current_tier == ModelTier.TEXT_LOCAL:
                next_tier = ModelTier.VISION_LOCAL
            elif current_tier == ModelTier.VISION_LOCAL:
                next_tier = ModelTier.CLOUD
            else:
                raise RuntimeError(f"No models available and cannot escalate from {current_tier}")
        
        # Check if escalation is allowed
        if task_requirements.max_tier and next_tier.value > task_requirements.max_tier.value:
            raise RuntimeError(f"Escalation to {next_tier} blocked by max_tier constraint")
        
        # Record escalation
        escalation_key = f"{current_tier.value.split('_')[0]}_to_{next_tier.value.split('_')[0]}"
        if escalation_key in self._escalation_stats:
            self._escalation_stats[escalation_key] += 1
        
        self.logger.info(f"Escalating from {current_tier.value} to {next_tier.value} using centralized chain")
        
        return await self._select_model_from_tier(next_tier, task_requirements, action_analysis)
    
    async def _select_best_model(
        self, 
        candidates: List[ModelConfig], 
        task_requirements: EnhancedTaskRequirements
    ) -> ModelConfig:
        """Select the best model from candidates using existing scoring logic."""
        if len(candidates) == 1:
            return candidates[0]
        
        # Convert to base TaskRequirements for compatibility
        base_requirements = TaskRequirements(
            requires_vision=task_requirements.requires_vision,
            requires_code=task_requirements.requires_code,
            max_response_time=task_requirements.max_response_time,
            max_cost=task_requirements.max_cost,
            preferred_providers=task_requirements.preferred_providers,
            avoid_providers=task_requirements.avoid_providers,
            is_planning_task=task_requirements.is_planning_task
        )
        
        # Use existing scoring logic from parent class
        scored_models = await self._score_models(candidates, base_requirements, self.default_strategy)
        scored_models.sort(key=lambda x: x.score, reverse=True)
        
        return scored_models[0].model_config
    
    async def _prepare_fallbacks(
        self, 
        current_tier: ModelTier, 
        task_requirements: EnhancedTaskRequirements
    ) -> List[ModelConfig]:
        """Prepare fallback models using centralized configuration."""
        fallbacks = []
        
        # Add other models from the same tier (fallback models from central config)
        central_fallbacks = self._central_config.get_fallback_models(current_tier)
        for central_model in central_fallbacks[:2]:  # Limit to 2 fallbacks from same tier
            model_config = self.model_config_manager.get_model_config(central_model.name)
            if model_config:
                fallbacks.append(model_config)
            else:
                try:
                    compatible_config = self._create_compatible_model_config(central_model)
                    fallbacks.append(compatible_config)
                except Exception as e:
                    self.logger.warning(f"Could not create compatible fallback config for {central_model.name}: {e}")
        
        # Add escalation options using centralized escalation chain
        escalation_chain = get_escalation_chain(requires_vision=True)  # Conservative approach
        try:
            current_index = escalation_chain.index(current_tier)
            if current_index + 1 < len(escalation_chain):
                next_tier = escalation_chain[current_index + 1]
                if not task_requirements.max_tier or next_tier.value <= task_requirements.max_tier.value:
                    escalation_models = await self._get_tier_models(next_tier)
                    fallbacks.extend(escalation_models[:1])  # Add one escalation option
        except ValueError:
            pass  # Current tier not in escalation chain
        
        return fallbacks[:3]  # Limit total fallbacks
    
    def _create_compatible_model_config(self, central_model) -> ModelConfig:
        """Create a compatible ModelConfig from central model configuration."""
        from config.central_model_config import ModelProvider as CentralProvider
        
        # Map central providers to config providers
        provider_map = {
            CentralProvider.OLLAMA: ModelProvider.OLLAMA,
            CentralProvider.OPENAI: ModelProvider.OPENAI,
            CentralProvider.ANTHROPIC: ModelProvider.ANTHROPIC,
            CentralProvider.GOOGLE: ModelProvider.GOOGLE
        }
        
        # Create a compatible ModelConfig
        # This is a simplified conversion - you may need to expand this based on your ModelConfig structure
        return ModelConfig(
            name=central_model.name,
            provider=provider_map.get(central_model.provider, ModelProvider.OPENAI),
            model_id=central_model.model_id or central_model.name,
            supports_vision="vision" in [cap.value for cap in central_model.capabilities],
            context_length=central_model.specs.context_length,
            estimated_memory_gb=central_model.specs.memory_gb,
            tokens_per_second=central_model.specs.tokens_per_second,
            cost_per_1k_tokens=central_model.specs.cost_per_1k_input
        )
    
    def _estimate_cost(self, model: ModelConfig, task_requirements: EnhancedTaskRequirements) -> float:
        """Estimate cost for a model request."""
        if model.provider == ModelProvider.OLLAMA:
            return 0.0  # Local models are free to run
        
        # Estimate token usage based on task complexity
        if task_requirements.action_context:
            base_tokens = 500  # Simple action
        else:
            base_tokens = 1000  # Complex action
        
        if task_requirements.has_dom_state:
            base_tokens += 300  # Additional context
        
        # Add vision overhead if applicable
        if task_requirements.requires_vision:
            base_tokens += 500  # Vision processing overhead
        
        estimated_cost = model.estimate_cost(base_tokens // 2, base_tokens // 2)
        return estimated_cost or 0.001  # Default small cost if estimation fails
    
    def _estimate_time(self, model: ModelConfig, tier: ModelTier) -> float:
        """Estimate response time for a model."""
        # Use performance tracking data
        base_time = self._tier_performance[tier]["avg_time"]
        
        # Adjust based on model specifics
        if model.specs.tokens_per_second:
            # Better estimate based on throughput
            estimated_tokens = 1000
            generation_time = estimated_tokens / model.specs.tokens_per_second
            return generation_time + 0.5  # Add network/processing overhead
        
        return base_time
    
    def _generate_routing_reasoning(
        self,
        action_analysis: ActionAnalysis,
        target_tier: ModelTier,
        actual_tier: ModelTier,
        selected_model: ModelConfig,
        strategy: RoutingStrategy
    ) -> str:
        """Generate human-readable reasoning for the routing decision."""
        reasons = []
        
        # Action analysis reasoning
        reasons.append(f"Action: {action_analysis.action_type.value}")
        reasons.append(f"Vision required: {action_analysis.requires_vision}")
        reasons.append(f"Complexity: {action_analysis.complexity.value}")
        reasons.append(f"Confidence: {action_analysis.confidence_score:.2f}")
        
        # Tier selection reasoning
        if target_tier != actual_tier:
            reasons.append(f"Escalated from {target_tier.value} to {actual_tier.value}")
        else:
            reasons.append(f"Target tier: {target_tier.value}")
        
        # Strategy reasoning
        reasons.append(f"Strategy: {strategy.value}")
        
        # Model selection reasoning
        reasons.append(f"Selected: {selected_model.name} ({selected_model.provider.value})")
        
        return "; ".join(reasons)
    
    def _record_routing_decision(self, decision: RoutingDecision):
        """Record routing decision for analysis."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "action_type": decision.action_analysis.action_type.value,
            "requires_vision": decision.action_analysis.requires_vision,
            "complexity": decision.action_analysis.complexity.value,
            "selected_tier": decision.selected_tier.value,
            "selected_model": decision.selected_model.name,
            "estimated_cost": decision.estimated_cost,
            "estimated_time": decision.estimated_time,
            "confidence": decision.confidence,
            "reasoning": decision.reasoning
        }
        
        self._routing_history.append(record)
        
        # Keep only recent history
        if len(self._routing_history) > 1000:
            self._routing_history = self._routing_history[-800:]
    
    def get_enhanced_routing_stats(self) -> Dict[str, Any]:
        """Get enhanced routing statistics."""
        base_stats = self.get_routing_stats()
        
        # Add three-tier specific stats
        tier_distribution = {}
        if self._routing_history:
            for record in self._routing_history:
                tier = record.get("selected_tier", "unknown")
                tier_distribution[tier] = tier_distribution.get(tier, 0) + 1
        
        # Calculate efficiency metrics
        total_decisions = self._escalation_stats["total_decisions"]
        if total_decisions > 0:
            escalation_rate = (
                self._escalation_stats["text_to_vision"] +
                self._escalation_stats["vision_to_cloud"] +
                self._escalation_stats["text_to_cloud"]
            ) / total_decisions
        else:
            escalation_rate = 0.0
        
        enhanced_stats = {
            **base_stats,
            "three_tier_stats": {
                "tier_distribution": tier_distribution,
                "escalation_stats": self._escalation_stats.copy(),
                "escalation_rate": escalation_rate,
                "tier_performance": self._tier_performance.copy()
            }
        }
        
        return enhanced_stats
    
    def _should_use_planner(self, task_requirements: EnhancedTaskRequirements) -> bool:
        """Always use planner if available - o3-2025-04-16 is smart enough to handle any query."""
        return self.task_planner is not None
    
    async def _create_task_plan(self, task_requirements: EnhancedTaskRequirements) -> Optional[TaskPlan]:
        """Create a task plan using o3-2025-04-16 planner."""
        if not self.task_planner:
            self.logger.warning("Task planner not available")
            return None
        
        try:
            # Build context for the planner
            context = {}
            if task_requirements.current_url:
                context["current_url"] = task_requirements.current_url
            if task_requirements.browser_state:
                context["browser_state"] = task_requirements.browser_state
            if task_requirements.action_context:
                context["action_context"] = task_requirements.action_context
                
            # Add user preferences to context
            preferences = {}
            if task_requirements.prefer_speed:
                preferences["prefer_speed"] = True
            if task_requirements.prefer_cost:
                preferences["prefer_cost"] = True
                
            if preferences:
                context["user_preferences"] = preferences
            
            self.logger.info(f"Creating task plan for: {task_requirements.task_description[:100]}...")
            
            # Create the plan
            plan = await self.task_planner.create_plan(
                task_requirements.task_description,
                context
            )
            
            if plan:
                self.logger.info(
                    f"Plan created: {plan.strategy.value} strategy, "
                    f"{len(plan.steps)} steps, "
                    f"confidence: {plan.confidence:.2f}"
                )
                
                # Log plan steps for debugging
                for i, step in enumerate(plan.steps[:3]):  # Show first 3 steps
                    self.logger.debug(f"Step {i+1}: {step.action_type.value} - {step.description[:50]}...")
                    
            return plan
            
        except Exception as e:
            self.logger.error(f"Task planning failed: {e}")
            return None