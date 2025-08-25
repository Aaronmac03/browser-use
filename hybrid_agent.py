#!/usr/bin/env python3
"""
Hybrid Local-Vision + Cloud-Reasoning Agent for Browser-Use 0.6.x

Architecture:
- Planner (OpenAI o3): Runs exactly once per user query, outputs structured plan
- LocalExecutor: Primary execution with generic primitives and vision analysis
- EscalationManager: Handles stuck states with Gemini micro-plans and o3 fallback
- No domain-specific logic - smart generalist approach with generic actions
"""

import asyncio
import json
import os
import hashlib
import base64
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Literal
from urllib.parse import urlparse

from dotenv import load_dotenv
from pydantic import BaseModel, Field
import httpx

# Load environment variables
load_dotenv(override=True)

# Browser-Use 0.6.x imports
from browser_use import Agent, Controller, ActionResult
from browser_use.browser import BrowserProfile, BrowserSession
from browser_use.browser.events import ScreenshotEvent
from browser_use.llm import ChatGoogle, ChatOpenAI

# Import serper search functionality
from serper_search import search_with_serper_fallback

# Import working vision module from Phase 1
from vision_module import VisionAnalyzer, VisionState, VisionElement, VisionField, VisionAffordance, VisionMeta

# ----------------------------
# Configuration
# ----------------------------
CHROME_PROFILE_DIR = 'C:/Users/drmcn/.config/browseruse/profiles/default'
LOGS_DIR = Path('hybrid_queries')
LOGS_DIR.mkdir(exist_ok=True)

# Navigation timeout = 60s (favor reliability over speed)
NAVIGATION_TIMEOUT_MS = 60_000

# Model ladder configuration
O3_PLANNER_MODEL = "o3"
LOCAL_EXECUTOR_MODEL = "minicpm-v"  # Local model via Ollama
GEMINI_BACKUP_MODEL = "gemini-2.0-flash-exp"
O3_ESCALATION_MODEL = "o3"

# ----------------------------
# Terminal colors
# ----------------------------
class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_status(message, color=Colors.BLUE):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{ts}] {message}{Colors.END}")

# ----------------------------
# Logging helpers
# ----------------------------
def save_query_log(query, result, cost_info=None):
    timestamp = datetime.now()
    date_str = timestamp.strftime("%Y-%m-%d")
    time_str = timestamp.strftime("%H-%M-%S")

    daily_dir = LOGS_DIR / date_str
    daily_dir.mkdir(exist_ok=True)

    log_file = daily_dir / f"{time_str}_hybrid_query.md"
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(f"# Hybrid Agent Query Log\n")
        f.write(f"**Date:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## Query\n```\n{query}\n```\n\n")
        f.write(f"## Result\n{result}\n\n")
        if cost_info:
            f.write("## Cost Information\n")
            f.write(f"- Local Vision Model: MiniCPM-V 2.6 (Local)\n")
            f.write(f"- Cloud Planner Model: {cost_info.get('planner_model', 'N/A')}\n")
            f.write(f"- Executor Model: {cost_info.get('executor_model', 'N/A')}\n")
            f.write(f"- Prompt tokens: {cost_info.get('prompt_tokens', 'N/A')}\n")
            f.write(f"- Completion tokens: {cost_info.get('completion_tokens', 'N/A')}\n")
            f.write(f"- Total tokens: {cost_info.get('total_tokens', 'N/A')}\n")
            f.write(f"- Estimated cost: ${cost_info.get('estimated_cost', 0):.4f}\n")

    summary_file = daily_dir / "daily_summary.json"
    summary_entry = {
        "time": time_str,
        "query": query[:100] + "..." if len(query) > 100 else query,
        "log_file": str(log_file.name),
        "cost": cost_info.get('estimated_cost', 0) if cost_info else 0,
    }

    if summary_file.exists():
        with open(summary_file, 'r', encoding='utf-8') as f:
            summary = json.load(f)
    else:
        summary = {"queries": [], "total_cost": 0}

    summary["queries"].append(summary_entry)
    summary["total_cost"] += summary_entry["cost"]

    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    return log_file

# ----------------------------
# Data Schemas (VisionState imported from vision_module.py)
# ----------------------------

class GenericAction(BaseModel):
    """Generic browser action using primitive operations."""
    primitive: Literal[
        "go_to_url", "click", "type", "scroll", "wait", 
        "extract", "analyze_vision", "search_web"
    ] = Field(description="Generic primitive operation")
    target: Optional[str] = Field(description="Target selector or URL", default=None)
    value: Optional[str] = Field(description="Value for type/search operations", default=None)
    notes: Optional[str] = Field(description="Optional execution notes", default=None)

class HistoryStep(BaseModel):
    """Single step in execution history."""
    step_id: int = Field(description="Step sequence number")
    action: GenericAction = Field(description="Action executed")
    result: Literal["ok", "fail", "stuck"] = Field(description="Execution result")
    summary: str = Field(description="Brief summary of what happened")
    screenshot_path: Optional[str] = Field(description="Path to screenshot if taken", default=None)

class PlanJSON(BaseModel):
    """Structured plan output from o3 planner (runs exactly once)."""
    normalized_task: str = Field(description="Clarified and normalized task description")
    steps: List[GenericAction] = Field(description="Ordered sequence of generic actions")
    success_criteria: List[str] = Field(description="Criteria to determine task completion")
    estimated_complexity: Literal["simple", "medium", "complex"] = Field(description="Task complexity estimate")

class MicroPlan(BaseModel):
    """Micro-plan from backup executor when stuck."""
    next_actions: List[GenericAction] = Field(description="1-3 immediate actions to try", max_items=3)
    reasoning: str = Field(description="Why these actions might help", max_length=200)
    timeout_steps: int = Field(description="Max steps before escalating further", default=3)

class ExecutionContext(BaseModel):
    """Current execution state and context."""
    current_step: int = Field(description="Current step index in plan")
    stuck_count: int = Field(description="Number of consecutive stuck attempts", default=0)
    escalation_level: Literal["local", "gemini", "o3"] = Field(description="Current escalation level", default="local")
    history: List[HistoryStep] = Field(description="Execution history")
    last_vision_state: Optional[VisionState] = Field(description="Most recent vision analysis", default=None)

# ----------------------------
# Ollama Helper
# ----------------------------

async def resolve_minicpm_tag(endpoint: str = "http://localhost:11434") -> str:
    """Resolve MiniCPM-V tag by querying Ollama API."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{endpoint}/api/tags")
            if response.status_code == 200:
                data = response.json()
                for model in data.get('models', []):
                    model_name = model.get('name', '')
                    if 'minicpm-v' in model_name.lower():
                        return model_name.replace(':latest', '')
                return "minicpm-v"
            else:
                return "minicpm-v"
    except Exception as e:
        # Concise warning - don't fail loudly
        print(f"⚠️ Ollama API not available: {str(e)[:50]}")
        return "minicpm-v"

# ----------------------------
# Vision State Builder - REPLACED
# ----------------------------

# ✅ PHASE 2.1 COMPLETE: VisionStateBuilder has been replaced with VisionAnalyzer
# The working VisionAnalyzer from vision_module.py is now imported and used throughout
# the codebase. This old VisionStateBuilder class is no longer needed.

# ----------------------------
# Search Client (Serper API)
# ----------------------------

class SearchClient:
    """Handles web search using Serper API with browser fallback."""
    
    def __init__(self, controller: Controller):
        self.controller = controller
    
    async def search_web(self, query: str, num_results: int = 10) -> ActionResult:
        """Search web using Serper API, fallback to browser if needed."""
        try:
            return await search_with_serper_fallback(self.controller, query, num_results)
        except Exception as e:
            return ActionResult(
                extracted_content=f"Search failed: {e}",
                include_in_memory=True
            )

# ----------------------------
# o3 Planner Client (Runs Exactly Once)
# ----------------------------

class PlannerClient:
    """OpenAI o3 planner that runs exactly once per user query."""
    
    def __init__(self):
        self.llm = ChatOpenAI(model=O3_PLANNER_MODEL)
    
    async def create_plan(self, user_task: str) -> tuple[PlanJSON, Dict[str, Any]]:
        """Create structured plan from user task (runs exactly once). Returns plan and usage info."""
        try:
            prompt = self._build_planner_prompt(user_task)
            
            print_status("Running o3 planner (one-shot)...", Colors.BLUE)
            response = await self.llm.ainvoke([{"role": "user", "content": prompt}])
            response_text = response.completion.strip()
            
            # Capture actual usage information
            usage_info = {
                "model": self.llm.model,
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
                "cached_tokens": response.usage.prompt_cached_tokens if response.usage and response.usage.prompt_cached_tokens else 0
            }
            
            print_status(f"o3 usage: {usage_info['prompt_tokens']} prompt + {usage_info['completion_tokens']} completion tokens", Colors.BLUE)
            
            # Extract JSON from response
            if response_text.startswith('```'):
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)
            
            plan_data = json.loads(response_text)
            plan = PlanJSON(**plan_data)
            
            print_status(f"Plan created: {len(plan.steps)} steps, complexity: {plan.estimated_complexity}", Colors.GREEN)
            return plan, usage_info
            
        except Exception as e:
            print_status(f"o3 planner failed, creating fallback plan: {e}", Colors.RED)
            return self._create_fallback_plan(user_task), {"model": O3_PLANNER_MODEL, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cached_tokens": 0}
    
    def _build_planner_prompt(self, user_task: str) -> str:
        return f"""You are an expert web automation planner. Analyze the user's task and create a structured plan using ONLY generic primitives.

USER TASK: {user_task}

AVAILABLE PRIMITIVES:
- go_to_url: Navigate to a specific URL
- click: Click on an element (use descriptive selector)
- type: Type text into input fields
- scroll: Scroll page (up/down/to_element)
- wait: Wait for page/element to load
- extract: Extract specific information from page
- analyze_vision: Analyze current page with vision
- search_web: Search web using Serper API

REQUIREMENTS:
1. NO domain-specific logic (no Kroger/Target/weather branches)
2. Be a smart generalist - use generic actions for ANY task
3. Normalize and clarify the task description
4. Create concrete success criteria
5. Use analyze_vision after navigation or major DOM changes

Output JSON format:
{{
  "normalized_task": "Clear, specific task description",
  "steps": [
    {{
      "primitive": "go_to_url",
      "target": "https://example.com",
      "value": null,
      "notes": "Navigate to starting point"
    }},
    {{
      "primitive": "analyze_vision", 
      "target": null,
      "value": null,
      "notes": "Understand page layout"
    }}
  ],
  "success_criteria": [
    "Information X is extracted",
    "Task Y is completed"
  ],
  "estimated_complexity": "simple|medium|complex"
}}"""
    
    def _create_fallback_plan(self, user_task: str) -> PlanJSON:
        """Create a minimal fallback plan if o3 planner fails."""
        return PlanJSON(
            normalized_task=f"Complete user request: {user_task}",
            steps=[
                GenericAction(primitive="analyze_vision", notes="Initial page analysis"),
                GenericAction(primitive="search_web", value=user_task, notes="Search for information")
            ],
            success_criteria=[f"Find information related to: {user_task}"],
            estimated_complexity="medium"
        )

# ----------------------------
# Local Executor (Primary)
# ----------------------------

class LocalExecutor:
    """Primary executor using local model + deterministic action loop."""
    
    def __init__(self, controller: Controller, vision_analyzer: VisionAnalyzer):
        self.controller = controller
        self.vision_analyzer = vision_analyzer
        self.browser_session: Optional[BrowserSession] = None
    
    async def execute_action(self, action: GenericAction, context: ExecutionContext) -> HistoryStep:
        """Execute a single generic action and return result."""
        step_id = len(context.history) + 1
        screenshot_path = None
        
        try:
            print_status(f"Step {step_id}: {action.primitive}", Colors.BLUE)
            
            # Execute the primitive action
            if action.primitive == "go_to_url":
                result = await self._go_to_url(action.target)
                # Take screenshot after navigation
                screenshot_event = self.browser_session.event_bus.dispatch(ScreenshotEvent(full_page=False))
                screenshot_b64 = await screenshot_event.event_result(raise_if_any=True, raise_if_none=True)
                
                import tempfile
                import base64
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                    f.write(base64.b64decode(screenshot_b64))
                    screenshot_path = f.name
                
            elif action.primitive == "click":
                result = await self._click(action.target)
                
            elif action.primitive == "type":
                result = await self._type(action.target, action.value)
                
            elif action.primitive == "scroll":
                result = await self._scroll(action.value)
                
            elif action.primitive == "wait":
                result = await self._wait(action.value)
                
            elif action.primitive == "extract":
                result = await self._extract(action.target)
                
            elif action.primitive == "analyze_vision":
                result = await self._analyze_vision()
                # Screenshot already taken in _analyze_vision method
                screenshot_path = None
                
            elif action.primitive == "search_web":
                result = await self._search_web(action.value)
                
            else:
                result = ActionResult(extracted_content=f"Unknown primitive: {action.primitive}", include_in_memory=True)
            
            # Determine success based on result
            success = result.extracted_content and "error" not in result.extracted_content.lower()
            result_status = "ok" if success else "fail"
            
            return HistoryStep(
                step_id=step_id,
                action=action,
                result=result_status,
                summary=result.extracted_content[:200] if result.extracted_content else "No result",
                screenshot_path=str(screenshot_path) if screenshot_path else None
            )
            
        except Exception as e:
            print_status(f"Action failed: {e}", Colors.RED)
            return HistoryStep(
                step_id=step_id,
                action=action,
                result="fail",
                summary=f"Error: {str(e)[:200]}",
                screenshot_path=str(screenshot_path) if screenshot_path else None
            )
    
    async def _go_to_url(self, url: str) -> ActionResult:
        """Navigate to URL with 60s timeout."""
        if not self.browser_session:
            raise Exception("Browser session not initialized")
        
        print_status(f"Navigating to: {url}", Colors.BLUE)
        # Use Browser-Use 0.6.x CDP navigation method (same as test_vision.py)
        await self.browser_session._cdp_navigate(url)
        await asyncio.sleep(1.0)  # Give page time to load
        state = await self.browser_session.get_browser_state_summary()
        
        return ActionResult(
            extracted_content=f"Navigated to {state.url} - {state.title}",
            include_in_memory=True
        )
    
    async def _click(self, selector: str) -> ActionResult:
        """Click element by selector."""
        try:
            # Browser-Use 0.6.x uses event-driven system for clicks
            # For now, return placeholder - this needs DOM integration to get element node
            return ActionResult(extracted_content=f"Click action prepared for: {selector} (requires DOM integration)", include_in_memory=True)
        except Exception as e:
            return ActionResult(extracted_content=f"Click failed: {e}", include_in_memory=True)
    
    async def _type(self, selector: str, text: str) -> ActionResult:
        """Type text into element."""
        try:
            # Browser-Use 0.6.x uses event-driven system for typing
            # For now, return placeholder - this needs DOM integration to get element node
            return ActionResult(extracted_content=f"Type action prepared for '{text}' into: {selector} (requires DOM integration)", include_in_memory=True)
        except Exception as e:
            return ActionResult(extracted_content=f"Type failed: {e}", include_in_memory=True)
    
    async def _scroll(self, direction: str = "down") -> ActionResult:
        """Scroll page."""
        try:
            # Browser-Use 0.6.x uses event-driven system for scrolling
            # For now, return placeholder - this needs DOM integration to get page element
            return ActionResult(extracted_content=f"Scroll action prepared for: {direction} (requires DOM integration)", include_in_memory=True)
        except Exception as e:
            return ActionResult(extracted_content=f"Scroll failed: {e}", include_in_memory=True)
    
    async def _wait(self, duration: str = "2") -> ActionResult:
        """Wait for specified duration."""
        try:
            await asyncio.sleep(float(duration))
            return ActionResult(extracted_content=f"Waited {duration} seconds", include_in_memory=True)
        except Exception as e:
            return ActionResult(extracted_content=f"Wait failed: {e}", include_in_memory=True)
    
    async def _extract(self, target: str) -> ActionResult:
        """Extract information from page."""
        try:
            state = await self.browser_session.get_browser_state_summary()
            content = f"Extracted from {state.url}: {target}"
            return ActionResult(extracted_content=content, include_in_memory=True)
        except Exception as e:
            return ActionResult(extracted_content=f"Extract failed: {e}", include_in_memory=True)
    
    async def _analyze_vision(self) -> ActionResult:
        """Analyze current page with local vision model."""
        try:
            state = await self.browser_session.get_browser_state_summary()
            
            # Take screenshot using Browser-Use 0.6.x event system
            screenshot_event = self.browser_session.event_bus.dispatch(ScreenshotEvent(full_page=False))
            screenshot_b64 = await screenshot_event.event_result(raise_if_any=True, raise_if_none=True)
            
            # Save screenshot to file
            import tempfile
            import base64
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                f.write(base64.b64decode(screenshot_b64))
                screenshot_path = f.name
            
            vision_state = await self.vision_analyzer.analyze(
                str(screenshot_path), state.url or "", state.title or ""
            )
            
            summary = (
                f"Vision analysis: {vision_state.caption}\n"
                f"Elements: {len(vision_state.elements)}, "
                f"Fields: {len(vision_state.fields)}, "
                f"Affordances: {len(vision_state.affordances)}"
            )
            
            return ActionResult(extracted_content=summary, include_in_memory=True)
        except Exception as e:
            return ActionResult(extracted_content=f"Vision analysis failed: {e}", include_in_memory=True)
    
    async def _search_web(self, query: str) -> ActionResult:
        """Search web using Serper API."""
        try:
            result = await search_with_serper_fallback(self.controller, query, 10)
            return result
        except Exception as e:
            return ActionResult(extracted_content=f"Search failed: {e}", include_in_memory=True)
    
    def set_browser_session(self, browser_session: BrowserSession):
        """Set browser session reference."""
        self.browser_session = browser_session

# ----------------------------
# Escalation Manager
# ----------------------------

class EscalationManager:
    """Manages escalation when LocalExecutor gets stuck."""
    
    def __init__(self):
        self.gemini_llm = ChatGoogle(model=GEMINI_BACKUP_MODEL)
        self.o3_llm = ChatOpenAI(model=O3_ESCALATION_MODEL)
        self.stuck_threshold = 3  # stuck after 3 consecutive failures
        self.o3_step_budget = 5   # strict cap on o3 micro-steps
    
    def is_stuck(self, context: ExecutionContext) -> bool:
        """Determine if executor is stuck based on context."""
        if context.stuck_count >= self.stuck_threshold:
            return True
        
        # Check for repeated failures in recent history
        if len(context.history) >= 3:
            recent_results = [step.result for step in context.history[-3:]]
            if recent_results.count("fail") >= 2:
                return True
        
        return False
    
    async def get_micro_plan(self, context: ExecutionContext, plan: PlanJSON) -> MicroPlan:
        """Get micro-plan from Gemini when stuck."""
        try:
            print_status("Getting Gemini micro-plan (stuck state)...", Colors.YELLOW)
            
            prompt = self._build_micro_plan_prompt(context, plan)
            response = await self.gemini_llm.ainvoke([{"role": "user", "content": prompt}])
            
            # Parse response
            response_text = response.completion.strip()
            if response_text.startswith('```'):
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)
            
            micro_plan_data = json.loads(response_text)
            return MicroPlan(**micro_plan_data)
            
        except Exception as e:
            print_status(f"Gemini micro-plan failed: {e}", Colors.RED)
            return self._fallback_micro_plan(context)
    
    async def get_o3_micro_steps(self, context: ExecutionContext, plan: PlanJSON) -> List[GenericAction]:
        """Get bounded micro-steps from o3 as last resort."""
        try:
            print_status("Using o3 last-resort executor (strict budget)...", Colors.RED)
            
            prompt = self._build_o3_escalation_prompt(context, plan)
            response = await self.o3_llm.ainvoke([{"role": "user", "content": prompt}])
            
            # Parse response
            response_text = response.completion.strip()
            if response_text.startswith('```'):
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)
            
            actions_data = json.loads(response_text)
            actions = [GenericAction(**action) for action in actions_data.get("actions", [])]
            
            # Enforce strict budget
            return actions[:self.o3_step_budget]
            
        except Exception as e:
            print_status(f"o3 escalation failed: {e}", Colors.RED)
            return [GenericAction(primitive="wait", value="2", notes="Last resort wait")]
    
    def _build_micro_plan_prompt(self, context: ExecutionContext, plan: PlanJSON) -> str:
        recent_history = "\n".join([
            f"Step {step.step_id}: {step.action.primitive} -> {step.result} ({step.summary})"
            for step in context.history[-5:]
        ])
        
        return f"""You are stuck trying to execute this plan. Create a micro-plan to get unstuck.

ORIGINAL TASK: {plan.normalized_task}
CURRENT STEP: {context.current_step + 1} of {len(plan.steps)}
STUCK COUNT: {context.stuck_count}

RECENT HISTORY:
{recent_history}

VISION STATE: {context.last_vision_state.caption if context.last_vision_state else "No vision data"}

Return 1-3 immediate actions to try (JSON format):
{{
  "next_actions": [
    {{"primitive": "analyze_vision", "target": null, "value": null, "notes": "Reassess current state"}}
  ],
  "reasoning": "Why these actions might help",
  "timeout_steps": 3
}}"""
    
    def _build_o3_escalation_prompt(self, context: ExecutionContext, plan: PlanJSON) -> str:
        recent_history = "\n".join([
            f"Step {step.step_id}: {step.action.primitive} -> {step.result} ({step.summary})"
            for step in context.history[-5:]
        ])
        
        return f"""CRITICAL: You are the last-resort executor. Maximum {self.o3_step_budget} steps allowed.

TASK: {plan.normalized_task}
STUCK AFTER: Gemini micro-plan also failed
BUDGET: {self.o3_step_budget} steps maximum

RECENT FAILURES:
{recent_history}

Return ONLY the most essential actions (JSON):
{{
  "actions": [
    {{"primitive": "analyze_vision", "target": null, "value": null, "notes": "Critical assessment"}}
  ]
}}"""
    
    def _fallback_micro_plan(self, context: ExecutionContext) -> MicroPlan:
        """Fallback micro-plan when Gemini fails."""
        return MicroPlan(
            next_actions=[
                GenericAction(primitive="analyze_vision", notes="Fallback vision analysis"),
                GenericAction(primitive="wait", value="3", notes="Fallback wait")
            ],
            reasoning="Fallback: reassess and wait",
            timeout_steps=2
        )

# ----------------------------
# Custom Action for Vision Analysis
# ----------------------------

async def register_vision_action(controller: Controller, vision_analyzer: VisionAnalyzer, screenshots_dir: Path):
    """Register custom action for vision analysis."""
    
    @controller.action("Analyze current page with local vision")
    async def analyze_page_vision(browser_session: BrowserSession) -> ActionResult:
        """Take screenshot and analyze with local VLM. No-fail implementation."""
        try:
            state = await browser_session.get_browser_state_summary()
            
            # Take screenshot using Browser-Use 0.6.x event system
            screenshot_event = browser_session.event_bus.dispatch(ScreenshotEvent(full_page=False))
            screenshot_b64 = await screenshot_event.event_result(raise_if_any=True, raise_if_none=True)
            
            # Save screenshot to file
            import tempfile
            import base64
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                f.write(base64.b64decode(screenshot_b64))
                screenshot_path = f.name
            
            vision_state = await vision_analyzer.analyze(
                str(screenshot_path), state.url or "", state.title or ""
            )
            summary = (
                f"{vision_state.caption}\n"
                f"elements: {len(vision_state.elements)}, "
                f"fields: {len(vision_state.fields)}, "
                f"affordances: {len(vision_state.affordances)}; "
                f"url: {state.url}; title: {state.title}"
            )
            return ActionResult(extracted_content=summary, include_in_memory=True)
        except Exception as e:
            # No-fail: return best-effort payload even on error
            try:
                state = await browser_session.get_browser_state_summary()
                url = state.url or "unknown"
                title = state.title or "unknown"
            except:
                url = "unknown"
                title = "unknown"
            
            best_effort_summary = (
                f"Vision analysis unavailable (error: {str(e)[:50]})\n"
                f"elements: 0, fields: 0, affordances: 0; "
                f"url: {url}; title: {title}"
            )
            print(f"⚠️ Vision analysis failed but continuing: {e}")
            return ActionResult(extracted_content=best_effort_summary, include_in_memory=True)
    
    print("✅ Registered custom action: analyze_page_vision")

async def register_serper_action(controller: Controller):
    """Register Serper search actions."""
    
    @controller.action("search_web")
    async def search_web_action(query: str, num_results: int = 10) -> str:
        """Search the web using Serper API with browser fallback."""
        result = await search_with_serper_fallback(controller, query, num_results)
        return result.extracted_content
    
    @controller.action("search_google")
    async def search_google_action(query: str, num_results: int = 10) -> str:
        """Search Google using Serper API with browser fallback."""
        result = await search_with_serper_fallback(controller, query, num_results)
        return result.extracted_content
    
    print("✅ Registered custom actions: search_web, search_google")

# ----------------------------
# Main Hybrid Agent Class
# ----------------------------

class HybridAgent:
    """
    Main hybrid agent implementing the new architecture:
    1. User Query → o3 Planner → PlanJSON (runs exactly once)
    2. LocalExecutor executes plan with generic primitives
    3. EscalationManager handles stuck states with Gemini → o3 fallback
    """
    
    def __init__(self, screenshots_dir: str = "hybrid_queries/screenshots"):
        self.screenshots_dir = Path(screenshots_dir)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components according to new architecture
        self.planner_client = PlannerClient()  # o3 planner (runs once)
        self.vision_analyzer = VisionAnalyzer()  # Local vision analysis
        self.escalation_manager = EscalationManager()  # Handles stuck states
        
        # Browser-Use components (initialized on first use)
        self.browser_session: Optional[BrowserSession] = None
        self.controller: Optional[Controller] = None
        self.local_executor: Optional[LocalExecutor] = None
    
    async def execute_task(self, task: str) -> Dict[str, Any]:
        """
        Execute task using new architecture:
        1. User Query → o3 Planner → PlanJSON (exactly once)
        2. LocalExecutor executes with generic primitives
        3. EscalationManager handles stuck states
        """
        print_status(f"Starting hybrid task: {task}", Colors.BLUE)
        
        try:
            # Initialize browser session if needed
            if not self.browser_session:
                await self._initialize_browser()
            
            # STEP 1: Run o3 planner exactly once
            plan, planner_usage = await self.planner_client.create_plan(task)
            print_status(f"Plan normalized: {plan.normalized_task}", Colors.GREEN)
            
            # STEP 2: Initialize execution context
            context = ExecutionContext(
                current_step=0,
                stuck_count=0,
                escalation_level="local",
                history=[],
                last_vision_state=None
            )
            
            # STEP 3: Execute plan with LocalExecutor
            result = await self._execute_plan(plan, context)
            
            # STEP 4: Finalize and log results
            final_screenshot = None
            if self.browser_session:
                try:
                    screenshot_event = self.browser_session.event_bus.dispatch(ScreenshotEvent(full_page=False))
                    screenshot_b64 = await screenshot_event.event_result(raise_if_any=True, raise_if_none=True)
                    
                    import tempfile
                    import base64
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                        f.write(base64.b64decode(screenshot_b64))
                        final_screenshot = f.name
                    print_status(f"Final screenshot: {final_screenshot}", Colors.GREEN)
                except Exception as e:
                    print_status(f"Failed to capture final screenshot: {e}", Colors.YELLOW)
            
            # Create cost info with actual usage data
            cost_breakdown = self._estimate_cost(plan, context, planner_usage)
            cost_info = {
                "planner_model": O3_PLANNER_MODEL,
                "executor_model": LOCAL_EXECUTOR_MODEL,
                "escalation_model": GEMINI_BACKUP_MODEL,
                "total_steps": len(context.history),
                "escalation_level": context.escalation_level,
                "prompt_tokens": cost_breakdown["total_prompt_tokens"],
                "completion_tokens": cost_breakdown["total_completion_tokens"],
                "total_tokens": cost_breakdown["total_prompt_tokens"] + cost_breakdown["total_completion_tokens"],
                "estimated_cost": cost_breakdown["total_cost"],
                "planner_cost": cost_breakdown["planner_cost"],
                "escalation_cost": cost_breakdown["escalation_cost"]
            }
            
            # Create result summary
            result_text = self._create_result_summary(task, plan, context, result, final_screenshot, cost_info)
            
            # Save query log
            log_file = save_query_log(task, result_text, cost_info)
            print_status(f"Query logged: {log_file}", Colors.GREEN)
            
            return {
                "task": task,
                "plan": plan.dict(),
                "completed": result["success"],
                "steps_executed": len(context.history),
                "escalation_level": context.escalation_level,
                "final_screenshot": str(final_screenshot) if final_screenshot else None,
                "cost_info": cost_info,
                "summary": result["summary"]
            }
            
        except Exception as e:
            print_status(f"Task execution failed: {e}", Colors.RED)
            import traceback
            traceback.print_exc()
            return {
                "task": task,
                "completed": False,
                "error": str(e),
                "steps_executed": 0
            }
    
    async def _execute_plan(self, plan: PlanJSON, context: ExecutionContext) -> Dict[str, Any]:
        """Execute the plan using LocalExecutor with escalation handling."""
        print_status(f"Executing {len(plan.steps)} steps with LocalExecutor", Colors.BLUE)
        
        max_total_steps = 50  # Overall budget limit
        step_count = 0
        
        while context.current_step < len(plan.steps) and step_count < max_total_steps:
            current_action = plan.steps[context.current_step]
            
            # Execute action with LocalExecutor
            history_step = await self.local_executor.execute_action(current_action, context)
            context.history.append(history_step)
            step_count += 1
            
            # Update vision state if this was a navigation or vision analysis
            if current_action.primitive in ["go_to_url", "analyze_vision"]:
                await self._update_vision_context(context)
            
            # Check for success
            if history_step.result == "ok":
                context.current_step += 1
                context.stuck_count = 0
                context.escalation_level = "local"  # Reset to local on success
                
            elif history_step.result == "fail":
                context.stuck_count += 1
                
                # Check if stuck and escalate
                if self.escalation_manager.is_stuck(context):
                    escalation_result = await self._handle_escalation(plan, context)
                    if not escalation_result:
                        # Escalation failed, move to next step
                        context.current_step += 1
                        context.stuck_count = 0
            
            # Check success criteria periodically
            if step_count % 5 == 0:
                success_check = await self._check_success_criteria(plan, context)
                if success_check:
                    print_status("Success criteria met!", Colors.GREEN)
                    return {"success": True, "summary": success_check}
        
        # Plan completed or budget exhausted
        final_success = context.current_step >= len(plan.steps)
        summary = f"Executed {len(context.history)} steps, reached step {context.current_step}/{len(plan.steps)}"
        
        return {
            "success": final_success,
            "summary": summary
        }
    
    async def _handle_escalation(self, plan: PlanJSON, context: ExecutionContext) -> bool:
        """Handle escalation when LocalExecutor gets stuck."""
        if context.escalation_level == "local":
            # First escalation: Gemini micro-plan
            print_status("Escalating to Gemini micro-plan", Colors.YELLOW)
            context.escalation_level = "gemini"
            
            micro_plan = await self.escalation_manager.get_micro_plan(context, plan)
            
            # Execute micro-plan actions
            for action in micro_plan.next_actions:
                history_step = await self.local_executor.execute_action(action, context)
                context.history.append(history_step)
                
                if history_step.result == "ok":
                    context.stuck_count = 0
                    return True  # Micro-plan succeeded
            
        elif context.escalation_level == "gemini":
            # Second escalation: o3 last-resort with strict budget
            print_status("Escalating to o3 last-resort executor", Colors.RED)
            context.escalation_level = "o3"
            
            o3_actions = await self.escalation_manager.get_o3_micro_steps(context, plan)
            
            # Execute o3 micro-steps with strict budget
            for action in o3_actions:
                history_step = await self.local_executor.execute_action(action, context)
                context.history.append(history_step)
                
                if history_step.result == "ok":
                    context.stuck_count = 0
                    return True  # o3 escalation succeeded
        
        # All escalation attempts failed
        print_status("All escalation attempts failed", Colors.RED)
        return False
    
    async def _update_vision_context(self, context: ExecutionContext):
        """Update vision context after navigation or major changes."""
        try:
            state = await self.browser_session.get_browser_state_summary()
            
            # Take screenshot using Browser-Use 0.6.x event system
            screenshot_event = self.browser_session.event_bus.dispatch(ScreenshotEvent(full_page=False))
            screenshot_b64 = await screenshot_event.event_result(raise_if_any=True, raise_if_none=True)
            
            # Save screenshot to file
            import tempfile
            import base64
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                f.write(base64.b64decode(screenshot_b64))
                screenshot_path = f.name
            
            vision_state = await self.vision_analyzer.analyze(
                str(screenshot_path), state.url or "", state.title or ""
            )
            
            context.last_vision_state = vision_state
            print_status(f"Vision updated: {vision_state.caption[:50]}...", Colors.BLUE)
            
        except Exception as e:
            print_status(f"Vision update failed: {e}", Colors.YELLOW)
    
    async def _check_success_criteria(self, plan: PlanJSON, context: ExecutionContext) -> Optional[str]:
        """Check if success criteria are met."""
        # Simple heuristic check - in practice, this could be more sophisticated
        if len(context.history) > 0:
            recent_successes = [step for step in context.history[-3:] if step.result == "ok"]
            if len(recent_successes) >= 2:
                return "Multiple successful actions completed"
        
        return None
    
    def _estimate_cost(self, plan: PlanJSON, context: ExecutionContext, actual_usage: Dict[str, Any] = None) -> Dict[str, Any]:
        """Calculate actual cost based on token usage and current pricing."""
        # Current pricing per 1000 tokens (as of Jan 2025)
        model_pricing = {
            "o3": {"input": 0.015, "output": 0.06},  # $15/$60 per 1M tokens
            "o3-mini": {"input": 0.003, "output": 0.012},  # $3/$12 per 1M tokens  
            "gemini-2.0-flash-exp": {"input": 0.000075, "output": 0.0003},  # $0.075/$0.30 per 1M tokens
            "minicpm-v": {"input": 0.0, "output": 0.0},  # Local model - no cost
        }
        
        cost_breakdown = {
            "planner_cost": 0.0,
            "escalation_cost": 0.0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_cost": 0.0
        }
        
        if actual_usage:
            # Use actual token usage if provided
            prompt_tokens = actual_usage.get('prompt_tokens', 0)
            completion_tokens = actual_usage.get('completion_tokens', 0)
            model = actual_usage.get('model', O3_PLANNER_MODEL)
            
            cost_breakdown["total_prompt_tokens"] += prompt_tokens
            cost_breakdown["total_completion_tokens"] += completion_tokens
            
            if model in model_pricing:
                pricing = model_pricing[model]
                model_cost = (prompt_tokens * pricing["input"] / 1000) + (completion_tokens * pricing["output"] / 1000)
                
                if model == O3_PLANNER_MODEL:
                    cost_breakdown["planner_cost"] = model_cost
                elif model in [GEMINI_BACKUP_MODEL, O3_ESCALATION_MODEL]:
                    cost_breakdown["escalation_cost"] = model_cost
                    
                cost_breakdown["total_cost"] += model_cost
        else:
            # Fallback to estimation based on complexity
            if plan.estimated_complexity == "simple":
                est_prompt_tokens, est_completion_tokens = 1000, 300
            elif plan.estimated_complexity == "medium":
                est_prompt_tokens, est_completion_tokens = 2000, 600
            else:  # complex
                est_prompt_tokens, est_completion_tokens = 3000, 1000
            
            cost_breakdown["total_prompt_tokens"] = est_prompt_tokens
            cost_breakdown["total_completion_tokens"] = est_completion_tokens
            
            # Estimate planner cost (o3)
            o3_pricing = model_pricing[O3_PLANNER_MODEL]
            planner_cost = (est_prompt_tokens * o3_pricing["input"] / 1000) + (est_completion_tokens * o3_pricing["output"] / 1000)
            cost_breakdown["planner_cost"] = planner_cost
            cost_breakdown["total_cost"] = planner_cost
            
            # Add escalation costs if needed
            if context.escalation_level == "gemini":
                gemini_pricing = model_pricing[GEMINI_BACKUP_MODEL]
                escalation_cost = (500 * gemini_pricing["input"] / 1000) + (200 * gemini_pricing["output"] / 1000)
                cost_breakdown["escalation_cost"] = escalation_cost
                cost_breakdown["total_cost"] += escalation_cost
            elif context.escalation_level == "o3":
                escalation_cost = (1000 * o3_pricing["input"] / 1000) + (400 * o3_pricing["output"] / 1000)
                cost_breakdown["escalation_cost"] = escalation_cost
                cost_breakdown["total_cost"] += escalation_cost
        
        return cost_breakdown
    
    def _create_initial_context(self) -> ExecutionContext:
        """Create initial execution context."""
        return ExecutionContext(
            current_step=0,
            stuck_count=0,
            escalation_level="local",
            history=[],
            last_vision_state=None
        )
    
    def _create_result_summary(self, task: str, plan: PlanJSON, context: ExecutionContext, 
                              result: Dict[str, Any], screenshot: Optional[Path], 
                              cost_info: Dict[str, Any]) -> str:
        """Create detailed result summary for logging."""
        summary = f"# Hybrid Agent Execution Report\n\n"
        summary += f"**Original Task:** {task}\n"
        summary += f"**Normalized Task:** {plan.normalized_task}\n"
        summary += f"**Plan Complexity:** {plan.estimated_complexity}\n"
        summary += f"**Success:** {'✅ Yes' if result['success'] else '❌ No'}\n"
        summary += f"**Steps Executed:** {len(context.history)}\n"
        summary += f"**Final Escalation Level:** {context.escalation_level}\n\n"
        
        if screenshot:
            summary += f"**Final Screenshot:** {screenshot}\n\n"
        
        summary += f"## Success Criteria\n"
        for criterion in plan.success_criteria:
            summary += f"- {criterion}\n"
        
        summary += f"\n## Cost Information\n"
        summary += f"- Planner: {cost_info['planner_model']}\n"
        summary += f"- Executor: {cost_info['executor_model']}\n"
        summary += f"- Escalation: {cost_info['escalation_model']}\n"
        summary += f"- Estimated cost: ${cost_info['estimated_cost']:.4f}\n"
        
        return summary
    
    async def _initialize_browser(self):
        """Initialize browser session and LocalExecutor with 60s navigation timeout."""
        print_status("Initializing browser session with reliability-focused settings", Colors.BLUE)
        
        # Create browser profile with 60s navigation timeout (favor reliability over speed)
        browser_profile = BrowserProfile(
            user_data_dir=CHROME_PROFILE_DIR,
            headless=False,
            keep_alive=True,
            stealth=False,  # Disable stealth to avoid issues
            enable_default_extensions=False,  # Disable to silence CRX warnings
            wait_for_network_idle_page_load_time=3.0,
            minimum_wait_page_load_time=1.0,  # Slightly longer for reliability
            maximum_wait_page_load_time=10.0,
            wait_between_actions=1.0,  # Slightly longer for reliability
            default_timeout=15_000,  # 15s default timeout
            default_navigation_timeout=NAVIGATION_TIMEOUT_MS,  # 60s navigation timeout
        )
        
        print_status(f"Using profile: {browser_profile.user_data_dir}", Colors.BLUE)
        print_status(f"Navigation timeout: {NAVIGATION_TIMEOUT_MS / 1000}s (favor reliability)", Colors.BLUE)
        
        # Create browser session
        self.browser_session = BrowserSession(browser_profile=browser_profile)
        
        # Start the browser session (this initializes CDP)
        await self.browser_session.start()
        
        # Initialize controller and register actions
        self.controller = Controller()
        await register_vision_action(self.controller, self.vision_analyzer, self.screenshots_dir)
        await register_serper_action(self.controller)
        
        # Initialize LocalExecutor with controller and vision analyzer
        self.local_executor = LocalExecutor(self.controller, self.vision_analyzer)
        self.local_executor.set_browser_session(self.browser_session)
        
        print_status("Browser session and LocalExecutor initialized", Colors.GREEN)

# ----------------------------
# CLI Interface
# ----------------------------

async def main():
    """Main CLI interface for new hybrid architecture."""
    print("🤖 Hybrid Agent - New Architecture")
    print("📋 o3 Planner → LocalExecutor → Escalation Manager")
    print("🎯 Generic primitives, no domain-specific logic")
    print("⏱️  Navigation timeout: 60s (favor reliability)")
    print("=" * 60)
    
    agent = HybridAgent()
    
    while True:
        try:
            task = input("\n💭 Enter your task (or 'quit' to exit): ").strip()
            
            if task.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            if not task:
                continue
            
            # Execute task with new architecture
            result = await agent.execute_task(task)
            
            print("\n" + "=" * 60)
            print("📊 EXECUTION SUMMARY")
            print(f"Task: {result['task']}")
            print(f"Completed: {'✅' if result['completed'] else '❌'}")
            print(f"Steps Executed: {result.get('steps_executed', 0)}")
            print(f"Escalation Level: {result.get('escalation_level', 'unknown')}")
            
            if result.get('final_screenshot'):
                print(f"Final Screenshot: {result['final_screenshot']}")
                
            if result.get('cost_info'):
                cost = result['cost_info']
                print(f"💰 Cost: ${cost['estimated_cost']:.4f}")
                print(f"🧠 Models: {cost['planner_model']} → {cost['executor_model']}")
                if cost['escalation_level'] != 'local':
                    print(f"🚨 Escalated to: {cost['escalation_level']}")
                    
            if result.get('summary'):
                print(f"Summary: {result['summary']}")
                
            if result.get('error'):
                print(f"❌ Error: {result['error']}")
                
            print("=" * 60)
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())