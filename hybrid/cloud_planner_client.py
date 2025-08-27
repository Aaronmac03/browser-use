"""
CloudPlannerClient - Interface to Gemini 2.0 Flash for complex planning.

Handles escalation to cloud reasoning when local heuristics are insufficient.
"""

import logging
import json
from typing import List, Optional
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from .schemas import PlannerRequest, PlannerResponse, Action, VisionState

logger = logging.getLogger(__name__)


class CloudPlannerClient:
    """Client for cloud-based planning using Gemini 2.0 Flash"""
    
    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.0-flash-exp",
        max_actions_per_plan: int = 5,
        rate_limit_calls_per_minute: int = 10
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.max_actions_per_plan = max_actions_per_plan
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        # Safety settings - allow discussions of browser automation
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        # Initialize model with function calling enabled
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            safety_settings=safety_settings,
            generation_config={
                "temperature": 0.1,  # Low temperature for consistent planning
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 1024,
            }
        )
        
        # Rate limiting (simple implementation)
        self._call_history: List[float] = []
    
    async def plan_actions(
        self,
        request: PlannerRequest
    ) -> PlannerResponse:
        """
        Get action plan from cloud reasoning.
        
        Args:
            request: PlannerRequest with task, history, and vision state
            
        Returns:
            PlannerResponse with action plan
        """
        
        try:
            # Check rate limiting
            self._check_rate_limit()
            
            # Create the planning prompt
            prompt = self._create_planning_prompt(request)
            
            # Call Gemini with structured output
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "response_schema": self._get_response_schema()
                }
            )
            
            # Parse response 
            response_data = json.loads(response.text)
            
            # Validate and create PlannerResponse
            planner_response = PlannerResponse(
                plan=self._parse_actions(response_data.get('plan', [])),
                reasoning_summary=response_data.get('reasoning_summary', '')[:300],
                needs_more_context=response_data.get('needs_more_context', False)
            )
            
            logger.info(f"Generated plan with {len(planner_response.plan)} actions")
            return planner_response
            
        except Exception as e:
            logger.error(f"Failed to get plan from cloud: {e}")
            # Return fallback response
            return PlannerResponse(
                plan=[],
                reasoning_summary="Cloud planning failed, manual intervention needed",
                needs_more_context=True
            )
    
    def _check_rate_limit(self):
        """Simple rate limiting implementation"""
        import time
        current_time = time.time()
        
        # Remove calls older than 1 minute
        self._call_history = [
            call_time for call_time in self._call_history 
            if current_time - call_time < 60
        ]
        
        if len(self._call_history) >= 10:  # 10 calls per minute limit
            raise Exception("Rate limit exceeded for cloud planning")
        
        self._call_history.append(current_time)
    
    def _create_planning_prompt(self, request: PlannerRequest) -> str:
        """Create the planning prompt for Gemini"""
        
        prompt = f"""
You are a web automation planning assistant. Given a user task, browsing history, and current page state, create a specific action plan.

TASK: {request.task}

CURRENT PAGE STATE:
URL: {request.vision.meta.url}
Title: {request.vision.meta.title}
Caption: {request.vision.caption}

Available Elements ({len(request.vision.elements)} total):
"""
        
        # Add key elements (limit to avoid token overflow)
        for i, element in enumerate(request.vision.elements[:20]):  # Limit to 20 elements
            prompt += f"- {element.role}: '{element.visible_text}' (confidence: {element.confidence:.2f})\n"
        
        prompt += f"\nAvailable Form Fields ({len(request.vision.fields)} total):\n"
        for field in request.vision.fields[:10]:  # Limit to 10 fields
            prompt += f"- {field.name_hint}: current='{field.value_hint}' (editable: {field.editable})\n"
        
        prompt += f"\nInteractive Elements ({len(request.vision.affordances)} total):\n"
        for affordance in request.vision.affordances[:15]:  # Limit to 15 affordances
            prompt += f"- {affordance.type}: '{affordance.label}'\n"
        
        if request.history:
            prompt += f"\nRECENT HISTORY ({len(request.history)} actions):\n"
            for i, hist_item in enumerate(request.history[-5:]):  # Last 5 actions
                prompt += f"{i+1}. {hist_item.action.op}"
                if hist_item.action.target:
                    prompt += f" on '{hist_item.action.target.selector_hint}'"
                if hist_item.action.value:
                    prompt += f" with '{hist_item.action.value}'"
                prompt += f" -> {hist_item.result}: {hist_item.summary}\n"
        
        constraints = request.constraints
        max_actions = constraints.get('max_actions', self.max_actions_per_plan)
        avoid_list = constraints.get('avoid', [])
        
        prompt += f"""
CONSTRAINTS:
- Maximum {max_actions} actions in the plan
- Avoid: {', '.join(avoid_list) if avoid_list else 'None specified'}

Create a JSON response with:
- "plan": Array of action objects with: 
  - "op": One of "click", "type", "scroll", "navigate", "wait", "select", "hover"
  - "target": Object with "selector_hint" and optional "text" 
  - "value": String value for type/navigate actions
  - "notes": Brief explanation of the action
- "reasoning_summary": Brief explanation of your approach (max 300 chars)
- "needs_more_context": Boolean - true if you need more information to proceed

Focus on:
1. Be specific with selector hints (prefer visible text, aria-labels, or position)
2. Break complex tasks into simple sequential actions
3. Handle error cases (e.g., if login is needed but user is already logged in)
4. If multiple options exist, choose the most reliable approach

Example action:
{{"op": "click", "target": {{"selector_hint": "button:contains('Sign In')", "text": "Sign In"}}, "notes": "Click the main sign in button"}}
"""
        
        return prompt
    
    def _get_response_schema(self):
        """Get the JSON schema for structured response"""
        return {
            "type": "object",
            "properties": {
                "plan": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "op": {
                                "type": "string",
                                "enum": ["click", "type", "scroll", "navigate", "wait", "select", "hover"]
                            },
                            "target": {
                                "type": "object",
                                "properties": {
                                    "selector_hint": {"type": "string"},
                                    "text": {"type": "string"}
                                },
                                "required": ["selector_hint"]
                            },
                            "value": {"type": "string"},
                            "notes": {"type": "string"}
                        },
                        "required": ["op"]
                    }
                },
                "reasoning_summary": {"type": "string"},
                "needs_more_context": {"type": "boolean"}
            },
            "required": ["plan", "reasoning_summary", "needs_more_context"]
        }
    
    def _parse_actions(self, plan_data: List[dict]) -> List[Action]:
        """Parse action data into Action objects"""
        actions = []
        
        for action_data in plan_data:
            try:
                # Build target if present
                target = None
                if action_data.get('target'):
                    target_data = action_data['target']
                    target = {
                        'selector_hint': target_data.get('selector_hint', ''),
                        'text': target_data.get('text')
                    }
                
                action = Action(
                    op=action_data['op'],
                    target=target,
                    value=action_data.get('value'),
                    notes=action_data.get('notes')
                )
                actions.append(action)
                
            except Exception as e:
                logger.warning(f"Skipping invalid action: {e}")
        
        return actions