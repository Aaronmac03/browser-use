"""
Three-Tier Agent Implementation

This module implements the ThreeTierAgent that uses the centralized model configuration
to execute browser automation tasks with proper escalation chains.
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from config.central_model_config import (
    CENTRAL_MODEL_CONFIG,
    get_planner_model,
    get_tier_models,
    get_escalation_chain,
    get_primary_model,
    ModelTier,
    ModelConfig
)
from models.cloud_handler import CloudModelManager
from utils.serper import SerperAPI


@dataclass
class TaskResult:
    """Result of a three-tier task execution."""
    success: bool
    result: Optional[str] = None
    error: Optional[str] = None
    model_used: Optional[str] = None
    tier_used: Optional[str] = None
    execution_time: float = 0.0
    escalation_path: Optional[List[str]] = None


class ThreeTierAgent:
    """
    Three-tier agent that uses centralized model configuration for browser automation.
    
    Architecture:
    1. Planning phase: Uses o3-2025-04-16 for task planning
    2. Execution phase: Uses escalation chain (Text → Vision → Cloud)
    3. Automatic fallback on model failures
    """
    
    def __init__(
        self,
        browser_session,
        serper_api: Optional[SerperAPI] = None,
        cloud_manager: Optional[CloudModelManager] = None
    ):
        """
        Initialize the three-tier agent.
        
        Args:
            browser_session: Browser session for web automation
            serper_api: Optional Serper API for search functionality
            cloud_manager: Cloud model manager for cloud models
        """
        self.browser_session = browser_session
        self.serper_api = serper_api
        self.cloud_manager = cloud_manager
        self.logger = logging.getLogger(__name__)
        
        # Execution statistics
        self._execution_stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "tier_usage": {"text_local": 0, "vision_local": 0, "cloud": 0},
            "total_execution_time": 0.0
        }
    
    async def execute_task(self, task: str) -> TaskResult:
        """
        Execute a task using the three-tier architecture.
        
        Args:
            task: Task description to execute
            
        Returns:
            TaskResult with execution details
        """
        start_time = time.time()
        escalation_path = []
        
        try:
            self.logger.info(f"Starting three-tier execution for task: {task}")
            
            # Phase 1: Planning with o3-2025-04-16
            self.logger.info("Phase 1: Planning with planner model")
            planner_model = get_planner_model()
            
            # For now, we'll simulate the planning phase
            # In a real implementation, this would use the planner model to break down the task
            plan = await self._simulate_planning(task, planner_model)
            
            # Phase 2: Execution with escalation chain
            self.logger.info("Phase 2: Execution with escalation chain")
            
            # Determine if vision is required (simple heuristic for demo)
            requires_vision = any(keyword in task.lower() for keyword in [
                "screenshot", "image", "visual", "see", "look", "click", "button", "element"
            ])
            
            # Get escalation chain
            escalation_chain = get_escalation_chain(requires_vision=requires_vision)
            
            # Try each tier in the escalation chain
            for tier in escalation_chain:
                tier_name = tier.value
                escalation_path.append(tier_name)
                
                try:
                    self.logger.info(f"Trying tier: {tier_name}")
                    primary_model = get_primary_model(tier)
                    
                    # Execute with this tier
                    result = await self._execute_with_tier(task, plan, primary_model, tier)
                    
                    if result:
                        # Success!
                        execution_time = time.time() - start_time
                        
                        # Update statistics
                        self._update_stats(tier_name, execution_time, success=True)
                        
                        return TaskResult(
                            success=True,
                            result=result,
                            model_used=primary_model.name,
                            tier_used=tier_name,
                            execution_time=execution_time,
                            escalation_path=escalation_path
                        )
                        
                except Exception as e:
                    self.logger.warning(f"Tier {tier_name} failed: {e}")
                    continue
            
            # All tiers failed
            execution_time = time.time() - start_time
            self._update_stats("unknown", execution_time, success=False)
            
            return TaskResult(
                success=False,
                error="All tiers in escalation chain failed",
                execution_time=execution_time,
                escalation_path=escalation_path
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            self._update_stats("unknown", execution_time, success=False)
            
            return TaskResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
                escalation_path=escalation_path
            )
    
    async def _simulate_planning(self, task: str, planner_model: ModelConfig) -> str:
        """
        Simulate the planning phase.
        
        In a real implementation, this would use the planner model to create
        a detailed execution plan.
        """
        self.logger.info(f"Planning with {planner_model.name}")
        
        # Simulate planning delay
        await asyncio.sleep(0.1)
        
        # Return a simple plan
        return f"Plan for '{task}': Navigate to target, perform action, verify result"
    
    async def _execute_with_tier(
        self, 
        task: str, 
        plan: str, 
        model: ModelConfig, 
        tier: ModelTier
    ) -> Optional[str]:
        """
        Execute the task with a specific tier/model.
        
        Args:
            task: Original task description
            plan: Execution plan from planner
            model: Model configuration to use
            tier: Tier being used
            
        Returns:
            Execution result or None if failed
        """
        self.logger.info(f"Executing with {model.name} ({tier.value})")
        
        # Simulate execution based on tier
        if tier == ModelTier.TEXT_LOCAL:
            return await self._execute_text_task(task, model)
        elif tier == ModelTier.VISION_LOCAL:
            return await self._execute_vision_task(task, model)
        elif tier == ModelTier.CLOUD:
            return await self._execute_cloud_task(task, model)
        else:
            raise ValueError(f"Unknown tier: {tier}")
    
    async def _execute_text_task(self, task: str, model: ModelConfig) -> Optional[str]:
        """Execute a text-only task."""
        # Simulate text-only execution
        await asyncio.sleep(0.2)
        
        # For demo purposes, simulate success for simple navigation tasks
        if any(keyword in task.lower() for keyword in ["google", "search", "navigate"]):
            return f"Successfully executed text task: {task} using {model.name}"
        
        # Simulate failure for complex tasks that need vision
        if any(keyword in task.lower() for keyword in ["click", "button", "element", "screenshot"]):
            return None  # Escalate to vision tier
        
        return f"Text execution result for: {task}"
    
    async def _execute_vision_task(self, task: str, model: ModelConfig) -> Optional[str]:
        """Execute a vision-capable task."""
        # Simulate vision execution
        await asyncio.sleep(0.5)
        
        # For demo purposes, simulate success for most visual tasks
        if any(keyword in task.lower() for keyword in ["click", "button", "element", "visual"]):
            return f"Successfully executed vision task: {task} using {model.name}"
        
        # Simulate failure for very complex tasks
        if "complex" in task.lower() or "expert" in task.lower():
            return None  # Escalate to cloud
        
        return f"Vision execution result for: {task}"
    
    async def _execute_cloud_task(self, task: str, model: ModelConfig) -> Optional[str]:
        """Execute a cloud-based task."""
        # Simulate cloud execution
        await asyncio.sleep(1.0)
        
        # Cloud models should handle most tasks
        return f"Successfully executed cloud task: {task} using {model.name}"
    
    def _update_stats(self, tier_name: str, execution_time: float, success: bool):
        """Update execution statistics."""
        self._execution_stats["total_executions"] += 1
        self._execution_stats["total_execution_time"] += execution_time
        
        if success:
            self._execution_stats["successful_executions"] += 1
        
        if tier_name in self._execution_stats["tier_usage"]:
            self._execution_stats["tier_usage"][tier_name] += 1
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        stats = self._execution_stats.copy()
        
        if stats["total_executions"] > 0:
            stats["success_rate"] = stats["successful_executions"] / stats["total_executions"]
            stats["average_execution_time"] = stats["total_execution_time"] / stats["total_executions"]
        else:
            stats["success_rate"] = 0.0
            stats["average_execution_time"] = 0.0
        
        return stats