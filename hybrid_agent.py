"""
Hybrid Local-Vision + Cloud-Reasoning Agent

A hybrid browser automation system that uses:
- Local VLM (MiniCPM-V 2.6) for fast vision processing and simple actions
- Cloud reasoning (Gemini 2.0 Flash) for complex planning and decision making

Based on agent.py but with hybrid vision system replacing direct browser automation.
"""

import asyncio
import json
import os
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from urllib.parse import urlparse

from dotenv import load_dotenv
from pydantic import BaseModel, Field
import httpx

# Load environment variables
load_dotenv(override=True)

async def resolve_minicpm_tag(endpoint: str = "http://localhost:11434") -> str:
    """
    Resolve MiniCPM-V tag by querying Ollama API to avoid hardcoded :latest.
    
    Returns:
        str: Resolved model tag (e.g., 'minicpm-v')
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{endpoint}/api/tags")
            if response.status_code == 200:
                data = response.json()
                # Find minicpm model
                for model in data.get('models', []):
                    model_name = model.get('name', '')
                    if 'minicpm-v' in model_name.lower():
                        # Return without :latest suffix
                        return model_name.replace(':latest', '')
                # Fallback if not found
                return "minicpm-v"
            else:
                return "minicpm-v"  # Default fallback
    except Exception:
        return "minicpm-v"  # Default fallback

from browser_use import Agent, BrowserSession, Controller
from browser_use.llm import ChatGoogle

# Import existing functionality from agent.py
from serper_search import search_with_serper_fallback

# ----------------------------
# Data Schemas (from hybrid_brief.md)
# ----------------------------

class VisionElement(BaseModel):
    """Individual UI element detected by vision system."""
    role: str = Field(description="Element type: button|link|text|image|other")
    visible_text: str = Field(description="Text content visible to user")
    attributes: Dict[str, str] = Field(description="HTML attributes like ariaLabel, type", default_factory=dict)
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
# Vision State Builder
# ----------------------------

class VisionStateBuilder:
    """Builds VisionState from screenshots using local MiniCPM-V 2.6."""
    
    def __init__(self, 
                 model_endpoint: str = "http://localhost:11434",
                 model_name: Optional[str] = None):
        """
        Initialize vision state builder.
        
        Args:
            model_endpoint: Ollama server endpoint
            model_name: Model identifier in Ollama (auto-resolved if None)
        """
        self.model_endpoint = model_endpoint.rstrip('/')
        self.model_name = model_name  # Will be resolved at runtime
        self.client = httpx.AsyncClient(timeout=60.0)
        
        # Cache for avoiding duplicate processing
        self.vision_cache = {}
        
    async def build_vision_state(self, screenshot_path: str, page_url: str, page_title: str) -> VisionState:
        """
        Build VisionState from screenshot using local VLM.
        
        Args:
            screenshot_path: Path to screenshot file
            page_url: Current page URL  
            page_title: Current page title
            
        Returns:
            VisionState with detected elements and metadata
        """
        # Check cache first
        screenshot_hash = await self._hash_screenshot(screenshot_path)
        if screenshot_hash in self.vision_cache:
            cached_state = self.vision_cache[screenshot_hash]
            # Update metadata but keep vision analysis
            cached_state.meta.url = page_url
            cached_state.meta.title = page_title
            cached_state.meta.timestamp = datetime.now().isoformat()
            return cached_state
        
        # Encode screenshot for vision model
        with open(screenshot_path, 'rb') as f:
            import base64
            image_b64 = base64.b64encode(f.read()).decode('utf-8')
        
        # Craft prompt for structured UI analysis
        prompt = self._build_vision_prompt()
        
        try:
            # Call local VLM via Ollama API
            response = await self._call_local_vlm(prompt, image_b64)
            vision_data = self._parse_vision_response(response)
            
            # Build VisionState
            vision_state = VisionState(
                caption=vision_data.get('caption', 'UI screenshot'),
                elements=[VisionElement(**elem) for elem in vision_data.get('elements', [])],
                fields=[VisionField(**field) for field in vision_data.get('fields', [])],
                affordances=[VisionAffordance(**afford) for afford in vision_data.get('affordances', [])],
                meta=VisionMeta(
                    url=page_url,
                    title=page_title,
                    scrollY=0,  # TODO: Get actual scroll position
                    timestamp=datetime.now().isoformat()
                )
            )
            
            # Cache result
            self.vision_cache[screenshot_hash] = vision_state
            return vision_state
            
        except Exception as e:
            print(f"Vision analysis failed: {e}")
            print(f"Exception type: {type(e)}")
            import traceback
            print("Full traceback:")
            traceback.print_exc()
            # Return minimal fallback state
            return self._fallback_vision_state(page_url, page_title)
    
    def _build_vision_prompt(self) -> str:
        """Build prompt for vision model to extract structured UI data."""
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
        """Call local VLM via Ollama API."""
        # Resolve model name if not set
        if not self.model_name:
            self.model_name = await resolve_minicpm_tag(self.model_endpoint)
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1
            }
        }
        
        print(f"🔗 Calling Ollama API at {self.model_endpoint}/api/generate")
        print(f"📦 Model: {self.model_name}")
        
        try:
            response = await self.client.post(
                f"{self.model_endpoint}/api/generate",
                json=payload
            )
            
            print(f"📡 HTTP Status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"❌ HTTP Error {response.status_code}: {response.text}")
                raise Exception(f"HTTP {response.status_code}: {response.text}")
            
            result = response.json()
            response_text = result.get('response', '')
            print(f"✅ API Response received: {len(response_text)} chars")
            print(f"📄 First 100 chars: {response_text[:100]}")
            
            # Check if the response indicates completion
            if result.get('done') == True and response_text:
                return result
            else:
                print(f"⚠️ Incomplete response: done={result.get('done')}")
                return result
            
        except Exception as e:
            print(f"❌ API call failed: {str(e)}")
            raise
    
    def _parse_vision_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse vision model response into structured data."""
        try:
            # Extract JSON from response
            response_text = response.get('response', '{}')
            print(f"📄 Raw response: {response_text[:200]}...")
            
            # Sometimes the model returns text before/after JSON, try to extract just the JSON
            response_text = response_text.strip()
            
            # Try to find JSON block if wrapped in other text
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_text = response_text[start_idx:end_idx]
            else:
                json_text = response_text
            
            print(f"🔍 Parsing JSON: {json_text[:100]}...")
            vision_data = json.loads(json_text)
            
            # Validate and clean data
            if not isinstance(vision_data, dict):
                vision_data = {}
                
            if 'elements' not in vision_data:
                vision_data['elements'] = []
            if 'fields' not in vision_data:
                vision_data['fields'] = []
            if 'affordances' not in vision_data:
                vision_data['affordances'] = []
            if 'caption' not in vision_data:
                vision_data['caption'] = 'UI screenshot analysis'
                
            # Validate elements structure
            valid_elements = []
            for elem in vision_data.get('elements', []):
                if isinstance(elem, dict):
                    # Set defaults for missing fields
                    elem.setdefault('role', 'other')
                    elem.setdefault('visible_text', '')
                    elem.setdefault('attributes', {})
                    elem.setdefault('selector_hint', '')
                    elem.setdefault('bbox', [0, 0, 0, 0])
                    elem.setdefault('confidence', 0.5)
                    valid_elements.append(elem)
            vision_data['elements'] = valid_elements
                
            print(f"✅ Parsed successfully: {len(vision_data['elements'])} elements, {len(vision_data['fields'])} fields")
            return vision_data
            
        except (json.JSONDecodeError, KeyError) as e:
            print(f"❌ Failed to parse vision response: {e}")
            print(f"📄 Response was: {response_text[:500]}")
            return {
                'caption': 'Vision analysis parsing failed',
                'elements': [],
                'fields': [],
                'affordances': []
            }
    
    def _fallback_vision_state(self, page_url: str, page_title: str) -> VisionState:
        """Return minimal fallback vision state when analysis fails."""
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
    
    async def _hash_screenshot(self, screenshot_path: str) -> str:
        """Generate hash of screenshot for caching."""
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
        """
        Determine if intent can be handled with local heuristics.
        
        Args:
            intent: User's intended action
            vision_state: Current page vision state
            
        Returns:
            True if can handle locally, False if needs cloud planning
        """
        # Parse intent to extract action type
        action_type = self._extract_action_type(intent)
        
        if action_type not in self.SIMPLE_ACTIONS:
            return False
        
        # For simple actions, check if we have unambiguous target
        if action_type in ['click', 'type']:
            return self._has_unambiguous_target(intent, vision_state)
        
        # Scroll and navigate are usually safe to handle locally
        if action_type in ['scroll', 'navigate', 'wait']:
            return True
            
        return False
    
    def _extract_action_type(self, intent: str) -> str:
        """Extract primary action type from intent description."""
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
        """Check if intent has single high-confidence target in vision state."""
        # Look for text mentions in intent
        intent_words = set(intent.lower().split())
        
        # Check elements and affordances for matches
        candidates = []
        
        for element in vision_state.elements:
            if element.confidence < self.CONFIDENCE_THRESHOLD:
                continue
            element_words = set(element.visible_text.lower().split())
            if intent_words & element_words:  # Word overlap
                candidates.append(element)
        
        for affordance in vision_state.affordances:
            affordance_words = set(affordance.label.lower().split())
            if intent_words & affordance_words:
                candidates.append(affordance)
        
        # Return True only if exactly one high-confidence match
        return len(candidates) == 1
    
    def _extract_action_type(self, intent: str) -> str:
        """Extract action type from intent string."""
        intent_lower = intent.lower()
        
        # Check for click-related keywords
        if any(keyword in intent_lower for keyword in ['click', 'press', 'tap', 'select', 'choose']):
            return 'click'
        
        # Check for type-related keywords
        if any(keyword in intent_lower for keyword in ['type', 'enter', 'fill', 'input', 'write']):
            return 'type'
        
        # Check for scroll-related keywords
        if any(keyword in intent_lower for keyword in ['scroll', 'page down', 'page up']):
            return 'scroll'
        
        # Check for navigation-related keywords
        if any(keyword in intent_lower for keyword in ['go to', 'navigate', 'visit', 'open']):
            return 'navigate'
        
        # Check for wait-related keywords
        if any(keyword in intent_lower for keyword in ['wait', 'pause', 'delay']):
            return 'wait'
        
        # Default to click for ambiguous cases
        return 'click'

# ----------------------------
# Cloud Planner Client
# ----------------------------

class CloudPlannerClient:
    """Client for cloud-based planning using Gemini 2.0 Flash."""
    
    def __init__(self, model_name: str = "gemini-2.0-flash-exp"):
        """Initialize cloud planner client."""
        self.model_name = model_name
        self.llm = ChatGoogle(model=model_name)
    
    async def get_plan(self, request: PlannerRequest) -> PlannerResponse:
        """
        Get action plan from cloud planner.
        
        Args:
            request: Planner request with task, history, and vision state
            
        Returns:
            PlannerResponse with action plan
        """
        try:
            # Build structured prompt
            prompt = self._build_planner_prompt(request)
            
            # Call cloud model with structured output
            response = await self.llm.structured_output(
                messages=[{"role": "user", "content": prompt}],
                output_format=PlannerResponse
            )
            
            return response
            
        except Exception as e:
            print(f"Cloud planning failed: {e}")
            # Return fallback plan
            return PlannerResponse(
                plan=[],
                reasoning_summary=f"Planning failed: {str(e)}",
                needs_more_context=True
            )
    
    def _build_planner_prompt(self, request: PlannerRequest) -> str:
        """Build prompt for cloud planner."""
        prompt = f"""You are a web automation planner. Analyze the current page state and create a detailed action plan.

TASK: {request.task}

CURRENT PAGE STATE:
URL: {request.vision.meta.url}
Title: {request.vision.meta.title}
Description: {request.vision.caption}

AVAILABLE ELEMENTS:
"""
        
        # Add elements information
        for i, elem in enumerate(request.vision.elements[:10]):  # Limit to avoid token overflow
            prompt += f"- {elem.role}: '{elem.visible_text}' (selector: {elem.selector_hint})\n"
        
        # Add affordances
        if request.vision.affordances:
            prompt += "\nINTERACTIVE ELEMENTS:\n"
            for afford in request.vision.affordances[:10]:
                prompt += f"- {afford.type}: '{afford.label}' (selector: {afford.selector_hint})\n"
        
        # Add form fields
        if request.vision.fields:
            prompt += "\nFORM FIELDS:\n"
            for field in request.vision.fields[:10]:
                prompt += f"- {field.name_hint}: current='{field.value_hint}' (editable: {field.editable})\n"
        
        # Add history context
        if request.history:
            prompt += f"\nRECENT HISTORY:\n"
            for step in request.history[-5:]:  # Last 5 steps
                prompt += f"- {step.action} → {step.result}: {step.summary}\n"
        
        prompt += f"""
CONSTRAINTS: {request.constraints}

Create a plan with 3-5 specific actions. Each action should:
1. Be immediately executable 
2. Have clear target selectors
3. Move toward the goal
4. Handle likely failure cases

Return as structured JSON following the PlannerResponse schema."""
        
        return prompt

# ----------------------------
# Handoff Manager  
# ----------------------------

class HandoffManager:
    """Manages routing between local and cloud execution with failure handling."""
    
    def __init__(self, confidence_threshold: float = 0.75, failure_threshold: int = 2):
        """
        Initialize handoff manager.
        
        Args:
            confidence_threshold: Minimum confidence for local execution
            failure_threshold: Consecutive failures before cloud escalation
        """
        self.confidence_threshold = confidence_threshold
        self.failure_threshold = failure_threshold
        self.consecutive_local_failures = 0
        self.history: List[HistoryStep] = []
    
    def should_use_local(self, intent: str, vision_state: VisionState, local_heuristics: LocalActionHeuristics) -> bool:
        """
        Determine if intent should be handled locally or escalated to cloud.
        
        Args:
            intent: User's intended action
            vision_state: Current page vision state
            local_heuristics: Local action decision engine
            
        Returns:
            True if should handle locally, False if should use cloud
        """
        # Force cloud escalation after repeated local failures
        if self.consecutive_local_failures >= self.failure_threshold:
            return False
        
        # Check if vision state has low confidence elements
        if vision_state.elements:
            avg_confidence = sum(elem.confidence for elem in vision_state.elements) / len(vision_state.elements)
            if avg_confidence < self.confidence_threshold:
                return False
        
        # Use local heuristics to determine capability
        return local_heuristics.can_handle_locally(intent, vision_state)
    
    def record_local_result(self, action: str, success: bool, summary: str):
        """Record result of local action execution."""
        result = "ok" if success else "fail"
        
        self.history.append(HistoryStep(
            action=action,
            result=result, 
            summary=summary
        ))
        
        if success:
            self.consecutive_local_failures = 0
        else:
            self.consecutive_local_failures += 1
    
    def record_cloud_result(self, action: str, success: bool, summary: str):
        """Record result of cloud action execution."""
        result = "ok" if success else "fail"
        
        self.history.append(HistoryStep(
            action=action,
            result=result,
            summary=summary
        ))
        
        # Reset local failure count after cloud execution
        self.consecutive_local_failures = 0
    
    def get_recent_history(self, max_steps: int = 5) -> List[HistoryStep]:
        """Get recent execution history for context."""
        return self.history[-max_steps:] if self.history else []
    
    def classify_failure(self, error_message: str) -> str:
        """
        Classify failure type for appropriate escalation strategy.
        
        Args:
            error_message: Error message from failed action
            
        Returns:
            Failure classification string
        """
        error_lower = error_message.lower()
        
        if any(keyword in error_lower for keyword in ['not found', 'no such element', 'selector']):
            return "element_not_found"
        elif any(keyword in error_lower for keyword in ['timeout', 'load']):
            return "page_load_timeout" 
        elif any(keyword in error_lower for keyword in ['click', 'interaction', 'element not clickable']):
            return "interaction_failed"
        elif any(keyword in error_lower for keyword in ['navigation', 'unexpected page', 'wrong page']):
            return "unexpected_page"
        else:
            return "unknown_error"
    
    def should_escalate_immediately(self, failure_type: str) -> bool:
        """Determine if failure type requires immediate cloud escalation."""
        immediate_escalation_types = {
            "element_not_found",
            "unexpected_page"
        }
        return failure_type in immediate_escalation_types

# ----------------------------
# Hybrid Agent Main Class
# ----------------------------

class HybridAgent:
    """Main hybrid agent combining local vision with cloud planning."""
    
    def __init__(self,
                 screenshots_dir: str = "browser_queries/screenshots",
                 vision_cache_size: int = 100,
                 confidence_threshold: float = 0.75,
                 failure_threshold: int = 2):
        """Initialize hybrid agent."""
        self.screenshots_dir = Path(screenshots_dir)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.vision_builder = VisionStateBuilder()
        self.local_heuristics = LocalActionHeuristics()
        self.cloud_planner = CloudPlannerClient()
        self.handoff_manager = HandoffManager(confidence_threshold, failure_threshold)
        
        # State tracking
        self.current_vision_state: Optional[VisionState] = None
        self.consecutive_failures = 0
        
        # Browser session (will be initialized on first use)
        self.browser_session: Optional[BrowserSession] = None
        self.controller: Optional[Controller] = None
    
    async def execute_task(self, task: str) -> Dict[str, Any]:
        """
        Execute a task using hybrid local-vision + cloud-reasoning approach.
        
        Args:
            task: Task description from user
            
        Returns:
            Execution result summary
        """
        print(f"🤖 Starting hybrid task: {task}")
        
        # Initialize browser if needed
        if not self.browser_session:
            await self._initialize_browser()
        
        # Main execution loop
        max_iterations = 20
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            print(f"\n--- Iteration {iteration} ---")
            
            try:
                # Step 1: Capture current state
                vision_state = await self._capture_vision_state()
                self.current_vision_state = vision_state
                
                print(f"📸 Vision: {vision_state.caption}")
                print(f"🎯 Elements: {len(vision_state.elements)}, Fields: {len(vision_state.fields)}, Affordances: {len(vision_state.affordances)}")
                
                # Step 2: Determine if task is complete
                if await self._is_task_complete(task, vision_state):
                    print("✅ Task completed successfully!")
                    break
                
                # Step 3: Decide on next action approach using HandoffManager
                if self.handoff_manager.should_use_local(task, vision_state, self.local_heuristics):
                    print("🔧 Handling locally...")
                    success = await self._execute_local_action(task, vision_state)
                else:
                    print("☁️ Escalating to cloud planner...")  
                    success = await self._execute_cloud_plan(task, vision_state)
                
                # Step 4: Update history and handle failures
                if success:
                    self.consecutive_failures = 0
                else:
                    self.consecutive_failures += 1
                    if self.consecutive_failures >= 3:
                        print("❌ Too many consecutive failures, stopping")
                        break
                
                # Brief pause between iterations
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"❌ Iteration {iteration} failed: {e}")
                self.consecutive_failures += 1
                if self.consecutive_failures >= 3:
                    break
        
        # Return execution summary
        return {
            "task": task,
            "completed": iteration < max_iterations and self.consecutive_failures < 3,
            "iterations": iteration,
            "history_length": len(self.handoff_manager.history),
            "final_url": self.current_vision_state.meta.url if self.current_vision_state else None
        }
    
    async def _initialize_browser(self):
        """Initialize browser session and controller."""
        print("🌐 Initializing browser session...")
        
        # Use browser-use's session management
        self.browser_session = BrowserSession()
        await self.browser_session.start()
        
        # Get controller for the session
        self.controller = self.browser_session.create_controller()
        
        print("✅ Browser initialized")
    
    async def _capture_vision_state(self) -> VisionState:
        """Capture and analyze current page state."""
        if not self.controller:
            raise RuntimeError("Browser not initialized")
        
        # Take screenshot
        timestamp = datetime.now().strftime("%H%M%S")
        screenshot_path = self.screenshots_dir / f"vision_{timestamp}.png"
        
        await self.controller.page.screenshot(path=str(screenshot_path))
        
        # Get page metadata
        page_url = self.controller.page.url
        page_title = await self.controller.page.title()
        
        # Build vision state
        vision_state = await self.vision_builder.build_vision_state(
            str(screenshot_path), page_url, page_title
        )
        
        return vision_state
    
    async def _is_task_complete(self, task: str, vision_state: VisionState) -> bool:
        """Determine if task has been completed."""
        # For now, implement basic heuristics
        # In a full implementation, this could use the cloud model for completion detection
        
        # Check for success indicators in page content
        success_indicators = ['success', 'complete', 'done', 'thank you', 'confirmation']
        page_text = vision_state.caption.lower()
        
        return any(indicator in page_text for indicator in success_indicators)
    
    async def _execute_local_action(self, task: str, vision_state: VisionState) -> bool:
        """Execute simple action using local heuristics."""
        try:
            # Extract action type and target from task
            action_type = self.local_heuristics._extract_action_type(task)
            
            if action_type == 'click':
                return await self._execute_local_click(task, vision_state)
            elif action_type == 'type':
                return await self._execute_local_type(task, vision_state)
            elif action_type == 'scroll':
                return await self._execute_local_scroll(task, vision_state)
            elif action_type == 'navigate':
                return await self._execute_local_navigate(task, vision_state)
            elif action_type == 'wait':
                await asyncio.sleep(2)  # Simple wait
                self.handoff_manager.record_local_result(
                    action="wait_executed",
                    success=True,
                    summary="Waited 2 seconds"
                )
                return True
            else:
                print(f"❌ Unknown local action type: {action_type}")
                return False
                
        except Exception as e:
            print(f"❌ Local action failed: {e}")
            action_type = self.local_heuristics._extract_action_type(task)
            self.handoff_manager.record_local_result(
                action=f"local_{action_type}_failed",
                success=False,
                summary=f"Local action failed: {str(e)}"
            )
            return False
    
    async def _execute_local_click(self, task: str, vision_state: VisionState) -> bool:
        """Execute click action locally."""
        # Find best target from vision state
        target = self._find_click_target(task, vision_state)
        if not target:
            return False
        
        try:
            # Try different click strategies
            success = False
            
            # Strategy 1: Use selector hint if available
            if hasattr(target, 'selector_hint') and target.selector_hint:
                try:
                    await self.controller.page.click(target.selector_hint, timeout=5000)
                    success = True
                    print(f"✅ Clicked using selector: {target.selector_hint}")
                except:
                    pass
            
            # Strategy 2: Click by coordinates if selector failed
            if not success and hasattr(target, 'bbox'):
                try:
                    x, y, w, h = target.bbox
                    center_x, center_y = x + w//2, y + h//2
                    await self.controller.page.mouse.click(center_x, center_y)
                    success = True
                    print(f"✅ Clicked at coordinates: ({center_x}, {center_y})")
                except:
                    pass
            
            # Strategy 3: Try JavaScript click
            if not success and hasattr(target, 'selector_hint'):
                try:
                    await self.controller.page.evaluate(f"""
                        const element = document.querySelector('{target.selector_hint}');
                        if (element) element.click();
                    """)
                    success = True
                    print(f"✅ JS clicked: {target.selector_hint}")
                except:
                    pass
            
            # Update history via HandoffManager
            action_desc = f"click_{getattr(target, 'visible_text', getattr(target, 'label', 'element'))}"
            self.handoff_manager.record_local_result(
                action=action_desc,
                success=success,
                summary=f"Click on {getattr(target, 'visible_text', getattr(target, 'label', 'element'))}"
            )
            
            return success
            
        except Exception as e:
            print(f"❌ Click execution failed: {e}")
            return False
    
    async def _execute_local_type(self, task: str, vision_state: VisionState) -> bool:
        """Execute type action locally."""
        # Extract text to type and find target field
        target, text_to_type = self._find_type_target(task, vision_state)
        if not target or not text_to_type:
            return False
        
        try:
            # Find the input field and type text
            success = False
            
            # Try to focus and type using selector
            if hasattr(target, 'selector_hint') and target.selector_hint:
                try:
                    await self.controller.page.fill(target.selector_hint, text_to_type)
                    success = True
                    print(f"✅ Typed '{text_to_type}' in {target.name_hint}")
                except:
                    # Try alternative approach
                    try:
                        await self.controller.page.click(target.selector_hint)
                        await self.controller.page.keyboard.type(text_to_type)
                        success = True
                        print(f"✅ Typed '{text_to_type}' via keyboard in {target.name_hint}")
                    except:
                        pass
            
            # Update history via HandoffManager
            self.handoff_manager.record_local_result(
                action=f"type_{target.name_hint}",
                success=success,
                summary=f"Typed '{text_to_type}' in {target.name_hint}"
            )
            
            return success
            
        except Exception as e:
            print(f"❌ Type execution failed: {e}")
            return False
    
    async def _execute_local_scroll(self, task: str, vision_state: VisionState) -> bool:
        """Execute scroll action locally."""
        try:
            # Determine scroll direction and amount
            if 'down' in task.lower() or 'page down' in task.lower():
                await self.controller.page.keyboard.press('PageDown')
                direction = "down"
            elif 'up' in task.lower() or 'page up' in task.lower():
                await self.controller.page.keyboard.press('PageUp')
                direction = "up"
            else:
                # Default scroll down
                await self.controller.page.evaluate("window.scrollBy(0, 400)")
                direction = "down"
            
            self.handoff_manager.record_local_result(
                action=f"scroll_{direction}",
                success=True,
                summary=f"Scrolled {direction}"
            )
            
            return True
            
        except Exception as e:
            print(f"❌ Scroll execution failed: {e}")
            return False
    
    async def _execute_local_navigate(self, task: str, vision_state: VisionState) -> bool:
        """Execute navigation action locally."""
        try:
            # Extract URL from task
            url = self._extract_url_from_task(task)
            if not url:
                return False
            
            await self.controller.page.goto(url, timeout=15000)
            await self.controller.page.wait_for_load_state('networkidle', timeout=10000)
            
            self.handoff_manager.record_local_result(
                action=f"navigate_to_{url}",
                success=True,
                summary=f"Navigated to {url}"
            )
            
            return True
            
        except Exception as e:
            print(f"❌ Navigation failed: {e}")
            return False
    
    def _find_click_target(self, task: str, vision_state: VisionState):
        """Find best click target from vision state."""
        task_words = set(task.lower().split())
        
        # Check affordances first (buttons, links, etc.)
        for affordance in vision_state.affordances:
            affordance_words = set(affordance.label.lower().split())
            if task_words & affordance_words:  # Word overlap
                return affordance
        
        # Check elements as fallback
        for element in vision_state.elements:
            if element.confidence < self.local_heuristics.CONFIDENCE_THRESHOLD:
                continue
            element_words = set(element.visible_text.lower().split())
            if task_words & element_words:
                return element
        
        return None
    
    def _find_type_target(self, task: str, vision_state: VisionState):
        """Find type target and extract text to type."""
        # Simple extraction - look for quoted text or after "type" keyword
        text_to_type = None
        
        # Look for quoted strings
        import re
        quotes = re.findall(r'"([^"]*)"', task) or re.findall(r"'([^']*)'", task)
        if quotes:
            text_to_type = quotes[0]
        else:
            # Look for text after "type" keyword
            words = task.split()
            type_idx = -1
            for i, word in enumerate(words):
                if word.lower() in ['type', 'enter', 'input', 'fill']:
                    type_idx = i
                    break
            if type_idx != -1 and type_idx + 1 < len(words):
                text_to_type = ' '.join(words[type_idx + 1:])
        
        if not text_to_type:
            return None, None
        
        # Find best field target
        task_words = set(task.lower().split())
        
        for field in vision_state.fields:
            if not field.editable:
                continue
            field_words = set(field.name_hint.lower().split())
            if task_words & field_words:  # Word overlap
                return field, text_to_type
        
        # Return first editable field as fallback
        for field in vision_state.fields:
            if field.editable:
                return field, text_to_type
        
        return None, None
    
    def _extract_url_from_task(self, task: str) -> Optional[str]:
        """Extract URL from navigation task."""
        import re
        
        # Look for URLs in the task
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, task)
        if urls:
            return urls[0]
        
        # Look for common domain patterns
        domain_pattern = r'(?:go to|visit|navigate to)\s+([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        domains = re.findall(domain_pattern, task, re.IGNORECASE)
        if domains:
            domain = domains[0]
            if not domain.startswith('http'):
                return f'https://{domain}'
            return domain
        
        return None
    
    async def _execute_cloud_plan(self, task: str, vision_state: VisionState) -> bool:
        """Execute action plan from cloud planner."""
        # Build planner request
        request = PlannerRequest(
            task=task,
            history=self.handoff_manager.get_recent_history(5),  # Last 5 steps for context
            vision=vision_state,
            constraints={"max_actions": 5}
        )
        
        # Get plan from cloud
        response = await self.cloud_planner.get_plan(request)
        
        print(f"📋 Cloud plan: {len(response.plan)} actions")
        print(f"🧠 Reasoning: {response.reasoning_summary}")
        
        if response.needs_more_context:
            print("⚠️ Cloud planner needs more context")
            return False
        
        # Execute plan actions sequentially
        success_count = 0
        for i, action in enumerate(response.plan):
            print(f"  Action {i+1}: {action.op} on {action.target}")
            
            try:
                success = await self._execute_single_action(action)
                if success:
                    success_count += 1
                    print(f"    ✅ Action {i+1} completed")
                else:
                    print(f"    ❌ Action {i+1} failed")
                    # Continue with remaining actions even if one fails
                
                # Brief pause between actions
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"    ❌ Action {i+1} error: {e}")
                # Continue with remaining actions
        
        # Update history via HandoffManager
        self.handoff_manager.record_cloud_result(
            action=f"cloud_plan_executed",
            success=success_count > 0,
            summary=f"Executed {success_count}/{len(response.plan)} actions from cloud plan"
        )
        
        return success_count > 0
    
    async def _execute_single_action(self, action: Action) -> bool:
        """Execute a single action from cloud plan."""
        try:
            if action.op == 'click':
                return await self._execute_action_click(action)
            elif action.op == 'type':
                return await self._execute_action_type(action)
            elif action.op == 'scroll':
                return await self._execute_action_scroll(action)
            elif action.op == 'navigate':
                return await self._execute_action_navigate(action)
            elif action.op == 'wait':
                wait_time = float(action.value) if action.value else 2.0
                await asyncio.sleep(wait_time)
                return True
            elif action.op == 'select':
                return await self._execute_action_select(action)
            elif action.op == 'hover':
                return await self._execute_action_hover(action)
            else:
                print(f"❌ Unknown action type: {action.op}")
                return False
                
        except Exception as e:
            print(f"❌ Action execution failed: {e}")
            return False
    
    async def _execute_action_click(self, action: Action) -> bool:
        """Execute click action from cloud plan."""
        try:
            selector_hint = action.target.get('selector_hint')
            text_hint = action.target.get('text')
            
            if selector_hint:
                try:
                    await self.controller.page.click(selector_hint, timeout=5000)
                    return True
                except:
                    # Try JavaScript click as fallback
                    try:
                        await self.controller.page.evaluate(f"""
                            const element = document.querySelector('{selector_hint}');
                            if (element) element.click();
                        """)
                        return True
                    except:
                        pass
            
            # If selector failed, try text-based selection
            if text_hint:
                try:
                    await self.controller.page.click(f"text={text_hint}", timeout=5000)
                    return True
                except:
                    pass
            
            return False
            
        except Exception as e:
            print(f"❌ Click action failed: {e}")
            return False
    
    async def _execute_action_type(self, action: Action) -> bool:
        """Execute type action from cloud plan."""
        try:
            selector_hint = action.target.get('selector_hint')
            value = action.value or ""
            
            if selector_hint:
                try:
                    await self.controller.page.fill(selector_hint, value)
                    return True
                except:
                    # Try alternative approach
                    try:
                        await self.controller.page.click(selector_hint)
                        await self.controller.page.keyboard.press('Control+a')  # Select all
                        await self.controller.page.keyboard.type(value)
                        return True
                    except:
                        pass
            
            return False
            
        except Exception as e:
            print(f"❌ Type action failed: {e}")
            return False
    
    async def _execute_action_scroll(self, action: Action) -> bool:
        """Execute scroll action from cloud plan."""
        try:
            # Parse scroll direction and amount from value or notes
            direction = "down"  # default
            amount = 400  # default pixels
            
            if action.value:
                if "up" in action.value.lower():
                    direction = "up"
                    amount = -400
                elif "down" in action.value.lower():
                    direction = "down"
                    amount = 400
            
            # Execute scroll
            await self.controller.page.evaluate(f"window.scrollBy(0, {amount})")
            return True
            
        except Exception as e:
            print(f"❌ Scroll action failed: {e}")
            return False
    
    async def _execute_action_navigate(self, action: Action) -> bool:
        """Execute navigate action from cloud plan."""
        try:
            url = action.value
            if not url:
                return False
            
            # Add protocol if missing
            if not url.startswith(('http://', 'https://')):
                url = f'https://{url}'
            
            await self.controller.page.goto(url, timeout=15000)
            await self.controller.page.wait_for_load_state('networkidle', timeout=10000)
            return True
            
        except Exception as e:
            print(f"❌ Navigate action failed: {e}")
            return False
    
    async def _execute_action_select(self, action: Action) -> bool:
        """Execute select action from cloud plan."""
        try:
            selector_hint = action.target.get('selector_hint')
            value = action.value
            
            if selector_hint and value:
                await self.controller.page.select_option(selector_hint, value)
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Select action failed: {e}")
            return False
    
    async def _execute_action_hover(self, action: Action) -> bool:
        """Execute hover action from cloud plan."""
        try:
            selector_hint = action.target.get('selector_hint')
            
            if selector_hint:
                await self.controller.page.hover(selector_hint)
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Hover action failed: {e}")
            return False

# ----------------------------
# CLI Interface (from agent.py)  
# ----------------------------

async def main():
    """Main CLI interface."""
    print("🤖 Hybrid Local-Vision + Cloud-Reasoning Agent")
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
            if result['final_url']:
                print(f"Final URL: {result['final_url']}")
            print("=" * 50)
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())