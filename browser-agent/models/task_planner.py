"""
Task Planner for Browser Automation with o3-2025-04-16.

This module implements intelligent task planning that:
1. Clarifies ambiguous user queries
2. Creates detailed execution plans 
3. Coordinates Serper API searches vs direct browser actions
4. Prevents local LLM wandering by providing clear navigation targets
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from models.cloud_handler import CloudModelManager
from utils.serper import SerperAPI, SearchFilters
from config.models import ModelConfigManager
from config.central_model_config import get_planner_model


class ActionType(str, Enum):
    """Types of actions the planner can recommend."""
    SEARCH_WEB = "search_web"           # Use Serper API to find information/websites
    NAVIGATE_TO = "navigate_to"         # Direct navigation to known URL
    BROWSER_ACTION = "browser_action"   # Local LLM browser interaction
    CLARIFY_QUERY = "clarify_query"     # Query needs user clarification


class PlanningStrategy(str, Enum):
    """Planning strategies."""
    SEARCH_FIRST = "search_first"       # Search before any browser actions
    DIRECT_ACTION = "direct_action"     # Go directly to known sites
    HYBRID = "hybrid"                   # Mix of search and direct actions


@dataclass
class PlanStep:
    """A single step in the execution plan."""
    action_type: ActionType
    description: str
    target_url: Optional[str] = None
    search_query: Optional[str] = None
    expected_outcome: str = ""
    fallback_action: Optional[str] = None
    estimated_time: float = 30.0  # seconds
    dependencies: List[int] = field(default_factory=list)  # Step indices this depends on


@dataclass
class TaskPlan:
    """Complete task execution plan."""
    original_query: str
    clarified_intent: str
    strategy: PlanningStrategy
    steps: List[PlanStep]
    total_estimated_time: float
    confidence: float  # 0.0 to 1.0
    requires_search: bool = False
    target_websites: List[str] = field(default_factory=list)
    reasoning: str = ""


class TaskPlanner:
    """Intelligent task planner using o3-2025-04-16."""
    
    def __init__(
        self,
        cloud_manager: CloudModelManager,
        serper_api: Optional[SerperAPI] = None,
        model_config_manager: Optional[ModelConfigManager] = None
    ):
        """Initialize the task planner."""
        self.cloud_manager = cloud_manager
        self.serper_api = serper_api
        self.model_config_manager = model_config_manager
        self.logger = logging.getLogger(__name__)
        
        # Use centralized configuration for planning model
        planner_config = get_planner_model()
        self.planning_model = planner_config.name
        self.logger.info(f"Task planner initialized with {self.planning_model} from centralized config")
        
        # Planning history for learning
        self._planning_history: List[Dict[str, Any]] = []
        
        # Common website patterns for direct navigation
        self._known_sites = {
            "google": "https://google.com",
            "amazon": "https://amazon.com", 
            "github": "https://github.com",
            "stackoverflow": "https://stackoverflow.com",
            "youtube": "https://youtube.com",
            "linkedin": "https://linkedin.com",
            "twitter": "https://twitter.com",
            "facebook": "https://facebook.com",
            "reddit": "https://reddit.com",
            "wikipedia": "https://wikipedia.org"
        }
    
    async def create_plan(
        self, 
        user_query: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> TaskPlan:
        """
        Create an intelligent execution plan for the user query.
        
        Args:
            user_query: Original user request
            context: Optional context (current page, user preferences, etc.)
            
        Returns:
            TaskPlan with detailed execution steps
        """
        self.logger.info(f"Creating plan for query: {user_query[:100]}...")
        
        # Step 1: Analyze the query and create plan
        plan_prompt = self._build_planning_prompt(user_query, context)
        
        try:
            # Get model config for o3-2025-04-16
            model_config = None
            if self.model_config_manager:
                model_config = self.model_config_manager.get_model_config(self.planning_model)
            
            if not model_config:
                # Create a temporary model config for o3-2025-04-16
                from config.models import ModelConfig, ModelProvider, ModelSpecs, ModelCapability
                model_config = ModelConfig(
                    name="o3-2025-04-16",
                    provider=ModelProvider.OPENAI,
                    model_id="o3-2025-04-16",
                    specs=ModelSpecs(
                        context_length=128000,
                        max_tokens=4096,
                        supports_vision=True,
                        supports_function_calling=True,
                        cost_per_1k_tokens=0.05
                    ),
                    capabilities=[ModelCapability.REASONING, ModelCapability.CODE],
                    temperature=0.1,
                    max_tokens=2048,
                    timeout=60
                )
            
            # Build full prompt for the planning model
            full_prompt = f"""{self._get_planning_system_prompt()}

{plan_prompt}"""
            
            # Use generate_text method
            planning_response = await self.cloud_manager.generate_text(
                model_config=model_config,
                prompt=full_prompt,
                max_tokens=2048,
                temperature=0.1
            )
            
            # Parse the planning response
            plan = await self._parse_planning_response(
                user_query, 
                planning_response,
                context
            )
            
            # Step 2: Enhance plan with search intelligence if needed
            if plan.requires_search and self.serper_api:
                plan = await self._enhance_plan_with_search(plan)
            
            # Step 3: Validate and optimize the plan
            plan = await self._validate_and_optimize_plan(plan)
            
            # Record the planning decision
            self._record_planning_decision(user_query, plan)
            
            self.logger.info(
                f"Created plan with {len(plan.steps)} steps, "
                f"strategy: {plan.strategy.value}, "
                f"confidence: {plan.confidence:.2f}"
            )
            
            return plan
            
        except Exception as e:
            self.logger.error(f"Planning failed: {e}")
            # Return a basic fallback plan
            return self._create_fallback_plan(user_query)
    
    def _get_planning_system_prompt(self) -> str:
        """Get the system prompt for the o3-2025-04-16 planner."""
        return """You are an expert browser automation task planner. Your job is to:

1. CLARIFY INTENT: Understand what the user really wants to accomplish
2. PLAN STRATEGY: Decide between search-first vs direct-action approaches  
3. IDENTIFY TARGETS: Specify exact websites/URLs to visit
4. CREATE STEPS: Break down the task into clear, executable steps
5. PREVENT WANDERING: Give local LLMs specific targets, not vague instructions

IMPORTANT PRINCIPLES:
- Always clarify ambiguous queries into specific, actionable intent
- Use web search to find the RIGHT websites before browsing
- Provide exact URLs whenever possible to prevent wandering
- Break complex tasks into simple, sequential steps
- Anticipate failure modes and provide fallbacks

Your response must be a JSON object with this structure:
{
  "clarified_intent": "Clear description of what user wants to accomplish",
  "strategy": "search_first|direct_action|hybrid", 
  "confidence": 0.85,
  "requires_search": true,
  "steps": [
    {
      "action_type": "search_web|navigate_to|browser_action",
      "description": "What to do in this step",
      "target_url": "https://specific-url.com (if known)",
      "search_query": "specific search terms (if searching)",
      "expected_outcome": "What should happen after this step",
      "estimated_time": 30.0
    }
  ],
  "reasoning": "Why you chose this approach"
}"""
    
    def _build_planning_prompt(self, user_query: str, context: Optional[Dict[str, Any]]) -> str:
        """Build the planning prompt for o3-2025-04-16."""
        prompt_parts = [
            f"USER QUERY: {user_query}",
            "",
            "CONTEXT:",
        ]
        
        if context:
            if context.get("current_url"):
                prompt_parts.append(f"- Currently on: {context['current_url']}")
            if context.get("user_preferences"):
                prompt_parts.append(f"- User preferences: {context['user_preferences']}")
            if context.get("previous_actions"):
                prompt_parts.append(f"- Previous actions: {context['previous_actions']}")
        else:
            prompt_parts.append("- No additional context provided")
        
        prompt_parts.extend([
            "",
            "AVAILABLE ACTIONS:",
            "1. search_web: Use Serper API to find information/websites",
            "2. navigate_to: Direct navigation to known URL", 
            "3. browser_action: Local LLM performs browser interactions",
            "",
            "KNOWN WEBSITES (can navigate directly):",
        ])
        
        for name, url in self._known_sites.items():
            prompt_parts.append(f"- {name}: {url}")
        
        prompt_parts.extend([
            "",
            "PLANNING GUIDELINES:",
            "- If query mentions specific sites (google, amazon, etc), use direct navigation",
            "- If query is vague ('find cheap laptops'), use search_first strategy",
            "- If query has specific product/info needs, search for best websites first",
            "- Break complex tasks into simple steps local LLMs can handle",
            "- Always provide specific URLs, not generic 'go to shopping site' instructions",
            "",
            "Create a detailed execution plan:"
        ])
        
        return "\n".join(prompt_parts)
    
    async def _parse_planning_response(
        self, 
        user_query: str,
        response_content: str,
        context: Optional[Dict[str, Any]]
    ) -> TaskPlan:
        """Parse the JSON response from o3-2025-04-16."""
        try:
            import json
            plan_data = json.loads(response_content)
            
            # Parse steps
            steps = []
            total_time = 0.0
            
            for i, step_data in enumerate(plan_data.get("steps", [])):
                step = PlanStep(
                    action_type=ActionType(step_data["action_type"]),
                    description=step_data["description"],
                    target_url=step_data.get("target_url"),
                    search_query=step_data.get("search_query"),
                    expected_outcome=step_data.get("expected_outcome", ""),
                    estimated_time=step_data.get("estimated_time", 30.0)
                )
                steps.append(step)
                total_time += step.estimated_time
            
            # Extract target websites
            target_websites = []
            for step in steps:
                if step.target_url:
                    # Extract domain from URL
                    try:
                        from urllib.parse import urlparse
                        domain = urlparse(step.target_url).netloc
                        if domain and domain not in target_websites:
                            target_websites.append(domain)
                    except:
                        pass
            
            return TaskPlan(
                original_query=user_query,
                clarified_intent=plan_data.get("clarified_intent", user_query),
                strategy=PlanningStrategy(plan_data.get("strategy", "hybrid")),
                steps=steps,
                total_estimated_time=total_time,
                confidence=plan_data.get("confidence", 0.8),
                requires_search=plan_data.get("requires_search", False),
                target_websites=target_websites,
                reasoning=plan_data.get("reasoning", "")
            )
            
        except Exception as e:
            self.logger.error(f"Failed to parse planning response: {e}")
            self.logger.debug(f"Response content: {response_content}")
            return self._create_fallback_plan(user_query)
    
    async def _enhance_plan_with_search(self, plan: TaskPlan) -> TaskPlan:
        """Enhance the plan by performing searches to find specific URLs."""
        if not self.serper_api:
            return plan
        
        enhanced_steps = []
        
        for step in plan.steps:
            if step.action_type == ActionType.SEARCH_WEB and step.search_query:
                try:
                    # Perform the search
                    filters = SearchFilters(num_results=5)
                    search_response = await self.serper_api.web_search(
                        step.search_query, 
                        filters
                    )
                    
                    if search_response.results:
                        # Replace search step with navigate steps
                        self.logger.info(f"Found {len(search_response.results)} results for '{step.search_query}'")
                        
                        # Add the top result as a navigation target
                        top_result = search_response.results[0]
                        enhanced_step = PlanStep(
                            action_type=ActionType.NAVIGATE_TO,
                            description=f"Navigate to {top_result.title}",
                            target_url=top_result.link,
                            expected_outcome=f"Access {top_result.title} - {top_result.snippet[:100]}",
                            estimated_time=step.estimated_time
                        )
                        enhanced_steps.append(enhanced_step)
                        
                        # Update target websites
                        try:
                            from urllib.parse import urlparse
                            domain = urlparse(top_result.link).netloc
                            if domain and domain not in plan.target_websites:
                                plan.target_websites.append(domain)
                        except:
                            pass
                    else:
                        # Keep original search step if no results
                        enhanced_steps.append(step)
                        
                except Exception as e:
                    self.logger.warning(f"Search enhancement failed: {e}")
                    enhanced_steps.append(step)
            else:
                enhanced_steps.append(step)
        
        plan.steps = enhanced_steps
        return plan
    
    async def _validate_and_optimize_plan(self, plan: TaskPlan) -> TaskPlan:
        """Validate and optimize the execution plan."""
        
        # 1. Check for missing steps
        if not plan.steps:
            self.logger.warning("Plan has no steps, creating basic navigation")
            plan.steps = [
                PlanStep(
                    action_type=ActionType.BROWSER_ACTION,
                    description=f"Accomplish: {plan.clarified_intent}",
                    expected_outcome="Complete user request",
                    estimated_time=60.0
                )
            ]
        
        # 2. Ensure all browser action steps have clear targets
        for i, step in enumerate(plan.steps):
            if step.action_type == ActionType.BROWSER_ACTION and not step.target_url:
                # Try to add a target URL if we can infer it
                if plan.target_websites:
                    step.target_url = f"https://{plan.target_websites[0]}"
                    self.logger.info(f"Added target URL to step {i}: {step.target_url}")
        
        # 3. Optimize step sequence
        optimized_steps = []
        for step in plan.steps:
            # Combine consecutive navigation steps to same domain
            if (optimized_steps and 
                optimized_steps[-1].action_type == ActionType.NAVIGATE_TO and
                step.action_type == ActionType.NAVIGATE_TO):
                
                # Check if same domain
                try:
                    from urllib.parse import urlparse
                    prev_domain = urlparse(optimized_steps[-1].target_url).netloc
                    curr_domain = urlparse(step.target_url).netloc
                    
                    if prev_domain == curr_domain:
                        # Skip this navigation, local LLM can handle it
                        self.logger.info(f"Optimized: Skipping redundant navigation to {curr_domain}")
                        continue
                except:
                    pass
            
            optimized_steps.append(step)
        
        plan.steps = optimized_steps
        
        # 4. Recalculate total time
        plan.total_estimated_time = sum(step.estimated_time for step in plan.steps)
        
        return plan
    
    def _create_fallback_plan(self, user_query: str) -> TaskPlan:
        """Create a basic fallback plan when planning fails."""
        return TaskPlan(
            original_query=user_query,
            clarified_intent=f"Accomplish: {user_query}",
            strategy=PlanningStrategy.DIRECT_ACTION,
            steps=[
                PlanStep(
                    action_type=ActionType.BROWSER_ACTION,
                    description=f"Complete task: {user_query}",
                    expected_outcome="Fulfill user request",
                    estimated_time=90.0
                )
            ],
            total_estimated_time=90.0,
            confidence=0.5,
            requires_search=True,
            reasoning="Fallback plan due to planning failure"
        )
    
    def _record_planning_decision(self, user_query: str, plan: TaskPlan):
        """Record planning decision for analysis and learning."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "user_query": user_query,
            "clarified_intent": plan.clarified_intent,
            "strategy": plan.strategy.value,
            "num_steps": len(plan.steps),
            "requires_search": plan.requires_search,
            "target_websites": plan.target_websites,
            "total_time": plan.total_estimated_time,
            "confidence": plan.confidence
        }
        
        self._planning_history.append(record)
        
        # Keep only recent history
        if len(self._planning_history) > 100:
            self._planning_history = self._planning_history[-80:]
    
    def get_planning_stats(self) -> Dict[str, Any]:
        """Get statistics about planning performance."""
        if not self._planning_history:
            return {"total_plans": 0}
        
        total_plans = len(self._planning_history)
        
        # Strategy distribution
        strategies = {}
        for record in self._planning_history:
            strategy = record["strategy"]
            strategies[strategy] = strategies.get(strategy, 0) + 1
        
        # Average metrics
        avg_steps = sum(r["num_steps"] for r in self._planning_history) / total_plans
        avg_confidence = sum(r["confidence"] for r in self._planning_history) / total_plans
        avg_time = sum(r["total_time"] for r in self._planning_history) / total_plans
        
        search_required = sum(1 for r in self._planning_history if r["requires_search"])
        
        return {
            "total_plans": total_plans,
            "strategy_distribution": strategies,
            "avg_steps_per_plan": avg_steps,
            "avg_confidence": avg_confidence,
            "avg_estimated_time": avg_time,
            "search_required_percentage": (search_required / total_plans) * 100,
            "most_common_strategy": max(strategies.keys(), key=strategies.get) if strategies else None
        }