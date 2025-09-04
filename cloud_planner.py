#!/usr/bin/env python3
"""
Cloud Planner for Browser-Use Hybrid Architecture
Strategic task decomposition to maximize local LLM success while minimizing cloud usage.
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from dotenv import load_dotenv
from browser_use import ChatOpenAI
from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import SystemMessage, UserMessage
from pydantic import BaseModel

load_dotenv()
logger = logging.getLogger(__name__)

class TaskComplexity(Enum):
	"""Task complexity levels for routing decisions."""
	SIMPLE = "simple"      # Direct navigation, single actions
	MODERATE = "moderate"  # Multi-step workflows, form filling  
	COMPLEX = "complex"    # Shopping, account management, research

class TaskStep(BaseModel):
	"""Individual step in a task decomposition."""
	step_number: int
	action: str
	description: str
	success_criteria: str
	fallback_strategy: Optional[str] = None
	expected_duration: int = 30  # seconds

class TaskPlan(BaseModel):
	"""Complete task decomposition plan."""
	original_task: str
	complexity: TaskComplexity
	total_steps: int
	steps: List[TaskStep]
	estimated_duration: int  # total seconds
	privacy_notes: str = "All web interactions executed locally"

class RecoveryPlan(BaseModel):
	"""Recovery strategy when local LLM gets stuck."""
	stuck_step: int
	issue_description: str
	recovery_actions: List[str]
	alternative_approach: Optional[str] = None

@dataclass 
class CloudPlannerConfig:
	"""Configuration for cloud planner usage."""
	model: str = "o3"  # Default to o3 to match ROADMAP and runner usage
	max_planning_calls: int = 2     # Limit cloud usage (1-2 calls/goal per roadmap)
	planning_timeout: int = 30      # Fast planning responses
	enable_recovery: bool = True    # Allow recovery planning
	
class CloudPlanner:
	"""Strategic task planner that minimizes cloud usage while maximizing local LLM success."""
	
	def __init__(self, config: CloudPlannerConfig = None):
		self.config = config or CloudPlannerConfig()
		self.planning_calls_used = 0
		self._client = None
	
	def _get_cloud_client(self) -> BaseChatModel:
		"""Get cloud LLM client for strategic planning only."""
		if self._client is None:
			api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
			if not api_key:
				raise ValueError("No cloud API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY")
			
			if "claude" in self.config.model:
				from browser_use.llm.anthropic import ChatAnthropic
				self._client = ChatAnthropic(model=self.config.model)
			else:
				self._client = ChatOpenAI(model=self.config.model)
			
			logger.info(f"☁️ Cloud planner ready: {self.config.model}")
		return self._client
	
	async def plan_task(self, task: str) -> TaskPlan:
		"""
		Decompose complex task into local LLM-friendly steps.
		This is the primary cloud usage - strategic planning only.
		"""
		if self.planning_calls_used >= self.config.max_planning_calls:
			logger.warning("⚠️ Max planning calls reached, using fallback decomposition")
			return self._fallback_plan(task)
		
		self.planning_calls_used += 1
		
		system_prompt = """You are a web automation strategist. Your job is to break down complex web tasks into simple, sequential steps that a local 7B LLM can execute reliably.

PRIVACY FIRST: The local LLM will execute ALL web interactions. You only provide the strategy.

DESIGN PRINCIPLES:
- Each step should be a single, clear action
- Steps should be sequential and logically connected  
- Provide specific success criteria for each step
- Include fallback strategies for common failure points
- Optimize for local LLM capabilities (direct navigation, clear targets)

STEP CATEGORIES:
- Navigate: Go to specific URL or click navigation link
- Search: Use search functionality to find items/information
- Interact: Fill forms, click buttons, select options
- Verify: Check that expected content/state is present
- Complete: Finalize task (submit, purchase, save, etc.)

OUTPUT REQUIREMENTS:
- Maximum 8 steps (local LLM context limits)
- Each step must be independently executable
- Clear success/failure criteria for each step"""

		user_prompt = f"""Plan this web automation task: {task}

Break it down into simple steps that a local 7B model can execute reliably. Focus on direct, efficient navigation patterns.

Consider these optimization factors:
- Local LLM prefers single actions per step
- Direct element interaction over complex reasoning
- Clear success indicators for each step
- Privacy-first approach (all web content stays local)

Return a structured plan with numbered steps, success criteria, and estimated duration."""

		try:
			response = await self._get_cloud_client().ainvoke([
				SystemMessage(content=system_prompt),
				UserMessage(content=user_prompt)
			], output_format=TaskPlan)
			
			plan = response.completion
			logger.info(f"📋 Task planned: {plan.total_steps} steps, {plan.complexity.value} complexity")
			return plan
			
		except Exception as e:
			logger.error(f"❌ Cloud planning failed: {e}")
			return self._fallback_plan(task)
	
	async def create_recovery_plan(
		self, 
		original_plan: TaskPlan, 
		stuck_step: int,
		error_context: str
	) -> RecoveryPlan:
		"""
		Generate recovery strategy when local LLM gets stuck.
		Minimal cloud usage for unsticking local execution.
		"""
		if not self.config.enable_recovery:
			return self._fallback_recovery(stuck_step, error_context)
		
		if self.planning_calls_used >= self.config.max_planning_calls:
			logger.warning("⚠️ Max planning calls reached, using fallback recovery")
			return self._fallback_recovery(stuck_step, error_context)
		
		self.planning_calls_used += 1
		
		system_prompt = """You are a web automation troubleshooter. A local 7B LLM got stuck during task execution and needs guidance to continue.

Your job is to provide specific recovery actions that will get the local LLM back on track.

RECOVERY PRINCIPLES:
- Diagnose the likely issue from the error context
- Provide specific, actionable recovery steps
- Consider alternative approaches if the current path is blocked
- Keep recovery simple - local LLM capabilities in mind
- Maintain privacy-first approach"""

		stuck_step_info = original_plan.steps[stuck_step - 1] if stuck_step <= len(original_plan.steps) else None
		
		user_prompt = f"""Local LLM got stuck executing this task plan:
Original task: {original_plan.original_task}
Stuck at step: {stuck_step}
Step details: {stuck_step_info.description if stuck_step_info else 'Unknown step'}
Error context: {error_context}

Provide recovery guidance to help the local LLM continue. Focus on simple, direct actions."""

		try:
			response = await self._get_cloud_client().ainvoke([
				SystemMessage(content=system_prompt), 
				UserMessage(content=user_prompt)
			], output_format=RecoveryPlan)
			
			recovery = response.completion
			logger.info(f"🔧 Recovery plan created for step {stuck_step}")
			return recovery
			
		except Exception as e:
			logger.error(f"❌ Recovery planning failed: {e}")
			return self._fallback_recovery(stuck_step, error_context)
	
	def _classify_task_complexity(self, task: str) -> TaskComplexity:
		"""Simple heuristic to classify task complexity."""
		task_lower = task.lower()
		
		# Complex indicators
		complex_indicators = [
			"buy", "purchase", "checkout", "payment", "order",
			"create account", "sign up", "register", "login",
			"compare", "research", "multiple", "complex"
		]
		
		# Simple indicators  
		simple_indicators = [
			"navigate to", "go to", "visit", "click", "find",
			"search for", "look for", "check"
		]
		
		if any(indicator in task_lower for indicator in complex_indicators):
			return TaskComplexity.COMPLEX
		elif any(indicator in task_lower for indicator in simple_indicators):
			return TaskComplexity.SIMPLE
		else:
			return TaskComplexity.MODERATE
	
	def _fallback_plan(self, task: str) -> TaskPlan:
		"""Fallback task decomposition when cloud planning fails."""
		complexity = self._classify_task_complexity(task)
		
		# Generic decomposition based on task complexity
		if complexity == TaskComplexity.SIMPLE:
			steps = [
				TaskStep(
					step_number=1,
					action="navigate",
					description=f"Navigate to target site for: {task}",
					success_criteria="Page loads successfully",
					expected_duration=15
				),
				TaskStep(
					step_number=2, 
					action="complete",
					description=f"Complete the task: {task}",
					success_criteria="Task objective achieved",
					expected_duration=30
				)
			]
		else:
			# More detailed breakdown for complex tasks
			steps = [
				TaskStep(step_number=1, action="navigate", description="Navigate to target website", success_criteria="Homepage loads", expected_duration=15),
				TaskStep(step_number=2, action="search", description="Find target content/functionality", success_criteria="Relevant results found", expected_duration=20),
				TaskStep(step_number=3, action="interact", description="Interact with found elements", success_criteria="Action completed", expected_duration=25),
				TaskStep(step_number=4, action="verify", description="Verify task completion", success_criteria="Success confirmed", expected_duration=10),
			]
		
		return TaskPlan(
			original_task=task,
			complexity=complexity,
			total_steps=len(steps),
			steps=steps,
			estimated_duration=sum(step.expected_duration for step in steps),
			privacy_notes="Fallback plan - all execution local"
		)
	
	def _fallback_recovery(self, stuck_step: int, error_context: str) -> RecoveryPlan:
		"""Fallback recovery strategy."""
		return RecoveryPlan(
			stuck_step=stuck_step,
			issue_description=f"Step {stuck_step} failed: {error_context}",
			recovery_actions=[
				"Wait 3 seconds for page to load completely",
				"Try clicking a different but related element",
				"Scroll down to find the target element",
				"Refresh the page and retry the action"
			],
			alternative_approach="Try a different navigation path to reach the same goal"
		)
	
	def get_usage_stats(self) -> Dict[str, int]:
		"""Get cloud usage statistics."""
		return {
			"planning_calls_used": self.planning_calls_used,
			"max_planning_calls": self.config.max_planning_calls,
			"remaining_calls": self.config.max_planning_calls - self.planning_calls_used
		}

# Usage example and testing
async def test_cloud_planner():
	"""Test the cloud planner with a complex task."""
	planner = CloudPlanner()
	
	# Test task decomposition
	complex_task = "Go to walmart.com and find a store locator, then look up stores near zip code 90210"
	
	print("☁️ Testing Cloud Planner...")
	plan = await planner.plan_task(complex_task)
	
	print(f"📋 Generated Plan:")
	print(f"  Task: {plan.original_task}")
	print(f"  Complexity: {plan.complexity.value}")
	print(f"  Steps: {plan.total_steps}")
	print(f"  Duration: {plan.estimated_duration}s")
	
	for step in plan.steps:
		print(f"    {step.step_number}. {step.action}: {step.description}")
	
	# Test usage stats
	stats = planner.get_usage_stats()
	print(f"\n📊 Cloud Usage: {stats['planning_calls_used']}/{stats['max_planning_calls']} calls")
	
	return planner

if __name__ == "__main__":
	asyncio.run(test_cloud_planner())