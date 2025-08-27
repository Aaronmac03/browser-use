#!/usr/bin/env python3
"""
Hybrid Local-Vision + Cloud-Reasoning Agent for Browser-Use 0.6.x

A hybrid browser automation system that uses:
- Local VLM (MiniCPM-V 2.6) for fast vision processing and simple actions
- Cloud reasoning (Gemini 2.0 Flash) for complex planning and decision making
"""

import asyncio
import json
import os
import hashlib
import base64
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from urllib.parse import urlparse

from dotenv import load_dotenv
from pydantic import BaseModel, Field
import httpx

# Load environment variables
load_dotenv(override=True)

# Browser-Use 0.6.x imports
from browser_use import Agent, Controller, ActionResult
from browser_use.browser import BrowserProfile, BrowserSession
from browser_use.llm import ChatGoogle, ChatOpenAI

# Import serper search functionality
from serper_search import search_with_serper_fallback

# ----------------------------
# Data Schemas
# ----------------------------

class VisionElement(BaseModel):
    """Individual UI element detected by vision system."""
    role: str = Field(description="Element type: button|link|text|image|other")
    visible_text: str = Field(description="Text content visible to user")
    attributes: Dict[str, str] = Field(description="HTML attributes", default_factory=dict)
    selector_hint: str = Field(description="CSS/XPath selector hint for targeting")
    bbox: List[int] = Field(description="Bounding box [x,y,w,h]")
    confidence: float = Field(description="Vision confidence score 0-1")

class VisionField(BaseModel):
    """Form field detected by vision system."""
    name_hint: str = Field(description="Field name/label hint")
    value_hint: str = Field(description="Current field value if visible")
    bbox: List[int] = Field(description="Bounding box [x,y,w,h]")
    editable: bool = Field(description="Whether field accepts input")

class VisionAffordance(BaseModel):
    """Interactive affordance detected by vision system."""
    type: str = Field(description="Affordance type: button|link|tab|menu|icon")
    label: str = Field(description="Human-readable label")
    selector_hint: str = Field(description="CSS/XPath selector hint")
    bbox: List[int] = Field(description="Bounding box [x,y,w,h]")

class VisionMeta(BaseModel):
    """Page metadata from vision analysis."""
    url: str = Field(description="Current page URL")
    title: str = Field(description="Page title")
    scrollY: int = Field(description="Vertical scroll position")
    timestamp: str = Field(description="ISO8601 timestamp of capture")

class VisionState(BaseModel):
    """Complete vision state of current page."""
    caption: str = Field(description="Brief description of page content", max_length=200)
    elements: List[VisionElement] = Field(description="UI elements detected")
    fields: List[VisionField] = Field(description="Form fields detected")  
    affordances: List[VisionAffordance] = Field(description="Interactive elements")
    meta: VisionMeta = Field(description="Page metadata")

class Action(BaseModel):
    """Single browser action to execute."""
    op: str = Field(description="Operation: click|type|scroll|navigate|wait|select|hover")
    target: Dict[str, str] = Field(description="Target with selector_hint and optional text")
    value: Optional[str] = Field(description="Value for type/select operations", default=None)
    notes: Optional[str] = Field(description="Optional execution notes", default=None)

class HistoryStep(BaseModel):
    """Single step in execution history."""
    action: str = Field(description="Action description")
    result: str = Field(description="Result: ok|fail")
    summary: str = Field(description="Brief summary of what happened")

class PlannerRequest(BaseModel):
    """Request sent to cloud planner."""
    task: str = Field(description="User's goal description")
    history: List[HistoryStep] = Field(description="Recent action history")
    vision: VisionState = Field(description="Current page vision state")
    constraints: Dict[str, Any] = Field(description="Execution constraints", default_factory=dict)

class PlannerResponse(BaseModel):
    """Response from cloud planner."""
    plan: List[Action] = Field(description="Ordered list of actions to execute")
    reasoning_summary: str = Field(description="Brief reasoning explanation", max_length=300)
    needs_more_context: bool = Field(description="Whether more context is needed")

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
# Vision State Builder
# ----------------------------

class VisionStateBuilder:
    """Builds VisionState from screenshots using local MiniCPM-V 2.6."""
    
    def __init__(self, model_endpoint: str = "http://localhost:11434", model_name: Optional[str] = None):
        self.model_endpoint = model_endpoint.rstrip('/')
        self.model_name = model_name
        self.client = httpx.AsyncClient(timeout=60.0)
        self.vision_cache = {}
        
    async def build_vision_state(self, screenshot_path: str, page_url: str, page_title: str) -> VisionState:
        """Build VisionState from screenshot using local VLM."""
        # Check cache first
        screenshot_hash = self._hash_screenshot(screenshot_path)
        if screenshot_hash in self.vision_cache:
            cached_state = self.vision_cache[screenshot_hash]
            cached_state.meta.url = page_url
            cached_state.meta.title = page_title
            cached_state.meta.timestamp = datetime.now().isoformat()
            return cached_state
        
        # Encode screenshot
        with open(screenshot_path, 'rb') as f:
            image_b64 = base64.b64encode(f.read()).decode('utf-8')
        
        prompt = self._build_vision_prompt()
        
        try:
            response = await self._call_local_vlm(prompt, image_b64)
            vision_data = self._parse_vision_response(response)
            
            vision_state = VisionState(
                caption=vision_data.get('caption', 'UI screenshot'),
                elements=[VisionElement(**elem) for elem in vision_data.get('elements', [])],
                fields=[VisionField(**field) for field in vision_data.get('fields', [])],
                affordances=[VisionAffordance(**afford) for afford in vision_data.get('affordances', [])],
                meta=VisionMeta(
                    url=page_url,
                    title=page_title,
                    scrollY=0,
                    timestamp=datetime.now().isoformat()
                )
            )
            
            self.vision_cache[screenshot_hash] = vision_state
            return vision_state
            
        except Exception as e:
            print(f"⚠️ Vision analysis failed but continuing: {e}")
            return self._fallback_vision_state(page_url, page_title)
    
    def _build_vision_prompt(self) -> str:
        return """Analyze this screenshot and extract UI elements as JSON.

Find buttons, links, input fields, text, and interactive elements. Return JSON only:

{
  "caption": "Brief description of the page",
  "elements": [
    {
      "role": "button|link|text|input|other",
      "visible_text": "text shown", 
      "attributes": {},
      "selector_hint": "element description",
      "bbox": [0, 0, 0, 0],
      "confidence": 0.8
    }
  ],
  "fields": [
    {
      "name_hint": "field name",
      "value_hint": "current value", 
      "bbox": [0, 0, 0, 0],
      "editable": true
    }
  ],
  "affordances": [
    {
      "type": "button|link|tab|menu",
      "label": "element label",
      "selector_hint": "how to find it",
      "bbox": [0, 0, 0, 0]
    }
  ]
}"""

    async def _call_local_vlm(self, prompt: str, image_b64: str) -> Dict[str, Any]:
        if not self.model_name:
            self.model_name = await resolve_minicpm_tag(self.model_endpoint)
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1}
        }
        
        response = await self.client.post(
            f"{self.model_endpoint}/api/generate",
            json=payload
        )
        
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
        
        return response.json()
    
    def _parse_vision_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response_text = response.get('response', '{}')
            
            # Extract JSON
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_text = response_text[start_idx:end_idx]
            else:
                json_text = response_text
            
            vision_data = json.loads(json_text)
            
            # Validate and set defaults
            if not isinstance(vision_data, dict):
                vision_data = {}
                
            vision_data.setdefault('elements', [])
            vision_data.setdefault('fields', [])
            vision_data.setdefault('affordances', [])
            vision_data.setdefault('caption', 'UI screenshot analysis')
            
            # Validate elements
            valid_elements = []
            for elem in vision_data.get('elements', []):
                if isinstance(elem, dict):
                    elem.setdefault('role', 'other')
                    elem.setdefault('visible_text', '')
                    elem.setdefault('attributes', {})
                    elem.setdefault('selector_hint', '')
                    elem.setdefault('bbox', [0, 0, 0, 0])
                    elem.setdefault('confidence', 0.5)
                    valid_elements.append(elem)
            vision_data['elements'] = valid_elements
                
            return vision_data
            
        except (json.JSONDecodeError, KeyError) as e:
            return {
                'caption': 'Vision analysis parsing failed',
                'elements': [],
                'fields': [],
                'affordances': []
            }
    
    def _fallback_vision_state(self, page_url: str, page_title: str) -> VisionState:
        return VisionState(
            caption="Vision analysis unavailable",
            elements=[],
            fields=[],
            affordances=[],
            meta=VisionMeta(
                url=page_url,
                title=page_title,
                scrollY=0,
                timestamp=datetime.now().isoformat()
            )
        )
    
    def _hash_screenshot(self, screenshot_path: str) -> str:
        with open(screenshot_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

# ----------------------------
# Local Action Heuristics
# ----------------------------

class LocalActionHeuristics:
    """Determines if actions can be handled locally vs requiring cloud planning."""
    
    SIMPLE_ACTIONS = {'click', 'type', 'scroll', 'navigate', 'wait'}
    CONFIDENCE_THRESHOLD = 0.75
    
    def can_handle_locally(self, intent: str, vision_state: VisionState) -> bool:
        action_type = self._extract_action_type(intent)
        
        if action_type not in self.SIMPLE_ACTIONS:
            return False
        
        if action_type in ['click', 'type']:
            return self._has_unambiguous_target(intent, vision_state)
        
        if action_type in ['scroll', 'navigate', 'wait']:
            return True
            
        return False
    
    def _extract_action_type(self, intent: str) -> str:
        intent_lower = intent.lower()
        
        if any(word in intent_lower for word in ['click', 'press', 'select', 'choose']):
            return 'click'
        elif any(word in intent_lower for word in ['type', 'enter', 'input', 'fill']):
            return 'type'
        elif any(word in intent_lower for word in ['scroll', 'page down', 'page up']):
            return 'scroll'
        elif any(word in intent_lower for word in ['go to', 'navigate', 'visit']):
            return 'navigate'
        elif any(word in intent_lower for word in ['wait', 'pause', 'delay']):
            return 'wait'
        else:
            return 'unknown'
    
    def _has_unambiguous_target(self, intent: str, vision_state: VisionState) -> bool:
        intent_words = set(intent.lower().split())
        candidates = []
        
        for element in vision_state.elements:
            if element.confidence < self.CONFIDENCE_THRESHOLD:
                continue
            element_words = set(element.visible_text.lower().split())
            if intent_words & element_words:
                candidates.append(element)
        
        for affordance in vision_state.affordances:
            affordance_words = set(affordance.label.lower().split())
            if intent_words & affordance_words:
                candidates.append(affordance)
        
        return len(candidates) == 1

# ----------------------------
# Cloud Planner Client
# ----------------------------

class CloudPlannerClient:
    """Client for cloud-based planning using OpenAI."""
    
    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.model_name = model_name
        self.llm = ChatOpenAI(model=model_name)
    
    async def get_plan(self, request: PlannerRequest) -> PlannerResponse:
        try:
            prompt = self._build_planner_prompt(request)
            
            # Use regular generation
            response = await self.llm.ainvoke([{"role": "user", "content": prompt}])
            
            # Parse the response
            response_text = response.completion.strip()
            
            # Try to extract JSON from response
            if response_text.startswith('```'):
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)
            
            try:
                response_data = json.loads(response_text)
                return PlannerResponse(**response_data)
            except:
                # Fallback response
                return PlannerResponse(
                    plan=[],
                    reasoning_summary="Failed to parse planner response",
                    needs_more_context=True
                )
            
        except Exception as e:
            print(f"Cloud planning failed: {e}")
            return PlannerResponse(
                plan=[],
                reasoning_summary=f"Planning failed: {str(e)}",
                needs_more_context=True
            )
    
    def _build_planner_prompt(self, request: PlannerRequest) -> str:
        prompt = f"""You are a web automation planner. Create an action plan to complete the task.

TASK: {request.task}

CURRENT PAGE:
URL: {request.vision.meta.url}
Description: {request.vision.caption}

AVAILABLE ELEMENTS:
"""
        
        for i, elem in enumerate(request.vision.elements[:10], 1):
            prompt += f"- {elem.role}: '{elem.visible_text}'\n"
        
        if request.history:
            prompt += f"\nRECENT HISTORY:\n"
            for step in request.history[-5:]:
                prompt += f"- {step.action} → {step.result}\n"
        
        prompt += f"""
GUIDANCE:
- After search, prefer clicking relevant results to get actual content
- Avoid finalizing with google.com/search URLs - click through to actual sites
- When on search results, look for product pages, official sites, or detailed content
- For price/product information, navigate to retailer sites (kroger.com, etc.)

Current URL context: {request.vision.meta.url}
If currently on Google/search results, prioritize clicking relevant links.

Return a simple task to navigate or search for the information requested.
Keep it focused on finding the specific information the user wants.

Response format (JSON):
{{
  "plan": [],
  "reasoning_summary": "Navigate to [site] and search for [query]",
  "needs_more_context": false
}}"""
        
        return prompt

# ----------------------------
# Handoff Manager  
# ----------------------------

class HandoffManager:
    """Manages routing between local and cloud execution."""
    
    def __init__(self, confidence_threshold: float = 0.75, failure_threshold: int = 2):
        self.confidence_threshold = confidence_threshold
        self.failure_threshold = failure_threshold
        self.consecutive_local_failures = 0
        self.history: List[HistoryStep] = []
    
    def should_use_local(self, intent: str, vision_state: VisionState, local_heuristics: LocalActionHeuristics) -> bool:
        if self.consecutive_local_failures >= self.failure_threshold:
            return False
        
        if vision_state.elements:
            avg_confidence = sum(elem.confidence for elem in vision_state.elements) / len(vision_state.elements)
            if avg_confidence < self.confidence_threshold:
                return False
        
        return local_heuristics.can_handle_locally(intent, vision_state)
    
    def record_local_result(self, action: str, success: bool, summary: str):
        result = "ok" if success else "fail"
        self.history.append(HistoryStep(action=action, result=result, summary=summary))
        
        if success:
            self.consecutive_local_failures = 0
        else:
            self.consecutive_local_failures += 1
    
    def record_cloud_result(self, action: str, success: bool, summary: str):
        result = "ok" if success else "fail"
        self.history.append(HistoryStep(action=action, result=result, summary=summary))
        self.consecutive_local_failures = 0
    
    def get_recent_history(self, max_steps: int = 5) -> List[HistoryStep]:
        return self.history[-max_steps:] if self.history else []

# ----------------------------
# Custom Action for Vision Analysis
# ----------------------------

async def register_vision_action(controller: Controller, vision_builder: VisionStateBuilder, screenshots_dir: Path):
    """Register custom action for vision analysis."""
    
    @controller.action("Analyze current page with local vision")
    async def analyze_page_vision(browser_session: BrowserSession) -> ActionResult:
        """Take screenshot and analyze with local VLM. No-fail implementation."""
        try:
            state = await browser_session.get_browser_state_summary()
            screenshot_path = await browser_session.take_screenshot()
            vision_state = await vision_builder.build_vision_state(
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
# Hybrid Agent Main Class
# ----------------------------

class HybridAgent:
    """Main hybrid agent using Browser-Use 0.6.x API correctly."""
    
    def __init__(self, screenshots_dir: str = "browser_queries/screenshots", user_data_dir: Optional[str] = None):
        self.screenshots_dir = Path(screenshots_dir)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.vision_builder = VisionStateBuilder()
        self.local_heuristics = LocalActionHeuristics()
        self.cloud_planner = CloudPlannerClient()
        self.handoff_manager = HandoffManager()
        
        # State tracking
        self.current_vision_state: Optional[VisionState] = None
        self.consecutive_failures = 0
        
        # Set up user data directory
        if user_data_dir is None:
            user_data_dir = str(Path.home() / ".config" / "browser-use" / "hybrid-agent")
        self.user_data_dir = Path(user_data_dir)
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Browser-Use components (will be initialized on first use)
        self.browser_session: Optional[BrowserSession] = None
        self.agent: Optional[Agent] = None
    
    async def execute_task(self, task: str) -> Dict[str, Any]:
        """Execute a task using hybrid approach with Browser-Use 0.6.x."""
        print(f"🤖 Starting hybrid task: {task}")
        
        # Initialize browser session if needed
        if not self.browser_session:
            await self._initialize_browser()
        
        # Create task description that incorporates vision analysis
        enhanced_task = self._create_enhanced_task(task)
        
        # Create controller and register custom actions
        controller = Controller()
        await register_vision_action(controller, self.vision_builder, self.screenshots_dir)
        await register_serper_action(controller)
        
        # Create agent with the task
        self.agent = Agent(
            task=enhanced_task,
            llm=self.cloud_planner.llm,
            controller=controller,
            browser_session=self.browser_session,
            use_vision=True,  # Enable vision for Browser-Use
            save_conversation_path=str(self.screenshots_dir / "conversations"),
        )
        
        # Run the agent
        try:
            print("🚀 Running Browser-Use agent with hybrid enhancements...")
            history = await self.agent.run(max_steps=15)
            
            # Extract results using AgentHistoryList helpers
            success = history.is_done() and not history.has_errors()
            final_url = (history.urls() or [None])[-1]
            
            # Capture screenshot on completion for finalization guardrails
            screenshot_path = None
            if success and self.browser_session:
                try:
                    screenshot_path = await self.browser_session.take_screenshot()
                    print(f"📸 Final screenshot saved: {screenshot_path}")
                except Exception as e:
                    print(f"⚠️ Failed to capture final screenshot: {e}")
            
            return {
                "task": task,
                "completed": success,
                "iterations": len(history),
                "history_length": len(history),
                "final_url": final_url,
                "final_screenshot": str(screenshot_path) if screenshot_path else None
            }
            
        except Exception as e:
            print(f"❌ Agent execution failed: {e}")
            import traceback
            traceback.print_exc()
            return {
                "task": task,
                "completed": False,
                "iterations": 0,
                "history_length": 0,
                "error": str(e)
            }
    
    async def _initialize_browser(self):
        """Initialize browser session using Browser-Use 0.6.x API."""
        print("🌐 Initializing browser session...")
        
        # Create browser profile
        browser_profile = BrowserProfile(
            user_data_dir=str(self.user_data_dir),
            headless=False,
            keep_alive=True,
            stealth=False,  # Disable stealth to avoid issues
            enable_default_extensions=False,  # Disable to silence CRX warnings
            wait_for_network_idle_page_load_time=3.0,
            minimum_wait_page_load_time=0.5,
            maximum_wait_page_load_time=8.0,
            wait_between_actions=0.7,
            default_timeout=10_000,
            default_navigation_timeout=45_000,
        )
        
        print(f"🗂️ Using user_data_dir: {browser_profile.user_data_dir}")
        
        # Create browser session
        self.browser_session = BrowserSession(browser_profile=browser_profile)
        
        print("✅ Browser session initialized")
    
    def _create_enhanced_task(self, task: str) -> str:
        """Create enhanced task description for the agent."""
        
        # Determine task type and enhance accordingly
        task_lower = task.lower()
        
        if 'weather' in task_lower:
            # Extract location
            import re
            zip_match = re.search(r'\b\d{5}\b', task)
            location = zip_match.group() if zip_match else task.replace('check weather', '').strip()
            
            return f"""Navigate to Google and search for weather in {location}.
Find and report the current temperature, conditions, and forecast.
Use the custom action 'analyze_page_vision' periodically to understand page content.
"""
        
        elif any(word in task_lower for word in ['search', 'find', 'look up']):
            return f"""Use the custom action 'search_web' to search for: {task}
Alternatively, navigate to Google and perform the search.
Report the top results found.
Use 'analyze_page_vision' to understand search results.
"""
        
        else:
            return f"""{task}
Use the custom action 'analyze_page_vision' periodically to understand page content.
This will help you navigate and interact with the page more effectively.
"""

# ----------------------------
# CLI Interface
# ----------------------------

async def main():
    """Main CLI interface."""
    print("🤖 Hybrid Local-Vision + Cloud-Reasoning Agent")
    print("📦 Using Browser-Use 0.6.x with modern API")
    print("=" * 50)
    
    agent = HybridAgent()
    
    while True:
        try:
            task = input("\n💭 Enter your task (or 'quit' to exit): ").strip()
            
            if task.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            if not task:
                continue
            
            # Execute task
            result = await agent.execute_task(task)
            
            print("\n" + "=" * 50)
            print("📊 TASK SUMMARY")
            print(f"Task: {result['task']}")
            print(f"Completed: {'✅' if result['completed'] else '❌'}")
            print(f"Iterations: {result['iterations']}")
            print(f"History steps: {result['history_length']}")
            if result.get('final_url'):
                print(f"Final URL: {result['final_url']}")
            if result.get('final_screenshot'):
                print(f"Final screenshot: {result['final_screenshot']}")
            if result.get('error'):
                print(f"Error: {result['error']}")
            print("=" * 50)
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())