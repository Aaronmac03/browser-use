"""
Basic example demonstrating the hybrid local-vision + cloud-reasoning system.

This example shows how to:
1. Set up the hybrid components
2. Process screenshots with local vision
3. Handle simple actions locally
4. Escalate to cloud when needed
"""

import asyncio
import os
import sys
from pathlib import Path
import logging

# Add browser-use to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from browser_use import Agent, BrowserSession 
from browser_use.browser.profile import BrowserProfile

# Import our hybrid components
from vision_state_builder import VisionStateBuilder
from local_action_heuristics import LocalActionHeuristics
from cloud_planner_client import CloudPlannerClient
from handoff_manager import HandoffManager

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class HybridAgent:
    """
    Hybrid agent combining local vision processing with cloud reasoning.
    
    This demonstrates the architecture described in the hybrid brief.
    """
    
    def __init__(
        self,
        google_api_key: str,
        ollama_url: str = "http://localhost:11434",
        minicpm_model: str = "minicpm-v:2.6"
    ):
        self.google_api_key = google_api_key
        
        # Initialize components
        self.vision_builder = VisionStateBuilder(
            ollama_base_url=ollama_url,
            model_name=minicpm_model,
            confidence_threshold=0.7
        )
        
        self.local_heuristics = LocalActionHeuristics(
            confidence_threshold=0.8,
            similarity_threshold=0.8
        )
        
        self.cloud_client = CloudPlannerClient(
            api_key=google_api_key,
            model_name="gemini-2.0-flash-exp"
        )
        
        self.handoff_manager = HandoffManager(
            vision_builder=self.vision_builder,
            local_heuristics=self.local_heuristics,
            cloud_client=self.cloud_client
        )
        
        self.browser_session = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.vision_builder.__aenter__()
        
        # Start browser session
        profile = BrowserProfile(headless=False, user_data_dir=None)
        self.browser_session = BrowserSession(browser_profile=profile)
        await self.browser_session.start()
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.browser_session:
            await self.browser_session.stop()
        await self.vision_builder.__aexit__(exc_type, exc_val, exc_tb)
    
    async def run_task(self, task_description: str, max_steps: int = 10) -> dict:
        """
        Run a task using the hybrid approach.
        
        Args:
            task_description: Natural language description of the task
            max_steps: Maximum number of steps to execute
            
        Returns:
            dict with task results and statistics
        """
        
        logger.info(f"Starting hybrid task: {task_description}")
        
        stats = {
            "total_steps": 0,
            "local_actions": 0,
            "cloud_actions": 0,
            "failures": 0,
            "task": task_description
        }
        
        current_intent = task_description
        
        for step in range(max_steps):
            logger.info(f"\n--- Step {step + 1}/{max_steps} ---")
            logger.info(f"Intent: {current_intent}")
            
            try:
                # Get current page info
                page_info = await self._get_current_page_info()
                if not page_info:
                    logger.error("Could not get page information")
                    break
                
                # Take screenshot
                screenshot_data = await self._take_screenshot()
                if not screenshot_data:
                    logger.error("Could not take screenshot")
                    break
                
                # Process intent and get next action
                action, reasoning, used_cloud = await self.handoff_manager.process_intent(
                    current_intent,
                    screenshot_data,
                    page_info["url"],
                    page_info["title"],
                    page_info["viewport"],
                    page_info["scroll_y"]
                )
                
                logger.info(f"Reasoning: {reasoning}")
                logger.info(f"Action: {action.op}" + (f" on {action.target.selector_hint}" if action.target else ""))
                
                # Execute the action
                result = await self._execute_action(action)
                
                # Record result
                self.handoff_manager.record_action_result(action, result["status"], result["message"])
                
                # Update stats
                stats["total_steps"] += 1
                if used_cloud:
                    stats["cloud_actions"] += 1
                else:
                    stats["local_actions"] += 1
                    
                if result["status"] != "ok":
                    stats["failures"] += 1
                
                # Check if task is complete
                if result["status"] == "ok" and ("done" in result["message"].lower() or "complete" in result["message"].lower()):
                    logger.info("Task appears to be complete")
                    break
                
                # For this demo, we'll break after each action to avoid runaway loops
                # In a real implementation, you'd have better completion detection
                if step > 0:  # Allow at least 2 actions
                    user_continue = input("\nContinue to next step? (y/n): ").strip().lower()
                    if user_continue != 'y':
                        break
                
            except Exception as e:
                logger.error(f"Error in step {step + 1}: {e}")
                stats["failures"] += 1
        
        # Get final state summary
        final_state = self.handoff_manager.get_current_state_summary()
        stats["final_state"] = final_state
        
        logger.info(f"\nTask completed. Stats: {stats}")
        return stats
    
    async def _get_current_page_info(self) -> dict:
        """Get current page information"""
        try:
            page = self.browser_session.context.pages[0]  # Assuming single page
            
            return {
                "url": page.url,
                "title": await page.title(),
                "viewport": page.viewport_size,
                "scroll_y": await page.evaluate("window.pageYOffset")
            }
        except Exception as e:
            logger.error(f"Error getting page info: {e}")
            return None
    
    async def _take_screenshot(self) -> bytes:
        """Take screenshot of current page"""
        try:
            page = self.browser_session.context.pages[0]
            screenshot_data = await page.screenshot(type="png", full_page=False)
            return screenshot_data
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            return None
    
    async def _execute_action(self, action) -> dict:
        """Execute an action and return result"""
        try:
            page = self.browser_session.context.pages[0]
            
            if action.op == "navigate":
                await page.goto(action.value)
                return {"status": "ok", "message": f"Navigated to {action.value}"}
            
            elif action.op == "click":
                if action.target and action.target.selector_hint:
                    # Simple selector interpretation for demo
                    selector = self._convert_selector_hint(action.target.selector_hint)
                    await page.click(selector, timeout=5000)
                    return {"status": "ok", "message": f"Clicked {selector}"}
                else:
                    return {"status": "fail", "message": "No target specified for click"}
            
            elif action.op == "type":
                if action.target and action.target.selector_hint and action.value:
                    selector = self._convert_selector_hint(action.target.selector_hint)
                    await page.fill(selector, action.value)
                    return {"status": "ok", "message": f"Typed '{action.value}' into {selector}"}
                else:
                    return {"status": "fail", "message": "Missing target or value for type action"}
            
            elif action.op == "scroll":
                if action.value == "down":
                    await page.keyboard.press("Page_Down")
                elif action.value == "up":
                    await page.keyboard.press("Page_Up")
                else:
                    await page.evaluate(f"window.scrollBy(0, {action.value or 500})")
                return {"status": "ok", "message": f"Scrolled {action.value or 'down'}"}
            
            elif action.op == "wait":
                wait_ms = int(action.value or 1000)
                await asyncio.sleep(wait_ms / 1000)
                return {"status": "ok", "message": f"Waited {wait_ms}ms"}
            
            else:
                return {"status": "fail", "message": f"Unsupported action: {action.op}"}
        
        except Exception as e:
            logger.error(f"Error executing action {action.op}: {e}")
            return {"status": "fail", "message": f"Execution error: {str(e)}"}
    
    def _convert_selector_hint(self, selector_hint: str) -> str:
        """Convert selector hint to actual CSS selector"""
        
        # Simple conversions for demo - in real implementation this would be more sophisticated
        if ":contains(" in selector_hint:
            # Convert "button:contains('text')" to approximate CSS
            parts = selector_hint.split(":contains(")
            element_type = parts[0]
            text_part = parts[1].rstrip(")")
            text = text_part.strip("'\"")
            return f"{element_type}:has-text('{text}')"
        
        elif "[aria-label=" in selector_hint:
            return selector_hint
        
        elif " near " in selector_hint:
            # For demo, just use the first part
            return selector_hint.split(" near ")[0]
        
        else:
            # Return as-is for other cases
            return selector_hint


async def main():
    """Main example demonstrating hybrid system"""
    
    # Check for required API key
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        print("Please set GOOGLE_API_KEY environment variable")
        return
    
    # Task examples
    tasks = [
        "Navigate to google.com",
        "Search for 'browser automation'",
        "Click on the first search result",
    ]
    
    print("Hybrid Local-Vision + Cloud-Reasoning Demo")
    print("=" * 50)
    print("This demo requires:")
    print("1. Ollama running locally with minicpm-v:2.6 model")
    print("2. GOOGLE_API_KEY environment variable set")
    print("3. Browser automation will be visible (headless=False)")
    print()
    
    # Let user choose a task
    print("Available tasks:")
    for i, task in enumerate(tasks, 1):
        print(f"{i}. {task}")
    
    try:
        choice = int(input(f"Choose a task (1-{len(tasks)}): ")) - 1
        if 0 <= choice < len(tasks):
            selected_task = tasks[choice]
        else:
            print("Invalid choice, using first task")
            selected_task = tasks[0]
    except ValueError:
        print("Invalid input, using first task")
        selected_task = tasks[0]
    
    # Run the hybrid agent
    try:
        async with HybridAgent(google_api_key) as hybrid_agent:
            results = await hybrid_agent.run_task(selected_task, max_steps=5)
            
            print("\nTask Results:")
            print(f"- Total steps: {results['total_steps']}")
            print(f"- Local actions: {results['local_actions']}")
            print(f"- Cloud actions: {results['cloud_actions']}")
            print(f"- Failures: {results['failures']}")
            
    except KeyboardInterrupt:
        print("\nTask interrupted by user")
    except Exception as e:
        print(f"Error running task: {e}")


if __name__ == "__main__":
    asyncio.run(main())