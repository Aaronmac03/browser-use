#!/usr/bin/env python3
"""
Improved Hybrid Agent with Multi-Tier Vision System
Integrates the new reliable vision architecture with the existing hybrid agent
"""

import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# Configure logging early
import logging
import sys
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
    force=True
)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv(override=True)

# Browser-Use imports
from browser_use import Agent, Controller
from browser_use.browser import BrowserProfile, BrowserSession
from browser_use.llm import ChatOpenAI
import openai

# Import our new vision components
from multi_tier_vision import MultiTierVisionSystem, VisionRequest, VisionTier
from vision_service_manager import VisionServiceManager
from enhanced_dom_analyzer import EnhancedDOMAnalyzer

# Import existing components
from vision_module import VisionState
from serper_search import search_with_serper_fallback

# Configuration
CHROME_PROFILE_DIR = 'C:/Users/drmcn/.config/browseruse/profiles/default'
LOGS_DIR = Path('improved_hybrid_queries')
LOGS_DIR.mkdir(exist_ok=True)

# Terminal colors
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


class ImprovedHybridAgent:
    """Improved hybrid agent with multi-tier vision system"""
    
    def __init__(self):
        # Initialize vision system
        self.vision_system = MultiTierVisionSystem()
        self.service_manager = VisionServiceManager()
        
        # Initialize browser session
        self.browser_session = None
        self.controller = None
        
        # Initialize LLM client
        self.llm_client = openai.AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Performance tracking
        self.execution_stats = {
            'total_tasks': 0,
            'successful_tasks': 0,
            'vision_calls': 0,
            'vision_failures': 0,
            'avg_task_time': 0.0
        }
    
    async def initialize(self) -> bool:
        """Initialize the agent and all services"""
        print_status("Initializing Improved Hybrid Agent...", Colors.BLUE)
        
        try:
            # Setup vision services
            print_status("Setting up vision services...", Colors.BLUE)
            service_results = await self.service_manager.setup_all_services()
            
            if not service_results.get('ollama', False):
                print_status("Ollama service setup failed, will use DOM-only analysis", Colors.YELLOW)
            
            # Initialize browser session
            print_status("Initializing browser session...", Colors.BLUE)
            profile = BrowserProfile(
                profile_path=CHROME_PROFILE_DIR,
                headless=False,
                disable_security=True
            )
            
            self.browser_session = BrowserSession(profile=profile)
            await self.browser_session.start()
            self.controller = Controller(self.browser_session)
            
            print_status("Agent initialization completed", Colors.GREEN)
            return True
            
        except Exception as e:
            print_status(f"Agent initialization failed: {e}", Colors.RED)
            return False
    
    async def execute_task(self, task: str) -> Dict[str, Any]:
        """Execute a task using the improved hybrid approach"""
        start_time = time.time()
        self.execution_stats['total_tasks'] += 1
        
        print_status(f"Executing task: {task}", Colors.BLUE)
        
        try:
            # Step 1: Plan the task
            plan = await self._create_task_plan(task)
            print_status(f"Created plan with {len(plan.get('steps', []))} steps", Colors.GREEN)
            
            # Step 2: Execute the plan
            execution_result = await self._execute_plan(plan, task)
            
            # Step 3: Generate summary
            execution_time = time.time() - start_time
            
            result = {
                'task': task,
                'completed': execution_result.get('success', False),
                'steps_executed': execution_result.get('steps_executed', 0),
                'execution_time': execution_time,
                'vision_system_stats': self.vision_system.get_performance_summary(),
                'final_url': execution_result.get('final_url', ''),
                'summary': execution_result.get('summary', ''),
                'errors': execution_result.get('errors', [])
            }
            
            if result['completed']:
                self.execution_stats['successful_tasks'] += 1
            
            # Update average task time
            total_tasks = self.execution_stats['total_tasks']
            current_avg = self.execution_stats['avg_task_time']
            self.execution_stats['avg_task_time'] = (
                (current_avg * (total_tasks - 1) + execution_time) / total_tasks
            )
            
            # Save execution log
            await self._save_execution_log(task, result)
            
            return result
            
        except Exception as e:
            print_status(f"Task execution failed: {e}", Colors.RED)
            return {
                'task': task,
                'completed': False,
                'execution_time': time.time() - start_time,
                'error': str(e)
            }
    
    async def _create_task_plan(self, task: str) -> Dict[str, Any]:
        """Create a plan for the task using LLM"""
        try:
            prompt = f"""
            Create a step-by-step plan to accomplish this task: {task}
            
            Return a JSON object with this structure:
            {{
                "normalized_task": "clear description of what to accomplish",
                "steps": [
                    {{
                        "action": "navigate|search|click|type|extract|analyze",
                        "target": "description of what to target",
                        "value": "value to input if applicable",
                        "notes": "additional context"
                    }}
                ],
                "success_criteria": ["criteria to determine if task is complete"],
                "estimated_complexity": "simple|medium|complex"
            }}
            
            Keep plans concise but complete. Focus on observable actions.
            """
            
            response = await self.llm_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.1
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            if response_text.startswith('```'):
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)
            
            plan = json.loads(response_text)
            return plan
            
        except Exception as e:
            print_status(f"Plan creation failed: {e}", Colors.RED)
            # Return fallback plan
            return {
                "normalized_task": task,
                "steps": [
                    {"action": "analyze", "target": "current page", "value": "", "notes": "analyze current state"},
                    {"action": "search", "target": "web", "value": task, "notes": "search for information"}
                ],
                "success_criteria": ["relevant information found"],
                "estimated_complexity": "medium"
            }
    
    async def _execute_plan(self, plan: Dict[str, Any], original_task: str) -> Dict[str, Any]:
        """Execute the plan using multi-tier vision system"""
        steps_executed = 0
        errors = []
        
        try:
            for i, step in enumerate(plan.get('steps', [])):
                print_status(f"Executing step {i+1}: {step['action']} - {step['target']}", Colors.BLUE)
                
                try:
                    # Get current page state using vision system
                    vision_state = await self._analyze_current_page()
                    
                    # Execute the step
                    step_result = await self._execute_step(step, vision_state)
                    
                    steps_executed += 1
                    
                    if not step_result.get('success', False):
                        error_msg = f"Step {i+1} failed: {step_result.get('error', 'unknown error')}"
                        errors.append(error_msg)
                        print_status(error_msg, Colors.YELLOW)
                        
                        # Try to recover or continue
                        if len(errors) >= 3:
                            print_status("Too many errors, stopping execution", Colors.RED)
                            break
                    
                    # Brief pause between steps
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    error_msg = f"Step {i+1} exception: {str(e)}"
                    errors.append(error_msg)
                    print_status(error_msg, Colors.RED)
                    
                    if len(errors) >= 3:
                        break
            
            # Get final state
            final_vision_state = await self._analyze_current_page()
            final_url = self.controller.page.url if self.controller and self.controller.page else ""
            
            # Generate summary
            summary = await self._generate_execution_summary(original_task, plan, steps_executed, errors, final_vision_state)
            
            return {
                'success': len(errors) < 3 and steps_executed > 0,
                'steps_executed': steps_executed,
                'final_url': final_url,
                'summary': summary,
                'errors': errors
            }
            
        except Exception as e:
            return {
                'success': False,
                'steps_executed': steps_executed,
                'summary': f"Execution failed: {str(e)}",
                'errors': errors + [str(e)]
            }
    
    async def _analyze_current_page(self) -> Optional[VisionState]:
        """Analyze current page using multi-tier vision system"""
        try:
            if not self.controller or not self.controller.page:
                return None
            
            self.execution_stats['vision_calls'] += 1
            
            # Get page info
            page_url = self.controller.page.url
            page_title = await self.controller.page.title()
            
            # Take screenshot for advanced analysis
            screenshot_path = None
            try:
                screenshot_path = f"temp_screenshot_{int(time.time())}.png"
                await self.controller.page.screenshot(path=screenshot_path)
            except Exception as e:
                print_status(f"Screenshot failed: {e}", Colors.YELLOW)
            
            # Create vision request
            request = VisionRequest(
                page_url=page_url,
                page_title=page_title,
                screenshot_path=screenshot_path,
                required_accuracy=0.7,
                max_response_time=5.0
            )
            
            # Analyze with multi-tier system
            response = await self.vision_system.analyze(request, self.controller.page)
            
            print_status(f"Vision analysis: {response.tier_used.value} in {response.analysis_time:.2f}s", Colors.GREEN)
            
            # Cleanup screenshot
            if screenshot_path and Path(screenshot_path).exists():
                try:
                    Path(screenshot_path).unlink()
                except:
                    pass
            
            return response.vision_state
            
        except Exception as e:
            self.execution_stats['vision_failures'] += 1
            print_status(f"Vision analysis failed: {e}", Colors.RED)
            return None
    
    async def _execute_step(self, step: Dict[str, Any], vision_state: Optional[VisionState]) -> Dict[str, Any]:
        """Execute a single step"""
        action = step.get('action', '').lower()
        target = step.get('target', '')
        value = step.get('value', '')
        
        try:
            if action == 'navigate':
                if 'http' in target or 'http' in value:
                    url = target if 'http' in target else value
                    await self.controller.page.goto(url)
                    return {'success': True, 'message': f'Navigated to {url}'}
                else:
                    return {'success': False, 'error': 'No valid URL provided'}
            
            elif action == 'search':
                # Use web search
                search_query = value or target
                result = await search_with_serper_fallback(self.controller, search_query, 5)
                return {'success': True, 'message': f'Search completed for: {search_query}'}
            
            elif action == 'click':
                # Find element to click using vision state
                if vision_state:
                    element = self._find_element_by_description(vision_state, target)
                    if element:
                        # Try to click using selector hint
                        try:
                            await self.controller.page.click(element.selector_hint, timeout=5000)
                            return {'success': True, 'message': f'Clicked: {target}'}
                        except Exception as e:
                            # Fallback to coordinate click
                            if element.bbox and len(element.bbox) >= 4:
                                x = element.bbox[0] + element.bbox[2] // 2
                                y = element.bbox[1] + element.bbox[3] // 2
                                await self.controller.page.mouse.click(x, y)
                                return {'success': True, 'message': f'Clicked at coordinates: {x}, {y}'}
                            else:
                                return {'success': False, 'error': f'Could not click element: {e}'}
                    else:
                        return {'success': False, 'error': f'Element not found: {target}'}
                else:
                    return {'success': False, 'error': 'No vision state available for click'}
            
            elif action == 'type':
                # Find input field and type
                if vision_state:
                    field = self._find_field_by_description(vision_state, target)
                    if field:
                        # Find corresponding element
                        element = self._find_element_by_bbox(vision_state, field.bbox)
                        if element:
                            try:
                                await self.controller.page.fill(element.selector_hint, value)
                                return {'success': True, 'message': f'Typed "{value}" in {target}'}
                            except Exception as e:
                                return {'success': False, 'error': f'Could not type in field: {e}'}
                    return {'success': False, 'error': f'Input field not found: {target}'}
                else:
                    return {'success': False, 'error': 'No vision state available for typing'}
            
            elif action == 'extract':
                # Extract information from page
                if vision_state:
                    extracted_info = self._extract_information(vision_state, target)
                    return {'success': True, 'message': f'Extracted: {extracted_info}'}
                else:
                    return {'success': False, 'error': 'No vision state available for extraction'}
            
            elif action == 'analyze':
                # Just analyze current state
                if vision_state:
                    return {'success': True, 'message': f'Page analyzed: {vision_state.caption}'}
                else:
                    return {'success': False, 'error': 'Vision analysis failed'}
            
            else:
                return {'success': False, 'error': f'Unknown action: {action}'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _find_element_by_description(self, vision_state: VisionState, description: str) -> Optional[Any]:
        """Find element by description"""
        description_lower = description.lower()
        
        # Search in elements
        for element in vision_state.elements:
            if (description_lower in element.visible_text.lower() or
                description_lower in element.role.lower()):
                return element
        
        # Search in affordances
        for affordance in vision_state.affordances:
            if (description_lower in affordance.label.lower() or
                description_lower in affordance.type.lower()):
                # Convert affordance to element-like object
                class ElementLike:
                    def __init__(self, affordance):
                        self.selector_hint = affordance.selector_hint
                        self.bbox = affordance.bbox
                        self.visible_text = affordance.label
                return ElementLike(affordance)
        
        return None
    
    def _find_field_by_description(self, vision_state: VisionState, description: str):
        """Find form field by description"""
        description_lower = description.lower()
        
        for field in vision_state.fields:
            if description_lower in field.name_hint.lower():
                return field
        
        return None
    
    def _find_element_by_bbox(self, vision_state: VisionState, bbox: List[int]):
        """Find element by bounding box"""
        for element in vision_state.elements:
            if element.bbox == bbox:
                return element
        return None
    
    def _extract_information(self, vision_state: VisionState, target: str) -> str:
        """Extract information from vision state"""
        extracted = []
        
        if 'price' in target.lower():
            # Look for price-related text
            for element in vision_state.elements:
                if '$' in element.visible_text or 'price' in element.visible_text.lower():
                    extracted.append(element.visible_text)
        
        elif 'text' in target.lower() or 'content' in target.lower():
            # Extract all visible text
            for element in vision_state.elements:
                if element.visible_text.strip():
                    extracted.append(element.visible_text)
        
        return '; '.join(extracted[:10])  # Limit to first 10 items
    
    async def _generate_execution_summary(self, task: str, plan: Dict[str, Any], steps_executed: int, errors: List[str], final_vision_state: Optional[VisionState]) -> str:
        """Generate execution summary"""
        try:
            summary_parts = [
                f"Task: {task}",
                f"Steps executed: {steps_executed}/{len(plan.get('steps', []))}",
                f"Errors: {len(errors)}"
            ]
            
            if final_vision_state:
                summary_parts.append(f"Final page: {final_vision_state.caption}")
            
            if errors:
                summary_parts.append(f"Last error: {errors[-1]}")
            
            return " | ".join(summary_parts)
            
        except Exception as e:
            return f"Summary generation failed: {e}"
    
    async def _save_execution_log(self, task: str, result: Dict[str, Any]):
        """Save execution log"""
        try:
            timestamp = datetime.now()
            date_str = timestamp.strftime("%Y-%m-%d")
            time_str = timestamp.strftime("%H-%M-%S")
            
            daily_dir = LOGS_DIR / date_str
            daily_dir.mkdir(exist_ok=True)
            
            log_file = daily_dir / f"{time_str}_improved_hybrid.json"
            
            log_data = {
                'timestamp': timestamp.isoformat(),
                'task': task,
                'result': result,
                'agent_stats': self.execution_stats,
                'vision_stats': self.vision_system.get_performance_summary()
            }
            
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print_status(f"Failed to save log: {e}", Colors.YELLOW)
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            if self.browser_session:
                await self.browser_session.kill()
        except Exception as e:
            print_status(f"Cleanup error: {e}", Colors.YELLOW)


# Test function
async def test_improved_agent():
    """Test the improved hybrid agent"""
    agent = ImprovedHybridAgent()
    
    try:
        # Initialize agent
        if not await agent.initialize():
            print_status("Agent initialization failed", Colors.RED)
            return
        
        # Test task
        test_task = "search for information about Python programming"
        
        result = await agent.execute_task(test_task)
        
        print("\n" + "="*60)
        print("EXECUTION RESULT")
        print(f"Task: {result.get('task')}")
        print(f"Completed: {result.get('completed')}")
        print(f"Steps Executed: {result.get('steps_executed')}")
        print(f"Execution Time: {result.get('execution_time', 0):.2f}s")
        print(f"Summary: {result.get('summary')}")
        if result.get('errors'):
            print(f"Errors: {result['errors']}")
        print("="*60)
        
    finally:
        await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(test_improved_agent())