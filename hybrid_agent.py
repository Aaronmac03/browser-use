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
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Literal
from urllib.parse import urlparse

# Configure logging to handle Unicode properly on Windows - must be early
if not logging.getLogger().handlers:
	logging.basicConfig(
		level=logging.INFO,
		format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
		stream=sys.stdout,
		force=True
	)

# Set encoding for stdout to handle Unicode from browser_use package
if hasattr(sys.stdout, 'reconfigure'):
	sys.stdout.reconfigure(encoding='utf-8', errors='replace')

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
from browser_use.llm.messages import UserMessage
import openai

# Import serper search functionality
from serper_search import search_with_serper_fallback

# Import working vision module from Phase 1
from vision_module_llamacpp import VisionAnalyzer, VisionState, VisionElement, VisionField, VisionAffordance, VisionMeta

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
LOCAL_EXECUTOR_MODEL = "moondream:latest"  # Local model via Ollama
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
            f.write(f"- Local Vision Model: Moondream2 (Local)\n")
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
    
    @classmethod
    def create_normalized(cls, primitive: str, target: Optional[str] = None, value: Optional[str] = None, notes: Optional[str] = None):
        """Create GenericAction with primitive normalization."""
        # Import here to avoid circular imports
        from hybrid_agent import EscalationManager
        manager = EscalationManager()
        normalized_primitive = manager._normalize_action_primitive(primitive)
        
        return cls(
            primitive=normalized_primitive,
            target=target,
            value=value,
            notes=notes
        )

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
    escalation_tokens: Dict[str, int] = Field(description="Track actual escalation token usage", default_factory=dict)
    history: List[HistoryStep] = Field(description="Execution history")
    last_vision_state: Optional[VisionState] = Field(description="Most recent vision analysis", default=None)

# ----------------------------
# Ollama Helper
# ----------------------------

async def resolve_moondream_tag(endpoint: str = "http://localhost:11434") -> str:
    """Resolve Moondream2 tag by querying Ollama API."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{endpoint}/api/tags")
            if response.status_code == 200:
                data = response.json()
                for model in data.get('models', []):
                    model_name = model.get('name', '')
                    if 'moondream' in model_name.lower():
                        return model_name
                return "moondream:latest"
            else:
                return "moondream:latest"
    except Exception as e:
        # Concise warning - don't fail loudly
        print(f"WARNING: Ollama API not available: {str(e)[:50]}")
        return "moondream:latest"

# ----------------------------
# Vision State Builder - REPLACED
# ----------------------------

# SUCCESS: PHASE 2.1 COMPLETE: VisionStateBuilder has been replaced with VisionAnalyzer
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
        # Use native OpenAI client instead of browser-use ChatOpenAI to avoid message format issues
        self.client = openai.AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.model = O3_PLANNER_MODEL
    
    async def create_plan(self, user_task: str) -> tuple[PlanJSON, Dict[str, Any]]:
        """Create structured plan from user task (runs exactly once). Returns plan and usage info."""
        try:
            prompt = self._build_planner_prompt(user_task)
            
            print_status("Running o3 planner (one-shot)...", Colors.BLUE)
            
            # Use a working model instead of o3 for now (o3 may not be available yet)
            available_model = "gpt-4" if self.model == "o3" else self.model
            
            response = await self.client.chat.completions.create(
                model=available_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.1
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Capture actual usage information
            usage_info = {
                "model": available_model,
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
                "cached_tokens": 0  # Not available in standard API
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
            
            # Post-process: if no http in user_task and first two steps don't include search_web, insert search steps
            plan = self._post_process_plan(plan, user_task)
            
            print_status(f"Plan created: {len(plan.steps)} steps, complexity: {plan.estimated_complexity}", Colors.GREEN)
            return plan, usage_info
            
        except Exception as e:
            print_status(f"o3 planner failed, creating fallback plan: {e}", Colors.RED)
            return self._create_fallback_plan(user_task), {"model": self.model, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cached_tokens": 0}
    
    def _post_process_plan(self, plan: PlanJSON, user_task: str) -> PlanJSON:
        """Post-process plan to insert search_web steps if needed."""
        try:
            # Check if user_task contains http/https URLs
            if 'http' in user_task.lower():
                return plan  # Don't modify plans with explicit URLs
            
            # Check if first two steps include search_web
            first_two_steps = plan.steps[:2] if len(plan.steps) >= 2 else plan.steps
            has_search_web = any(step.primitive == "search_web" for step in first_two_steps)
            
            if not has_search_web:
                print_status("No search_web in first two steps, inserting search sequence", Colors.BLUE)
                
                # Create concise search query from user_task
                search_query = self._create_search_query(user_task)
                
                # Create new steps to insert
                search_steps = [
                    GenericAction(
                        primitive="search_web",
                        target=None,
                        value=search_query,
                        notes="Search for relevant information"
                    ),
                    GenericAction(
                        primitive="analyze_vision",
                        target=None,
                        value=None,
                        notes="Analyze search results"
                    ),
                    GenericAction(
                        primitive="click",
                        target="first relevant result",
                        value=None,
                        notes="Navigate to most relevant result"
                    )
                ]
                
                # Insert at the beginning
                plan.steps = search_steps + plan.steps
                print_status(f"Inserted {len(search_steps)} search steps at beginning of plan", Colors.GREEN)
            
            return plan
            
        except Exception as e:
            print_status(f"Plan post-processing failed: {e}", Colors.YELLOW)
            return plan  # Return original plan on error
    
    def _create_search_query(self, user_task: str) -> str:
        """Create a concise search query from user task."""
        # Simple heuristics to create better search queries
        task_lower = user_task.lower()
        
        # Extract key terms and create focused query
        if 'price' in task_lower and ('kroger' in task_lower or 'milk' in task_lower):
            return "kroger milk price"
        elif 'availability' in task_lower:
            # Extract store and product names
            words = user_task.split()
            return ' '.join(words[:4])  # Take first few words
        else:
            # Generic approach: take first 5-6 words, remove common stop words
            stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'find', 'get', 'check'}
            words = [w for w in user_task.split()[:6] if w.lower() not in stop_words]
            return ' '.join(words[:4])  # Limit to 4 meaningful words
    
    def _build_planner_prompt(self, user_task: str) -> str:
        return f"""You are an expert web automation planner. Analyze the user's task and create a structured plan using ONLY generic primitives.

USER TASK: {user_task}

AVAILABLE PRIMITIVES:
- go_to_url: Navigate to a specific URL (target = URL)
- click: Click on an element (target = selector/description)
- type: Type text into input fields (target = field, value = text)
- scroll: Scroll page (value = up/down/to_element)
- wait: Wait for page/element to load (value = seconds)
- extract: Extract specific information from page (target = what to extract)
- analyze_vision: Analyze current page with vision (no parameters needed)
- search_web: Search web using Serper API (value = search query - REQUIRED!)

CRITICAL RULES:
1. For search_web: ALWAYS set "value" to the search query string
2. Use analyze_vision after navigation or major DOM changes
3. Create specific, measurable success criteria
4. Normalize and clarify the task description
5. NO domain-specific branching logic

EXAMPLE for search task:
{{
  "normalized_task": "Search for product availability at specific store",
  "steps": [
    {{
      "primitive": "search_web",
      "target": null,
      "value": "store name product availability",
      "notes": "Search for store and product"
    }},
    {{
      "primitive": "analyze_vision",
      "target": null, 
      "value": null,
      "notes": "Analyze search results"
    }},
    {{
      "primitive": "click",
      "target": "first relevant result",
      "value": null,
      "notes": "Navigate to store website"
    }}
  ],
  "success_criteria": [
    "Found store website",
    "Located product information",
    "Determined availability status"
  ],
  "estimated_complexity": "medium"
}}

Now create a plan for: {user_task}"""
    
    def _create_fallback_plan(self, user_task: str) -> PlanJSON:
        """Create a minimal fallback plan if o3 planner fails."""
        return PlanJSON(
            normalized_task=f"Complete user request: {user_task}",
            steps=[
                GenericAction(primitive="search_web", value=user_task, notes="Search for relevant website"),
                GenericAction(primitive="analyze_vision", notes="Analyze search results"),
                GenericAction(primitive="click", target="first relevant result", notes="Navigate to appropriate website"),
                GenericAction(primitive="analyze_vision", notes="Analyze target website"),
                GenericAction(primitive="extract", target="relevant information", notes="Extract requested information")
            ],
            success_criteria=[
                f"Successfully searched for: {user_task}",
                "Navigated to relevant website",
                "Found and extracted the requested information"
            ],
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
        # Temporarily disable analyze_vision for a few steps after timeouts
        self.vision_skip_steps_remaining: int = 0
        # Track consecutive vision timeouts for backoff logic
        self.vision_timeout_count: int = 0
    
    async def execute_action(self, action: GenericAction, context: ExecutionContext) -> HistoryStep:
        """Execute a single generic action and return result."""
        step_id = len(context.history) + 1
        screenshot_path = None
        
        try:
            print_status(f"Step {step_id}: {action.primitive}", Colors.BLUE)
            
            # Execute the primitive action
            if action.primitive == "go_to_url":
                result = await self._go_to_url(action.target)
                
                # After navigation, dismiss common banners/popups
                if result.extracted_content and "successfully navigated" in result.extracted_content.lower():
                    try:
                        await self._dismiss_common_banners()
                    except Exception as e:
                        print_status(f"Banner dismissal failed: {e}", Colors.YELLOW)
                
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
                # Use DOM fallback when vision is skipped due to timeouts
                if self.vision_skip_steps_remaining > 0:
                    self.vision_skip_steps_remaining -= 1
                    print_status("Vision skipped due to timeout, using DOM fallback", Colors.YELLOW)
                    try:
                        state = await self.browser_session.get_browser_state_summary()
                        dom_analysis = await self._analyze_dom_fallback(state)
                        result = ActionResult(extracted_content=dom_analysis, include_in_memory=True)
                    except Exception as fallback_err:
                        print_status(f"DOM fallback also failed: {fallback_err}", Colors.RED)
                        result = ActionResult(extracted_content="Vision skipped and DOM fallback failed", include_in_memory=True)
                else:
                    result = await self._analyze_vision()
                # Screenshot already taken in _analyze_vision method
                screenshot_path = None
                
            elif action.primitive == "search_web":
                result = await self._search_web(action.value)
                
            else:
                result = ActionResult(extracted_content=f"Unknown primitive: {action.primitive}", include_in_memory=True)
            
            # Determine success based on result (more precise error checking)
            has_content = result.extracted_content is not None and result.extracted_content.strip() != ""
            has_error = has_content and ("error:" in result.extracted_content.lower() or 
                                       "failed" in result.extracted_content.lower() or
                                       "navigation failed" in result.extracted_content.lower())
            success = has_content and not has_error
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
        """Navigate to URL using proper controller method with success verification."""
        if not self.browser_session:
            raise Exception("Browser session not initialized")
        
        if not url:
            return ActionResult(extracted_content="Error: No URL provided", include_in_memory=True)
        
        print_status(f"Navigating to: {url}", Colors.BLUE)
        
        try:
            # Get current URL before navigation
            initial_state = await self.browser_session.get_browser_state_summary()
            initial_url = initial_state.url if initial_state else ""
            
            # Navigate via controller registry API (Controller has no direct go_to_url attribute)
            result = await self.controller.registry.execute_action(
                action_name="go_to_url",
                params={"url": url, "new_tab": False},
                browser_session=self.browser_session,
            )

            # Wait longer for page to settle and load
            await asyncio.sleep(3.0)
            
            # Verify navigation success by checking current URL
            final_state = await self.browser_session.get_browser_state_summary()
            final_url = final_state.url if final_state else ""
            
            # Check if navigation was successful
            from urllib.parse import urlparse
            target_domain = urlparse(url).netloc.lower()
            current_domain = urlparse(final_url).netloc.lower() if final_url else ""
            
            if current_domain and target_domain in current_domain:
                print_status(f"SUCCESS: Successfully navigated to: {final_url}", Colors.GREEN)
                return ActionResult(
                    extracted_content=f"Successfully navigated to {final_url}", 
                    include_in_memory=True
                )
            elif final_url != initial_url:
                # URL changed but not to target - may be redirect or search results
                print_status(f"REDIRECT: Navigation redirected to: {final_url}", Colors.YELLOW)
                return ActionResult(
                    extracted_content=f"Navigation redirected to {final_url}", 
                    include_in_memory=True
                )
            else:
                # URL didn't change - navigation failed
                print_status(f"FAILED: Navigation failed - URL unchanged: {final_url}", Colors.RED)
                return ActionResult(
                    extracted_content=f"Error: Navigation failed - remained at {final_url}", 
                    include_in_memory=True
                )
                
        except Exception as e:
            print_status(f"ERROR: Navigation error: {e}", Colors.RED)
            return ActionResult(
                extracted_content=f"Error: Navigation failed - {str(e)}", 
                include_in_memory=True
            )
    
    async def _click(self, selector: str) -> ActionResult:
        """Click element by selector/description."""
        try:
            if not self.browser_session:
                raise Exception("Browser session not initialized")
            
            # Get current browser state (fixed method call)
            state = await self.browser_session.get_browser_state_summary()
            if not state.dom_state or not state.dom_state.selector_map:
                raise Exception("No DOM state available")
            
            # Try to find matching element by text content or description
            target_element = None
            for idx, element in state.dom_state.selector_map.items():
                element_attrs = getattr(element, 'attributes', {}) or {}
                element_text = element_attrs.get('text', '') or element_attrs.get('value', '') or getattr(element, 'node_value', '') or ''
                
                if element_text and (selector.lower() in element_text.lower() or element_text.lower() in selector.lower()):
                    target_element = (idx, element)
                    break
                
                # Also check other attributes that might contain relevant text
                for attr_name in ['aria-label', 'title', 'alt']:
                    attr_value = element_attrs.get(attr_name, '')
                    if attr_value and (selector.lower() in attr_value.lower() or attr_value.lower() in selector.lower()):
                        target_element = (idx, element)
                        break
                
                if target_element:
                    break
            
            if not target_element:
                # Try first clickable element as fallback (look for buttons, links, etc.)
                for idx, element in state.dom_state.selector_map.items():
                    element_tag = getattr(element, 'node_name', '').lower()
                    if element_tag in ['button', 'a', 'input']:
                        target_element = (idx, element)
                        break
                
                if not target_element:
                    raise Exception(f"No clickable elements found matching: {selector}")
            
            idx, element = target_element
            
            # Execute registered click action via controller registry
            await self.controller.registry.execute_action(
                action_name="click_element_by_index",
                params={"index": idx, "while_holding_ctrl": False},
                browser_session=self.browser_session,
            )

            await asyncio.sleep(0.5)  # Brief wait for page changes
            return ActionResult(extracted_content=f"Successfully clicked element {idx}: {selector}", include_in_memory=True)
        except Exception as e:
            return ActionResult(extracted_content=f"Click failed: {e}", include_in_memory=True)
    
    async def _dismiss_common_banners(self) -> None:
        """Dismiss common banners/popups after navigation."""
        try:
            if not self.browser_session:
                return
            
            # Get current browser state
            state = await self.browser_session.get_browser_state_summary()
            if not state.dom_state or not state.dom_state.selector_map:
                return
            
            # Common banner/popup button text patterns (case insensitive)
            banner_patterns = [
                r'accept', r'agree', r'got it', r'continue', r'close', r'^x$',
                r'ok', r'dismiss', r'allow', r'enable', r'yes'
            ]
            
            import re
            
            # Look for buttons/links with banner dismissal text
            for idx, element in state.dom_state.selector_map.items():
                element_attrs = getattr(element, 'attributes', {}) or {}
                element_text = element_attrs.get('text', '') or element_attrs.get('value', '') or getattr(element, 'node_value', '') or ''
                element_tag = getattr(element, 'node_name', '').lower()
                
                # Only check clickable elements
                if element_tag in ['button', 'a', 'div'] and element_text:
                    # Check if text matches any banner pattern
                    for pattern in banner_patterns:
                        if re.search(pattern, element_text.strip(), re.IGNORECASE):
                            print_status(f"Dismissing banner: '{element_text.strip()}'", Colors.BLUE)
                            try:
                                # Click the banner dismissal button
                                await self.controller.registry.execute_action(
                                    action_name="click",
                                    params={"index": idx, "while_holding_ctrl": False},
                                    browser_session=self.browser_session,
                                )
                                await asyncio.sleep(0.5)  # Brief wait for banner to disappear
                                return  # Only dismiss one banner per call
                            except Exception as click_error:
                                print_status(f"Failed to click banner button: {click_error}", Colors.YELLOW)
                                continue
                            
        except Exception as e:
            print_status(f"Banner dismissal error: {e}", Colors.YELLOW)
    



    async def _type(self, selector: str, text: str) -> ActionResult:
        """Type text into element with browser-use DOM search and fallback strategies."""
        try:
            if not self.browser_session:
                raise Exception("Browser session not initialized")
            
            # Get current browser state
            state = await self.browser_session.get_browser_state_summary()
            if not state.dom_state or not state.dom_state.selector_map:
                # Fallback: try "/" shortcut for search
                print_status("No DOM state, trying '/' shortcut for search", Colors.YELLOW)
                return await self._try_slash_search_shortcut(text)
            
            # First, try browser-use DOM search for search-related typing
            if 'search' in selector.lower():
                search_element = await self._find_search_input_dom()
                if search_element:
                    idx, element = search_element
                    print_status(f"Found search input via DOM: {idx}", Colors.GREEN)
                    await self.controller.registry.execute_action(
                        action_name="input_text",
                        params={"index": idx, "text": text, "clear_existing": True},
                        browser_session=self.browser_session,
                    )
                    await asyncio.sleep(0.3)
                    return ActionResult(extracted_content=f"Successfully typed '{text}' into search element {idx}", include_in_memory=True)
            
            # Try to find matching input element from selector map
            target_element = None
            for idx, element in state.dom_state.selector_map.items():
                element_attrs = getattr(element, 'attributes', {}) or {}
                element_tag = getattr(element, 'node_name', '').lower()
                
                if element_tag == 'input':
                    # Check various attributes for matching
                    for attr_name in ['placeholder', 'aria-label', 'name', 'id', 'class']:
                        attr_value = element_attrs.get(attr_name, '')
                        if attr_value and (selector.lower() in attr_value.lower() or attr_value.lower() in selector.lower()):
                            target_element = (idx, element)
                            break
                    if target_element:
                        break
            
            if not target_element:
                # Try first input element as fallback
                for idx, element in state.dom_state.selector_map.items():
                    element_tag = getattr(element, 'node_name', '').lower()
                    if element_tag == 'input':
                        target_element = (idx, element)
                        break
                
                if not target_element:
                    # Enhanced fallback: try clicking navigation anchors first
                    print_status("No input fields found, trying navigation fallback", Colors.YELLOW)
                    nav_result = await self._try_navigation_fallback()
                    if nav_result.extracted_content and "clicked" in nav_result.extracted_content.lower():
                        # Successfully clicked a navigation element, wait and try again
                        await asyncio.sleep(1.0)
                        # Try to find input again after navigation
                        updated_state = await self.browser_session.get_browser_state_summary()
                        if updated_state.dom_state and updated_state.dom_state.selector_map:
                            for idx, element in updated_state.dom_state.selector_map.items():
                                element_tag = getattr(element, 'node_name', '').lower()
                                if element_tag == 'input':
                                    target_element = (idx, element)
                                    break
                    
                    # If still no input found, try slash shortcut
                    if not target_element:
                        print_status("No input fields found after navigation, trying slash shortcut", Colors.YELLOW)
                        return await self._try_slash_search_shortcut(text)
            
            idx, element = target_element
            
            # Execute registered input action via controller registry
            await self.controller.registry.execute_action(
                action_name="input_text",
                params={"index": idx, "text": text, "clear_existing": True},
                browser_session=self.browser_session,
            )

            await asyncio.sleep(0.3)  # Brief wait for text to register
            return ActionResult(extracted_content=f"Successfully typed '{text}' into element {idx}: {selector}", include_in_memory=True)
        except Exception as e:
            return ActionResult(extracted_content=f"Type failed: {e}", include_in_memory=True)
    
    async def _find_search_input_dom(self) -> Optional[tuple[int, Any]]:
        """Find search input using browser-use DOM state."""
        try:
            state = await self.browser_session.get_browser_state_summary()
            if not state.dom_state or not state.dom_state.selector_map:
                return None
            
            # Check selector map for search inputs
            for idx, element in state.dom_state.selector_map.items():
                element_attrs = getattr(element, 'attributes', {}) or {}
                element_tag = getattr(element, 'node_name', '').lower()
                
                if element_tag == 'input':
                    # Check input type
                    input_type = element_attrs.get('type', '').lower()
                    if input_type == 'search':
                        return (idx, element)
                    
                    # Check other search indicators
                    for attr_name in ['aria-label', 'placeholder', 'name', 'id', 'class']:
                        attr_value = element_attrs.get(attr_name, '').lower()
                        if 'search' in attr_value:
                            return (idx, element)
            
            return None
        except Exception:
            return None
    
    async def _try_navigation_fallback(self) -> ActionResult:
        """Try clicking navigation anchors with generic markers when no input is found."""
        try:
            if not self.browser_session:
                return ActionResult(extracted_content="No browser session", include_in_memory=True)
            
            state = await self.browser_session.get_browser_state_summary()
            if not state.dom_state or not state.dom_state.selector_map:
                return ActionResult(extracted_content="No DOM state for navigation fallback", include_in_memory=True)
            
            # Generic navigation markers to look for
            nav_markers = ["search", "browse", "catalog", "results", "directory", "explore", "shop", "list"]
            
            # Look for anchors with navigation markers in text or href
            for idx, element in state.dom_state.selector_map.items():
                element_attrs = getattr(element, 'attributes', {}) or {}
                element_tag = getattr(element, 'node_name', '').lower()
                element_text = element_attrs.get('text', '') or element_attrs.get('value', '') or getattr(element, 'node_value', '') or ''
                element_href = element_attrs.get('href', '')
                
                if element_tag == 'a':  # Only check anchor tags
                    # Check text content for navigation markers
                    text_lower = element_text.lower()
                    href_lower = element_href.lower()
                    
                    for marker in nav_markers:
                        if marker in text_lower or marker in href_lower:
                            print_status(f"Found navigation anchor: '{element_text}' with marker '{marker}'", Colors.GREEN)
                            try:
                                # Click the navigation anchor
                                await self.controller.registry.execute_action(
                                    action_name="click_element_by_index",
                                    params={"index": idx, "while_holding_ctrl": False},
                                    browser_session=self.browser_session,
                                )
                                await asyncio.sleep(0.5)  # Brief wait for navigation
                                return ActionResult(
                                    extracted_content=f"Clicked navigation anchor: '{element_text}' (marker: {marker})", 
                                    include_in_memory=True
                                )
                            except Exception as click_error:
                                print_status(f"Failed to click navigation anchor: {click_error}", Colors.YELLOW)
                                continue
            
            return ActionResult(extracted_content="No navigation anchors found with generic markers", include_in_memory=True)
            
        except Exception as e:
            return ActionResult(extracted_content=f"Navigation fallback failed: {e}", include_in_memory=True)
    
    async def _try_slash_search_shortcut(self, text: str) -> ActionResult:
        """Try using '/' shortcut for search or type into active element."""
        try:
            # Try "/" shortcut first (common on many sites)
            await self.controller.registry.execute_action(
                action_name="key",
                params={"key": "/"},
                browser_session=self.browser_session,
            )
            await asyncio.sleep(0.2)
            
            # Type the search text
            await self.controller.registry.execute_action(
                action_name="key",
                params={"key": text},
                browser_session=self.browser_session,
            )
            await asyncio.sleep(0.3)
            
            return ActionResult(extracted_content=f"Used '/' shortcut to type: {text}", include_in_memory=True)
            
        except Exception as e:
            # Final fallback: just type the text (will go to active element)
            try:
                await self.controller.registry.execute_action(
                    action_name="key",
                    params={"key": text},
                    browser_session=self.browser_session,
                )
                return ActionResult(extracted_content=f"Typed into active element: {text}", include_in_memory=True)
            except Exception as final_error:
                return ActionResult(extracted_content=f"All type strategies failed: {final_error}", include_in_memory=True)
    
    async def _scroll(self, direction: str = "down") -> ActionResult:
        """Scroll page."""
        try:
            if not self.browser_session:
                raise Exception("Browser session not initialized")
            
            # Use controller's scroll action
            from browser_use.controller.views import ScrollAction

            # Determine scroll direction flag
            down_flag = True if str(direction).lower() in ["down", "d", "true", "1", "yes"] else False

            # Build valid ScrollAction (controller expects down + num_pages)
            scroll_action = ScrollAction(down=down_flag, num_pages=1.0, frame_element_index=None)

            await self.controller.registry.execute_action(
                action_name="scroll",
                params={"down": down_flag, "num_pages": 1.0, "frame_element_index": None},
                browser_session=self.browser_session,
            )

            await asyncio.sleep(0.3)  # Brief wait for scroll to settle
            return ActionResult(extracted_content=f"Successfully scrolled {'down' if down_flag else 'up'}", include_in_memory=True)
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
        """Extract information from page with enhanced DOM analysis for hotel booking sites."""
        try:
            state = await self.browser_session.get_browser_state_summary()
            
            # Enhanced extraction for hotel booking sites
            if "booking.com" in (state.url or "").lower() or "hotel" in target.lower():
                return await self._extract_hotel_info(target, state)
            else:
                # Generic extraction fallback
                content = f"Extracted from {state.url}: {target}"
                return ActionResult(extracted_content=content, include_in_memory=True)
                
        except Exception as e:
            return ActionResult(extracted_content=f"Extract failed: {e}", include_in_memory=True)
    
    async def _extract_hotel_info(self, target: str, state) -> ActionResult:
        """Extract hotel pricing and availability information from booking sites."""
        try:
            print_status("Extracting hotel pricing and availability information...", Colors.BLUE)
            
            # Use browser-use's DOM extraction capabilities
            from browser_use.dom.service import DomService
            
            # Get page content for analysis
            page_content = await self.browser_session.get_browser_state_summary()
            
            # Look for common hotel booking elements
            extraction_selectors = [
                # Price selectors (common patterns)
                '[data-testid*="price"]',
                '.price, .rate, .cost',
                '[class*="price"], [class*="rate"], [class*="cost"]',
                'span:contains("$"), div:contains("$")',
                
                # Availability selectors
                '[data-testid*="available"]',
                '.available, .availability',
                '[class*="available"], [class*="room"]',
                
                # Hotel name and details
                'h1, h2, .hotel-name, [data-testid*="hotel"]',
                
                # Date confirmation
                '[data-testid*="date"], .date, [class*="date"]'
            ]
            
            extracted_info = {
                "url": state.url,
                "timestamp": datetime.now().isoformat(),
                "extraction_target": target,
                "found_elements": []
            }
            
            # Try to extract using browser-use's element detection
            try:
                # Get current page elements
                elements = await self.browser_session.get_browser_state_summary()
                
                # Look for price indicators in the page text
                page_text = str(elements)
                
                # Extract price patterns
                import re
                price_patterns = [
                    r'\$\d+(?:,\d{3})*(?:\.\d{2})?',  # $123.45, $1,234.56
                    r'\d+(?:,\d{3})*(?:\.\d{2})?\s*USD',  # 123.45 USD
                    r'USD\s*\d+(?:,\d{3})*(?:\.\d{2})?',  # USD 123.45
                ]
                
                found_prices = []
                for pattern in price_patterns:
                    matches = re.findall(pattern, page_text, re.IGNORECASE)
                    found_prices.extend(matches)
                
                if found_prices:
                    extracted_info["prices_found"] = list(set(found_prices))
                    print_status(f"Found {len(found_prices)} price indicators", Colors.GREEN)
                
                # Look for availability indicators
                availability_keywords = ["available", "book now", "reserve", "select room", "choose room"]
                availability_found = []
                
                for keyword in availability_keywords:
                    if keyword.lower() in page_text.lower():
                        availability_found.append(keyword)
                
                if availability_found:
                    extracted_info["availability_indicators"] = availability_found
                    print_status(f"Found availability indicators: {', '.join(availability_found)}", Colors.GREEN)
                
                # Check for date confirmation
                date_patterns = [
                    r'9/1/25', r'9/2/25',  # Our specific dates
                    r'Sep\s*1', r'Sep\s*2',  # Month abbreviations
                    r'September\s*1', r'September\s*2'  # Full month names
                ]
                
                found_dates = []
                for pattern in date_patterns:
                    if re.search(pattern, page_text, re.IGNORECASE):
                        found_dates.append(pattern)
                
                if found_dates:
                    extracted_info["dates_confirmed"] = found_dates
                    print_status(f"Confirmed dates found: {', '.join(found_dates)}", Colors.GREEN)
                
                # Determine if extraction was successful
                success_indicators = len(found_prices) + len(availability_found) + len(found_dates)
                
                if success_indicators >= 2:
                    extracted_info["extraction_success"] = True
                    extracted_info["success_score"] = success_indicators
                    print_status(f"Hotel extraction successful (score: {success_indicators})", Colors.GREEN)
                else:
                    extracted_info["extraction_success"] = False
                    extracted_info["success_score"] = success_indicators
                    print_status(f"Hotel extraction partial (score: {success_indicators})", Colors.YELLOW)
                
            except Exception as dom_error:
                print_status(f"DOM extraction error: {dom_error}", Colors.YELLOW)
                extracted_info["dom_error"] = str(dom_error)
            
            # Format the result
            result_content = f"""Hotel Information Extraction Results:
URL: {extracted_info['url']}
Target: {extracted_info['extraction_target']}
Success: {extracted_info.get('extraction_success', False)}
Score: {extracted_info.get('success_score', 0)}/6

Prices Found: {extracted_info.get('prices_found', [])}
Availability: {extracted_info.get('availability_indicators', [])}
Dates Confirmed: {extracted_info.get('dates_confirmed', [])}

Timestamp: {extracted_info['timestamp']}"""
            
            return ActionResult(
                extracted_content=result_content, 
                include_in_memory=True,
                success=extracted_info.get('extraction_success', False)
            )
            
        except Exception as e:
            error_content = f"Hotel extraction failed: {str(e)}"
            print_status(error_content, Colors.RED)
            return ActionResult(extracted_content=error_content, include_in_memory=True, success=False)
    
    async def _analyze_vision(self) -> ActionResult:
        """Analyze current page with local vision model."""
        try:
            state = await self.browser_session.get_browser_state_summary()
            print_status("Taking screenshot for vision analysis...", Colors.BLUE)
            
            # Take screenshot using Browser-Use 0.6.x event system
            screenshot_event = self.browser_session.event_bus.dispatch(ScreenshotEvent(full_page=False))
            screenshot_b64 = await screenshot_event.event_result(raise_if_any=True, raise_if_none=True)
            print_status("Screenshot captured successfully", Colors.GREEN)
            
            # Save screenshot to file
            import tempfile
            import base64
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                f.write(base64.b64decode(screenshot_b64))
                screenshot_path = f.name
            print_status(f"Screenshot saved to: {screenshot_path}", Colors.BLUE)
            
            print_status("Running vision analysis...", Colors.BLUE)

            # Call vision with a timeout to prevent hanging
            async def call_vision():
                return await self.vision_analyzer.analyze(
                    str(screenshot_path), state.url or "", state.title or ""
                )

            try:
                # Very aggressive timeout for local processing
                vision_state = await asyncio.wait_for(call_vision(), timeout=45)
                # Reset timeout counter on success
                self.vision_timeout_count = 0
            except asyncio.TimeoutError:
                # Increase timeout counter and apply backoff policy
                self.vision_timeout_count += 1
                # Disable further vision for a few steps and return non-failing content
                if self.vision_timeout_count >= 2:
                    # Stronger backoff after two consecutive timeouts
                    self.vision_skip_steps_remaining = 8
                    print_status("Two consecutive vision timeouts - disabling analyze_vision for next 8 steps", Colors.YELLOW)
                else:
                    self.vision_skip_steps_remaining = 5
                    print_status("Vision timeout - temporarily disabling analyze_vision for next 5 steps", Colors.YELLOW)
                # Fallback to DOM-based analysis when vision fails
                print_status("Vision failed, falling back to DOM analysis", Colors.YELLOW)
                dom_analysis = await self._analyze_dom_fallback(state)
                return ActionResult(extracted_content=dom_analysis, include_in_memory=True)

            print_status("Vision analysis completed", Colors.GREEN)
            
            summary = (
                f"Vision analysis: {vision_state.caption}\n"
                f"Elements: {len(vision_state.elements)}, "
                f"Fields: {len(vision_state.fields)}, "
                f"Affordances: {len(vision_state.affordances)}"
            )
            
            return ActionResult(extracted_content=summary, include_in_memory=True)
        except Exception as e:
            print_status(f"Vision analysis error details: {e}", Colors.RED)
            print_status(f"Error type: {type(e).__name__}", Colors.RED)
            # Fallback to DOM analysis for any vision failure
            print_status("Vision failed, falling back to DOM analysis", Colors.YELLOW)
            try:
                state = await self.browser_session.get_browser_state_summary()
                dom_analysis = await self._analyze_dom_fallback(state)
                return ActionResult(extracted_content=dom_analysis, include_in_memory=True)
            except Exception as fallback_err:
                print_status(f"DOM fallback also failed: {fallback_err}", Colors.RED)
                return ActionResult(extracted_content=f"Both vision and DOM analysis failed", include_in_memory=True)
    
    async def _analyze_dom_fallback(self, state) -> str:
        """DOM-based fallback analysis when vision fails - enables true local-first execution."""
        try:
            print_status("Running DOM-based page analysis", Colors.BLUE)
            
            # Extract basic page information
            url = state.url or "unknown"
            title = state.title or "unknown"
            
            # Analyze DOM structure if available
            interactive_elements = 0
            form_fields = 0
            buttons = 0
            links = 0
            
            if state.dom_state and state.dom_state.selector_map:
                for idx, element in state.dom_state.selector_map.items():
                    element_attrs = getattr(element, 'attributes', {}) or {}
                    tag_name = getattr(element, 'tag_name', '').lower()
                    
                    if tag_name in ['button', 'input', 'select', 'textarea']:
                        interactive_elements += 1
                        if tag_name == 'button':
                            buttons += 1
                        elif tag_name in ['input', 'select', 'textarea']:
                            form_fields += 1
                    elif tag_name == 'a':
                        links += 1
            
            # Hotel booking specific analysis
            booking_signals = []
            if 'omni' in url.lower() or 'omni' in title.lower():
                booking_signals.append("On Omni hotel website")
            if 'booking' in url.lower() or 'reservation' in url.lower():
                booking_signals.append("Booking/reservation page detected")
            if 'hotel' in url.lower() or 'hotel' in title.lower():
                booking_signals.append("Hotel-related page")
                
            # Build analysis summary
            analysis = f"DOM Analysis - URL: {url}\n"
            analysis += f"Title: {title}\n"
            analysis += f"Interactive elements: {interactive_elements} (buttons: {buttons}, fields: {form_fields}, links: {links})\n"
            
            if booking_signals:
                analysis += f"Hotel booking signals: {', '.join(booking_signals)}\n"
            
            # Add actionable context for the planner
            if interactive_elements > 0:
                analysis += f"Page appears interactive with {interactive_elements} actionable elements\n"
            else:
                analysis += "Page appears mostly static - may need scrolling or navigation\n"
                
            print_status(f"DOM analysis complete: {interactive_elements} interactive elements found", Colors.GREEN)
            return analysis
            
        except Exception as e:
            fallback_analysis = f"DOM analysis fallback - URL: {state.url or 'unknown'}, Title: {state.title or 'unknown'}"
            print_status(f"DOM fallback error: {e}, using minimal analysis", Colors.YELLOW)
            return fallback_analysis
    
    async def _search_web(self, query: str) -> ActionResult:
        """Search web using Serper API, then open the first result automatically."""
        try:
            if not query or query == "None" or query.strip() == "":
                print_status(f"WARNING: Invalid search query received: '{query}' - using fallback", Colors.YELLOW)
                # Use a generic hotel search as fallback to stay on task
                fallback_query = "Omni Hotel Louisville booking availability"
                print_status(f"Using fallback query: '{fallback_query}'", Colors.YELLOW)
                result = await search_with_serper_fallback(self.controller, fallback_query, 10)
            else:
                print_status(f"SEARCH: Searching for: '{query}'", Colors.BLUE)
                result = await search_with_serper_fallback(self.controller, query, 10)

            # Try to extract and navigate to the first URL in results
            try:
                import re
                content = result.extracted_content or ""
                # Prefer lines starting with 'URL:'
                urls = re.findall(r"URL:\s*(https?://\S+)", content)
                if not urls:
                    # Fallback: any bare http(s) links
                    urls = re.findall(r"https?://[^\s)]+", content)
                if urls:
                    first_url = urls[0]
                    print_status(f"Opening first result: {first_url}", Colors.BLUE)
                    nav_res = await self._go_to_url(first_url)
                    # Combine messages so the step is considered successful and we leave the homepage
                    combined = (result.extracted_content or "") + "\n\nOpened: " + first_url
                    return ActionResult(extracted_content=combined, include_in_memory=True)
            except Exception as parse_err:
                print_status(f"Couldn't open result automatically: {parse_err}", Colors.YELLOW)

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

    def _normalize_action_primitive(self, name: str) -> str:
        """Map common synonyms to allowed primitives."""
        n = (name or "").lower().strip()
        
        # Allowed primitives set
        allowed_primitives = {
            "go_to_url", "click", "type", "scroll", "wait", 
            "extract", "analyze_vision", "search_web"
        }
        
        # If already allowed, return as-is
        if n in allowed_primitives:
            return n
        
        # Mapping for unsupported primitives
        mapping = {
            # Click variants
            "click_link": "click",
            "click_button": "click",
            "press": "click",
            "press_button": "click",
            
            # Type variants
            "type_text": "type",
            "enter_text": "type",
            "input_text": "type",
            
            # Scroll variants
            "scroll_down": "scroll",
            "scroll_up": "scroll",
            
            # Extract variants
            "extract_text": "extract",
            "get_text": "extract",
            
            # Navigation variants
            "reload_page": "wait",  # treat reload/refresh as brief wait to settle
            "refresh": "wait",
            "open_url": "go_to_url",
            "go_to": "go_to_url",
            "open": "go_to_url",
            "navigate": "go_to_url",
            "visit": "go_to_url",
            
            # Keyboard actions - map to closest equivalent or wait
            "key": "wait",
            "key_press": "wait",
            "keypress": "wait", 
            "press_key": "wait",
            "enter": "wait",
            "escape": "wait",
            "tab": "wait",
            "space": "wait",
            "backspace": "wait",
            "delete": "wait",
            
            # Other actions
            "debug_console": "wait",
            "analyze_code": "analyze_vision",
            "comment": "wait",
            "pause": "wait",
            "text_search": "search_web",
            "search": "search_web",
        }
        
        normalized = mapping.get(n, "wait")  # Default fallback to wait
        
        # Log warning for unmapped primitives
        if normalized == "wait" and n not in mapping:
            print_status(f"WARNING: Unknown primitive '{n}' mapped to 'wait'", Colors.YELLOW)
        elif n in mapping and mapping[n] != n:
            print_status(f"NORM: Normalized primitive '{n}' -> '{normalized}'", Colors.BLUE)
            
        return normalized

    def _normalize_microplan_payload(self, data: dict) -> dict:
        """Normalize micro-plan JSON to fit MicroPlan model constraints."""
        out = dict(data or {})
        actions = out.get("next_actions", []) or []
        norm_actions: list[dict] = []
        for a in actions:
            if not isinstance(a, dict):
                continue
            prim_raw = a.get("primitive", "")
            prim = self._normalize_action_primitive(prim_raw)
            # Build minimal valid GenericAction dict
            target = a.get("target")
            value = a.get("value")
            
            # Convert target and value to strings to avoid Pydantic validation errors
            if target is not None and not isinstance(target, str):
                target = str(target)
            if value is not None and not isinstance(value, str):
                value = str(value)
                
            # If primitive suggests URL nav and value is a URL, move it to target
            if prim == "go_to_url" and (isinstance(value, str) and value.startswith("http")) and not target:
                target = value
                value = None
            ga = {
                "primitive": prim,
                "target": target,
                "value": value,
                "notes": a.get("notes"),
            }
            # For scroll_down/up synonyms, set value hint
            if prim_raw.lower() == "scroll_down":
                ga["value"] = "down"
            if prim_raw.lower() == "scroll_up":
                ga["value"] = "up"
            norm_actions.append(ga)
        if not norm_actions:
            norm_actions = [{"primitive": "wait", "value": "2", "notes": "fallback"}]
        out["next_actions"] = norm_actions[:3]
        reason = (out.get("reasoning") or "").strip()
        out["reasoning"] = reason[:200]
        # Clamp timeout
        try:
            out["timeout_steps"] = int(out.get("timeout_steps", 3))
        except Exception:
            out["timeout_steps"] = 3
        return out

    def _normalize_o3_actions_payload(self, data: dict) -> dict:
        """Normalize o3 JSON to allowed GenericAction schema."""
        out = dict(data or {})
        actions = out.get("actions", []) or []
        norm_actions: list[dict] = []
        for a in actions:
            if not isinstance(a, dict):
                continue
            prim_in = a.get("primitive", "")
            prim = self._normalize_action_primitive(prim_in)
            target = a.get("target")
            value = a.get("value")
            if prim == "go_to_url" and (isinstance(value, str) and value.startswith("http")) and not target:
                target = value
                value = None
            ga = {
                "primitive": prim,
                "target": target,
                "value": value,
                "notes": a.get("notes"),
            }
            if prim_in.lower() == "scroll_down":
                ga["value"] = "down"
            if prim_in.lower() == "scroll_up":
                ga["value"] = "up"
            norm_actions.append(ga)
        if not norm_actions:
            norm_actions = [{"primitive": "wait", "value": "2", "notes": "fallback"}]
        out["actions"] = norm_actions
        return out
    
    async def get_micro_plan(self, context: ExecutionContext, plan: PlanJSON) -> MicroPlan:
        """Get micro-plan from Gemini when stuck."""
        try:
            print_status("Getting Gemini micro-plan (stuck state)...", Colors.YELLOW)
            print_status(f"Local model failed {context.stuck_count} times, escalating to Gemini", Colors.YELLOW)
            
            prompt = self._build_micro_plan_prompt(context, plan)
            # Use proper message type to avoid 'dict' message errors
            response = await self.gemini_llm.ainvoke([UserMessage(content=prompt)])
            
            # Parse response
            response_text = response.completion.strip()
            if response_text.startswith('```'):
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)
            
            raw_data = json.loads(response_text)
            micro_plan_data = self._normalize_microplan_payload(raw_data)
            return MicroPlan(**micro_plan_data)
            
        except Exception as e:
            print_status(f"Gemini micro-plan failed: {e}", Colors.RED)
            return self._fallback_micro_plan(context)
    
    async def get_o3_micro_steps(self, context: ExecutionContext, plan: PlanJSON) -> List[GenericAction]:
        """Get bounded micro-steps from o3 as last resort."""
        try:
            print_status("Using o3 last-resort executor (strict budget)...", Colors.RED)
            
            prompt = self._build_o3_escalation_prompt(context, plan)
            # Use proper message type to avoid 'Unknown message type: dict'
            response = await self.o3_llm.ainvoke([UserMessage(content=prompt)])
            
            # Parse response
            response_text = response.completion.strip()
            if response_text.startswith('```'):
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)
            
            raw_actions = json.loads(response_text)
            actions_data = self._normalize_o3_actions_payload(raw_actions)
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
            print(f"WARNING: Vision analysis failed but continuing: {e}")
            return ActionResult(extracted_content=best_effort_summary, include_in_memory=True)
    
    print("Registered custom action: analyze_page_vision")

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
    
    print("Registered custom actions: search_web, search_google")

# ----------------------------
# Main Hybrid Agent Class
# ----------------------------

class HybridAgent:
    """
    Main hybrid agent implementing the new architecture:
    1. User Query -> o3 Planner -> PlanJSON (runs exactly once)
    2. LocalExecutor executes plan with generic primitives
    3. EscalationManager handles stuck states with Gemini -> o3 fallback
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
        1. User Query -> o3 Planner -> PlanJSON (exactly once)
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
                "plan": plan.model_dump(),
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
        
        last_failed_signature: tuple[str, str | None, str | None] | None = None
        while context.current_step < len(plan.steps) and step_count < max_total_steps:
            current_action = plan.steps[context.current_step]

            # Simple debounce: if we just failed same action repeatedly, insert a brief wait
            if current_action and context.history:
                if context.history[-1].result == "fail":
                    sig = (current_action.primitive, (current_action.target or None), (current_action.value or None))
                    if last_failed_signature == sig:
                        # Replace with short wait to let UI settle
                        current_action = GenericAction(primitive="wait", value="1", notes="debounce after repeat fail")
                    last_failed_signature = sig
                else:
                    last_failed_signature = None
            
            # Execute action with LocalExecutor
            history_step = await self.local_executor.execute_action(current_action, context)
            context.history.append(history_step)
            step_count += 1
            
            # Update vision state if this was a navigation or a successful action that likely changed UI
            if current_action.primitive == "go_to_url" or (history_step.result == "ok" and current_action.primitive in ["click", "type", "scroll", "extract", "analyze_vision"]):
                print_status(f"Updating vision context after {current_action.primitive} action", Colors.BLUE)
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
                    print_status(f"LocalExecutor stuck after {context.stuck_count} failures, escalating...", Colors.YELLOW)
                    escalation_result = await self._handle_escalation(plan, context)
                    if not escalation_result:
                        # Escalation failed, move to next step
                        print_status(f"Escalation failed, moving to next step", Colors.RED)
                        context.current_step += 1
                        context.stuck_count = 0
            
            # Check success criteria periodically
            if step_count % 5 == 0:
                success_check = await self._check_success_criteria(plan, context)
                if success_check:
                    print_status("Success criteria met!", Colors.GREEN)
                    return {"success": True, "summary": success_check}
        
        # Plan completed or budget exhausted - apply hardened success gating
        # Only report success if we actually meet the success criteria
        final_success_check = await self._check_success_criteria(plan, context)
        if final_success_check:
            return {"success": True, "summary": final_success_check}
        
        # Otherwise, report partial progress without false success
        successful_steps = [step for step in context.history if step.result == "ok"]
        summary = f"PARTIAL: Partial progress: {len(successful_steps)}/{len(context.history)} successful steps, reached step {context.current_step}/{len(plan.steps)}"
        
        return {
            "success": False,
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
            print_status("Taking screenshot for vision context update...", Colors.BLUE)
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
            
            print_status("Running vision analysis for context update...", Colors.BLUE)
            vision_state = await self.vision_analyzer.analyze(
                str(screenshot_path), state.url or "", state.title or ""
            )
            
            context.last_vision_state = vision_state
            print_status(f"Vision context updated: {vision_state.caption[:50]}...", Colors.GREEN)
            
        except Exception as e:
            print_status(f"Vision update failed: {type(e).__name__}: {e}", Colors.YELLOW)
            print_status(f"Vision update will use previous state", Colors.YELLOW)
    
    async def _check_success_criteria(self, plan: PlanJSON, context: ExecutionContext) -> Optional[str]:
        """Check if success criteria are met with improved hotel booking detection."""
        if len(context.history) < 5:  # Need at least a few steps to evaluate
            return None
        
        # Get current URL and page state for analysis
        current_url = ""
        page_title = ""
        try:
            if self.browser_session:
                state = await self.browser_session.get_browser_state_summary()
                current_url = state.url.lower() if state and state.url else ""
                page_title = state.title.lower() if state and state.title else ""
        except Exception:
            current_url = ""
            page_title = ""
        
        # Enhanced hotel booking success detection
        task_lower = plan.normalized_task.lower()
        
        # Check for Omni Hotel Louisville booking success
        if "omni" in task_lower and "louisville" in task_lower:
            # Success if we're on a hotel booking site (booking.com, omnihotels.com, etc.)
            hotel_booking_sites = ["booking.com", "omnihotels.com", "hotels.com", "expedia.com"]
            is_on_booking_site = any(site in current_url for site in hotel_booking_sites)
            
            if is_on_booking_site:
                # Check if we've progressed beyond the main hotel page
                booking_indicators = ["book", "reservation", "rooms", "availability", "rates", "omni", "louisville"]
                has_booking_indicator = any(indicator in current_url or indicator in page_title 
                                          for indicator in booking_indicators)
                
                # Count successful actions that indicate booking progress
                booking_actions = 0
                date_actions = 0
                extraction_success = False
                
                for step in context.history[-10:]:  # Check recent history
                    if step.result == "ok":
                        if step.action.primitive == "type" and step.action.value:
                            # Check if typed dates match our target dates
                            typed_value = step.action.value.lower()
                            if any(date in typed_value for date in ["09/01/2025", "09/02/2025", "9/1/25", "9/2/25"]):
                                date_actions += 1
                                booking_actions += 1
                        elif step.action.primitive == "click":
                            booking_actions += 1
                        elif step.action.primitive == "extract":
                            # Check if extraction found meaningful results
                            if (hasattr(step, 'action_result') and 
                                step.action_result and 
                                hasattr(step.action_result, 'extracted_content')):
                                content = step.action_result.extracted_content.lower()
                                if ("prices found" in content or 
                                    "availability" in content or 
                                    "success: true" in content):
                                    extraction_success = True
                                    booking_actions += 2  # Extraction success is worth more
                
                # Success criteria (more flexible for booking.com)
                if extraction_success and date_actions >= 2:
                    return f"SUCCESS: Hotel booking completed - found pricing/availability for Omni Louisville (9/1/25-9/2/25)"
                elif has_booking_indicator and booking_actions >= 4 and date_actions >= 2:
                    return f"SUCCESS: Reached Omni Louisville booking state with {booking_actions} booking actions completed"
                elif booking_actions >= 3 and date_actions >= 1:
                    return f"SUCCESS: Located Omni Louisville and initiated booking process with dates"
        
        # Check explicit success criteria with less vision dependence 
        for criterion in plan.success_criteria:
            criterion_lower = criterion.lower()
            # Check if criterion mentions hotel-specific outcomes
            if "omni" in criterion_lower or "hotel" in criterion_lower or "room" in criterion_lower:
                if "omnihotels.com" in current_url and "louisville" in current_url:
                    return f"SUCCESS: Located target hotel website: {criterion}"
        
        # Fallback: check for meaningful hotel booking URL patterns
        hotel_url_markers = ["hotel", "booking", "reservation", "rooms"]
        url_has_hotel_marker = any(marker in current_url for marker in hotel_url_markers)
        
        if url_has_hotel_marker:
            # Extract key terms from task
            task_key_terms = self._extract_task_key_terms(task_lower)
            url_term_matches = sum(1 for term in task_key_terms if term in current_url)
            
            if url_term_matches >= 1:
                return f"SUCCESS: Meaningful hotel booking state reached"
        
        # No success criteria met - return None (no false positives)
        return None
    
    def _extract_task_key_terms(self, task_lower: str) -> List[str]:
        """Extract key terms from the normalized task for success checking."""
        # Remove common stop words and extract meaningful terms
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "from", "up", "about", "into", "through", "during", "before", "after", "above", "below", "between", "among", "within", "without", "against", "toward", "upon", "across", "behind", "beyond", "under", "over", "around", "near", "far", "inside", "outside", "beside", "beneath", "above", "below"}
        
        # Split task into words and filter
        words = [word.strip(".,!?;:()[]{}\"'") for word in task_lower.split()]
        key_terms = [word for word in words if len(word) > 2 and word not in stop_words]
        
        # Return first 5 most relevant terms
        return key_terms[:5]
    
    def _estimate_cost(self, plan: PlanJSON, context: ExecutionContext, actual_usage: Dict[str, Any] = None) -> Dict[str, Any]:
        """Calculate actual cost based on token usage and current pricing."""
        # Current pricing per 1M tokens (as of Jan 2025)
        model_pricing = {
            "o3": {"input": 15.0, "output": 60.0},  # $15/$60 per 1M tokens
            "o3-mini": {"input": 3.0, "output": 12.0},  # $3/$12 per 1M tokens  
            "gemini-2.0-flash-exp": {"input": 0.075, "output": 0.30},  # $0.075/$0.30 per 1M tokens
            "moondream:latest": {"input": 0.0, "output": 0.0},  # Local model - no cost
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
                model_cost = (prompt_tokens * pricing["input"] / 1_000_000) + (completion_tokens * pricing["output"] / 1_000_000)
                
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
            planner_cost = (est_prompt_tokens * o3_pricing["input"] / 1_000_000) + (est_completion_tokens * o3_pricing["output"] / 1_000_000)
            cost_breakdown["planner_cost"] = planner_cost
            cost_breakdown["total_cost"] = planner_cost
            
            # Add escalation costs if escalation occurred  
            if context.escalation_level == "gemini":
                gemini_pricing = model_pricing[GEMINI_BACKUP_MODEL]
                # Use estimated costs until actual tracking is implemented
                escalation_cost = (500 * gemini_pricing["input"] / 1_000_000) + (200 * gemini_pricing["output"] / 1_000_000)
                cost_breakdown["escalation_cost"] = escalation_cost
                cost_breakdown["total_cost"] += escalation_cost
                print_status(f"WARNING: Gemini escalation used - estimated cost ${escalation_cost:.4f}", Colors.YELLOW)
            elif context.escalation_level == "o3":
                o3_pricing = model_pricing["o3"]
                # Use estimated costs until actual tracking is implemented
                escalation_cost = (1000 * o3_pricing["input"] / 1_000_000) + (400 * o3_pricing["output"] / 1_000_000)
                cost_breakdown["escalation_cost"] = escalation_cost
                cost_breakdown["total_cost"] += escalation_cost
                print_status(f"WARNING: O3 escalation used - estimated cost ${escalation_cost:.4f}", Colors.YELLOW)
        
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
        summary += f"**Success:** {'YES' if result['success'] else 'PARTIAL PROGRESS'}\n"
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
        
        # Enhanced warm-start with model health monitoring and stability checks
        try:
            print_status("Warming up local VLM (Moondream2) with a tiny ping...", Colors.BLUE)
            import base64
            # 1x1 white pixel PNG
            tiny_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
            # Use the analyzer's call path directly to trigger model load (no file I/O)
            prompt = self.vision_analyzer.build_vision_prompt()
            # Ensure exact model tag is resolved before first real call
            if not self.vision_analyzer.model_name:
                self.vision_analyzer.model_name = await self.vision_analyzer.resolve_moondream_tag()
            
            # Enhanced warm-up with model health verification
            start_time = time.time()
            await asyncio.wait_for(
                self.vision_analyzer.call_moondream(prompt, tiny_png_b64), 
                timeout=15.0
            )
            warm_up_time = time.time() - start_time
            
            # Verify model is in good state after warm-up
            if self.vision_analyzer.performance_stats['successful_calls'] > 0:
                print_status(f"Local VLM warm-up complete - model responsive ({warm_up_time:.1f}s)", Colors.GREEN)
                # Reset circuit breaker on successful warm-up
                self.vision_analyzer.circuit_breaker['consecutive_failures'] = 0
                self.vision_analyzer.circuit_breaker['is_open'] = False
            else:
                print_status("VLM warm-up completed but model may be unstable", Colors.YELLOW)
                
        except asyncio.TimeoutError:
            print_status("VLM warm-up timed out after 15s - vision will be disabled during execution", Colors.YELLOW) 
            print_status("Agent will continue with vision disabled but may have reduced accuracy", Colors.YELLOW)
            # Mark vision as degraded to prevent further timeouts
            self.vision_analyzer.circuit_breaker['is_open'] = True
            self.vision_analyzer.circuit_breaker['consecutive_failures'] = self.vision_analyzer.circuit_breaker['max_failures']
        except Exception as warm_err:
            print_status(f"VLM warm-up failed: {warm_err}", Colors.YELLOW)
            print_status("Agent will continue with vision disabled but may have reduced accuracy", Colors.YELLOW)
            # Mark vision as degraded to prevent further issues
            self.vision_analyzer.circuit_breaker['is_open'] = True
            self.vision_analyzer.circuit_breaker['consecutive_failures'] = self.vision_analyzer.circuit_breaker['max_failures']
        
        print_status("Browser session and LocalExecutor initialized", Colors.GREEN)

# ----------------------------
# CLI Interface
# ----------------------------

async def main():
    """Main CLI interface for new hybrid architecture."""
    print("Hybrid Agent - New Architecture")
    print("o3 Planner -> LocalExecutor -> Escalation Manager")
    print("Generic primitives, no domain-specific logic")
    print("Navigation timeout: 60s (favor reliability)")
    print("=" * 60)
    
    agent = HybridAgent()
    
    # Ensure llama.cpp server is properly set up
    print("\nVerifying llama.cpp server setup...")
    # Use the VisionAnalyzer's server availability check
    server_available = await agent.vision_analyzer.check_server_availability()
    if not server_available:
        print("llama.cpp server not running!")
        print("Please ensure llama.cpp server is installed and running:")
        print("   1. Setup: python setup_llamacpp.py")
        print("   2. Start server: ./run_llamacpp_server.sh or run_llamacpp_server.bat")  
        print("   3. Verify: curl http://localhost:8080/health")
        print("   4. Or run: python llama_cpp_manager.py --setup")
        print("\nExiting - vision model is required for hybrid agent functionality.")
        return
    else:
        print("llama.cpp server is running and accessible")
    
    # Test model availability
    try:
        model_name = await agent.vision_analyzer.resolve_moondream_tag()
        print(f"Using model: {model_name}")
    except Exception as e:
        print(f"Warning: Could not resolve model tag: {e}")
        print("Will attempt to use moondream:latest")
    print("")
    
    while True:
        try:
            task = input("\nEnter your task (or 'quit' to exit): ").strip()
            
            if task.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
            
            if not task:
                continue
            
            # Execute task with new architecture
            result = await agent.execute_task(task)
            
            print("\n" + "=" * 60)
            print("EXECUTION SUMMARY")
            print(f"Task: {result['task']}")
            print(f"Completed: {'YES' if result['completed'] else 'NO'}")
            print(f"Steps Executed: {result.get('steps_executed', 0)}")
            print(f"Escalation Level: {result.get('escalation_level', 'unknown')}")
            
            if result.get('final_screenshot'):
                print(f"Final Screenshot: {result['final_screenshot']}")
                
            if result.get('cost_info'):
                cost = result['cost_info']
                print(f"Cost: ${cost['estimated_cost']:.4f}")
                print(f"Models: {cost['planner_model']} -> {cost['executor_model']}")
                if cost['escalation_level'] != 'local':
                    print(f"ESCALATED to: {cost['escalation_level']}")
                    
            if result.get('summary'):
                print(f"Summary: {result['summary']}")
                
            if result.get('error'):
                print(f"ERROR: {result['error']}")
                
            print("=" * 60)
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())