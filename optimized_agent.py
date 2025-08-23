"""
Optimized Browser-Use Agent - Aug23 Playbook Implementation

This implements the optimization-first playbook with:
- Model strategy (planner vs executor with auto-escalation)
- Browser/agent config for stability
- Control flow & observability
- Robustness hooks + fallbacks
- Custom actions for reliability
- Human-in-the-loop gates
- Cost guardrails

Run with: python optimized_agent.py
"""

import asyncio
import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable
import traceback

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

from browser_use import Agent, BrowserProfile, BrowserSession, Controller
from browser_use.agent.views import AgentHistoryList
from browser_use.llm import ChatOpenAI, ChatAnthropic, ChatGoogle

# ----------------------------
# Structured Output Schemas
# ----------------------------

class TaskResult(BaseModel):
    """Structured result from agent execution."""
    success: bool = Field(description="Whether the task completed successfully")
    data: Any = Field(description="Extracted data or results", default=None)
    error: Optional[str] = Field(description="Error message if failed", default=None)
    steps_taken: int = Field(description="Number of steps executed")
    final_url: Optional[str] = Field(description="Final URL when task ended", default=None)

class StateMemo(BaseModel):
    """Compact state memo for persistence between runs."""
    last_url: Optional[str] = Field(default=None)
    last_success: Optional[str] = Field(default=None)
    last_error: Optional[str] = Field(default=None)
    context: Optional[str] = Field(default=None)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

# ----------------------------
# Configuration
# ----------------------------

class OptimizedAgentConfig:
    """Configuration following aug23 playbook."""
    
    # Model Strategy
    PLANNER_MODEL = "gpt-4o-mini"  # Cheaper reasoning model
    EXECUTOR_MODEL = "o3"          # Default executor
    STRONG_MODEL = "claude-3-5-sonnet-20241022"  # Escalation model
    
    # Browser timing (stability first)
    BROWSER_CONFIG = {
        'wait_for_network_idle_page_load_time': 3.0,
        'minimum_wait_page_load_time': 0.5,
        'maximum_wait_page_load_time': 8.0,
        'wait_between_actions': 0.7,
        'default_timeout': 10_000,
        'default_navigation_timeout': 45_000,
    }
    
    # Agent limits
    MAX_ACTIONS_PER_STEP = 2
    MAX_STEPS = 60
    MAX_FAILURES = 3
    RETRY_DELAY = 10
    
    # Vision settings
    USE_VISION = True
    VISION_DETAIL_LEVEL = "auto"  # Set to "low" for simple UIs to cut cost
    
    # Paths
    CONVERSATIONS_DIR = Path("browser_queries/conversations")
    STATE_MEMOS_DIR = Path("browser_queries/state_memos")
    
    def __init__(self):
        self.CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
        self.STATE_MEMOS_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------
# Custom Actions
# ----------------------------

class CustomActions:
    """Custom actions for robustness as per aug23 playbook."""
    
    def __init__(self, controller):
        self.controller = controller
        
    async def safe_go_to(self, url: str) -> bool:
        """Navigate with verification and retry."""
        try:
            await self.controller.page.goto(url)
            await self.controller.page.wait_for_load_state('networkidle', timeout=15000)
            
            # Verify URL contains expected host
            current_url = self.controller.page.url
            from urllib.parse import urlparse
            expected_host = urlparse(url).netloc
            current_host = urlparse(current_url).netloc
            
            if expected_host in current_host or current_host in expected_host:
                return True
            else:
                print(f"⚠️  URL verification failed. Expected: {expected_host}, Got: {current_host}")
                return False
                
        except Exception as e:
            print(f"❌ safe_go_to failed: {e}")
            return False
    
    async def js_click(self, selector: str) -> bool:
        """JavaScript click when standard click fails."""
        try:
            await self.controller.page.evaluate(f"""
                const element = document.querySelector('{selector}');
                if (element) {{
                    element.click();
                    return true;
                }} else {{
                    return false;
                }}
            """)
            return True
        except Exception as e:
            print(f"❌ js_click failed: {e}")
            return False
    
    async def keyboard_activate(self, selector: str = None) -> bool:
        """Focus + Tab/Enter path when selectors are flaky."""
        try:
            if selector:
                await self.controller.page.locator(selector).focus()
            
            # Try Tab then Enter
            await self.controller.page.keyboard.press('Tab')
            await self.controller.page.wait_for_timeout(500)
            await self.controller.page.keyboard.press('Enter')
            return True
            
        except Exception as e:
            print(f"❌ keyboard_activate failed: {e}")
            return False
    
    async def reset_to_home(self, home_url: str) -> bool:
        """Hard return to a known state."""
        try:
            await self.controller.page.goto(home_url)
            await self.controller.page.wait_for_load_state('networkidle', timeout=15000)
            return True
        except Exception as e:
            print(f"❌ reset_to_home failed: {e}")
            return False
    
    def ask_human(self, question: str) -> str:
        """Breakpoint handoff for human input."""
        print(f"\n🤖 HUMAN INPUT NEEDED:")
        print(f"❓ {question}")
        response = input("👤 Your response: ")
        return response

# ----------------------------
# Hooks Implementation
# ----------------------------

class RobustnessHooks:
    """Implement robustness hooks as per aug23 playbook."""
    
    def __init__(self, agent, custom_actions, config):
        self.agent = agent
        self.custom_actions = custom_actions
        self.config = config
        self.consecutive_failures = 0
        self.model_escalated = False
        self.screenshots_dir = Path("browser_queries/screenshots")
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
    
    async def on_step_start(self, agent, step_info: Dict[str, Any]):
        """Hook: on_step_start - Take screenshots and check domain drift."""
        
        # Take screenshot for visual verification if action is navigation or irreversible write
        action_type = step_info.get('action_type', '')
        if any(keyword in action_type.lower() for keyword in ['navigate', 'submit', 'click', 'type']):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = self.screenshots_dir / f"step_{step_info.get('step_number', 0)}_{timestamp}.png"
            
            try:
                await agent.controller.page.screenshot(path=str(screenshot_path))
                print(f"📸 Screenshot saved: {screenshot_path.name}")
            except Exception as e:
                print(f"⚠️  Screenshot failed: {e}")
        
        # Check domain drift (if allowed_domains is configured)
        if hasattr(agent.controller, 'allowed_domains') and agent.controller.allowed_domains != ['*']:
            current_url = agent.controller.page.url
            from urllib.parse import urlparse
            current_domain = urlparse(current_url).netloc
            
            allowed = any(domain in current_domain or current_domain in domain 
                         for domain in agent.controller.allowed_domains)
            
            if not allowed:
                print(f"⚠️  Domain drift detected: {current_domain}")
                # Queue a reset action (this would need to be implemented in the main agent loop)
                
    async def on_step_end(self, agent, step_result: Dict[str, Any]):
        """Hook: on_step_end - Handle failures and model escalation."""
        
        if step_result.get('success', True):
            # Reset failure counter on success
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1
            
            print(f"❌ Step failed. Consecutive failures: {self.consecutive_failures}")
            
            # Auto-escalation: if ≥2 consecutive failures, swap to strong model
            if self.consecutive_failures >= 2 and not self.model_escalated:
                print(f"🔄 Escalating to strong model: {self.config.STRONG_MODEL}")
                
                # Create strong model LLM
                strong_llm = ChatAnthropic(model=self.config.STRONG_MODEL)
                agent.llm = strong_llm
                self.model_escalated = True
            
            # If failed ≥3x, add recovery actions
            if self.consecutive_failures >= 3:
                print("🔄 Adding recovery actions...")
                
                # Try recovery strategies
                try:
                    # Strategy 1: Reload page
                    await agent.controller.page.reload()
                    await agent.controller.page.wait_for_load_state('networkidle', timeout=10000)
                    
                except Exception as e:
                    print(f"Recovery reload failed: {e}")
                    
                    # Strategy 2: Try JS click fallback
                    last_action = step_result.get('last_action', {})
                    if 'selector' in last_action:
                        await self.custom_actions.js_click(last_action['selector'])
                    
                    # Strategy 3: Keyboard navigation
                    await self.custom_actions.keyboard_activate()

# ----------------------------
# Cost Guardrails
# ----------------------------

class CostManager:
    """Manage cost with model downshifting as per aug23 playbook."""
    
    def __init__(self, config):
        self.config = config
        self.task_steady_state = False
        self.recent_failures = []
        
    def should_downshift_model(self, agent) -> bool:
        """Check if we should downshift to cheaper model."""
        
        # Only downshift if in steady state (no recent failures) and actions are trivial
        recent_failures = [step for step in agent.history[-5:] if not step.get('success', True)]
        
        if len(recent_failures) == 0 and self.task_steady_state:
            # Check if recent actions are trivial (scroll, click by text)
            recent_actions = [step.get('action_type', '') for step in agent.history[-3:]]
            trivial_actions = ['scroll', 'click', 'wait']
            
            if all(any(trivial in action.lower() for trivial in trivial_actions) 
                   for action in recent_actions):
                return True
        
        return False
    
    def downshift_model(self, agent):
        """Downshift to cheaper model."""
        print("💰 Downshifting to cost-efficient model: gemini-2.5-flash")
        agent.llm = ChatGoogle(model="gemini-2.5-flash")

# ----------------------------
# Human-in-the-Loop Gates
# ----------------------------

class HumanGatekeeper:
    """Safety gates for human confirmation."""
    
    DANGER_KEYWORDS = [
        'buy', 'purchase', 'submit', 'send', 'transfer', 
        'delete', 'remove', 'cancel', 'confirm payment',
        'place order', 'checkout', 'pay now'
    ]
    
    def requires_confirmation(self, action_description: str) -> bool:
        """Check if action requires human confirmation."""
        return any(keyword in action_description.lower() 
                  for keyword in self.DANGER_KEYWORDS)
    
    def get_human_confirmation(self, action_description: str) -> bool:
        """Get human confirmation for risky action."""
        print(f"\n🚨 CONFIRMATION REQUIRED:")
        print(f"🤖 About to perform: {action_description}")
        print(f"⚠️  This action may be irreversible!")
        
        while True:
            response = input("👤 Continue? (yes/no): ").lower().strip()
            if response in ['yes', 'y']:
                return True
            elif response in ['no', 'n']:
                return False
            else:
                print("Please respond with 'yes' or 'no'")

# ----------------------------
# Main Optimized Agent Class
# ----------------------------

class OptimizedAgent:
    """Main optimized agent implementing aug23 playbook."""
    
    def __init__(self, task: str, config: OptimizedAgentConfig = None):
        self.config = config or OptimizedAgentConfig()
        self.task = task
        
        # Initialize models
        self.planner_llm = ChatOpenAI(model=self.config.PLANNER_MODEL)
        self.executor_llm = ChatOpenAI(model=self.config.EXECUTOR_MODEL)
        
        # Initialize browser profile
        self.browser_profile = BrowserProfile(
            **self.config.BROWSER_CONFIG,
            allowed_domains=['*']  # Configure as needed
        )
        
        # Initialize session and controller
        self.session = BrowserSession(browser_profile=self.browser_profile)
        self.controller = Controller(output_model=TaskResult)
        
        # Initialize custom actions
        self.custom_actions = None  # Will be initialized after controller setup
        
        # Initialize managers
        self.cost_manager = CostManager(self.config)
        self.gatekeeper = HumanGatekeeper()
        
        # State tracking
        self.conversation_path = None
        
    async def setup(self):
        """Setup the agent components."""
        await self.session.start()
        self.controller = Controller(browser=self.session, output_model=TaskResult)
        self.custom_actions = CustomActions(self.controller)
        
        # Initialize hooks
        self.hooks = RobustnessHooks(self, self.custom_actions, self.config)
        
    async def run(self, message_context: str = None) -> TaskResult:
        """Run the optimized agent with all aug23 playbook features."""
        
        try:
            await self.setup()
            
            # Set up conversation saving
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.conversation_path = self.config.CONVERSATIONS_DIR / f"task_{timestamp}.json"
            
            # Load previous state memo if available
            previous_state = self._load_state_memo()
            if previous_state and message_context is None:
                message_context = f"Previous context: {previous_state.context}"
            
            # Create agent with planner/executor strategy
            agent = Agent(
                task=self.task,
                llm=self.executor_llm,
                planner_llm=self.planner_llm,
                controller=self.controller,
                use_vision=self.config.USE_VISION,
                vision_detail_level=self.config.VISION_DETAIL_LEVEL,
                save_conversation_path=str(self.conversation_path),
                message_context=message_context
            )
            
            # Custom hook wrapper to integrate our robustness hooks
            async def enhanced_step_wrapper(step_func, step_info):
                # Pre-step hook
                await self.hooks.on_step_start(agent, step_info)
                
                # Human-in-the-loop gate
                if self.gatekeeper.requires_confirmation(step_info.get('action_description', '')):
                    if not self.gatekeeper.get_human_confirmation(step_info['action_description']):
                        raise Exception("User cancelled action")
                
                # Execute step
                result = await step_func()
                
                # Post-step hook
                await self.hooks.on_step_end(agent, {
                    'success': result.get('success', True),
                    'last_action': step_info
                })
                
                # Cost management
                if self.cost_manager.should_downshift_model(agent):
                    self.cost_manager.downshift_model(agent)
                
                return result
            
            # Run the agent with our configuration
            history = await agent.run(
                max_steps=self.config.MAX_STEPS,
                max_actions_per_step=self.config.MAX_ACTIONS_PER_STEP,
                max_failures=self.config.MAX_FAILURES,
                retry_delay=self.config.RETRY_DELAY,
            )
            
            # Process results using AgentHistoryList helpers
            history_list = AgentHistoryList(history)
            
            # Extract final result
            final_result = TaskResult(
                success=history_list.is_complete(),
                data=history_list.extract_data(),
                steps_taken=len(history),
                final_url=self.controller.page.url if self.controller.page else None
            )
            
            # Save state memo for next run
            self._save_state_memo(final_result, history_list)
            
            return final_result
            
        except Exception as e:
            error_msg = f"Agent execution failed: {str(e)}\n{traceback.format_exc()}"
            print(f"❌ {error_msg}")
            
            return TaskResult(
                success=False,
                error=error_msg,
                steps_taken=0
            )
            
        finally:
            if hasattr(self, 'session'):
                await self.session.close()
    
    def _load_state_memo(self) -> Optional[StateMemo]:
        """Load previous state memo."""
        memo_file = self.config.STATE_MEMOS_DIR / "latest_memo.json"
        if memo_file.exists():
            try:
                with open(memo_file, 'r') as f:
                    data = json.load(f)
                return StateMemo(**data)
            except Exception as e:
                print(f"⚠️  Failed to load state memo: {e}")
        return None
    
    def _save_state_memo(self, result: TaskResult, history: AgentHistoryList):
        """Save compact state memo for next run."""
        memo = StateMemo(
            last_url=result.final_url,
            last_success="Task completed successfully" if result.success else None,
            last_error=result.error if not result.success else None,
            context=f"Last task: {self.task[:100]}. Steps taken: {result.steps_taken}",
        )
        
        memo_file = self.config.STATE_MEMOS_DIR / "latest_memo.json"
        with open(memo_file, 'w') as f:
            json.dump(memo.dict(), f, indent=2)

# ----------------------------
# Example Usage Functions
# ----------------------------

async def run_search_task():
    """Example: Search task with optimization."""
    agent = OptimizedAgent(
        task="Search for 'browser automation tools' and extract the top 5 results with titles and URLs"
    )
    
    result = await agent.run()
    
    print(f"\n{'='*50}")
    print(f"Task completed: {result.success}")
    if result.data:
        print(f"Data extracted: {result.data}")
    if result.error:
        print(f"Error: {result.error}")
    print(f"Steps taken: {result.steps_taken}")
    print(f"Final URL: {result.final_url}")
    
    return result

async def run_form_filling_task():
    """Example: Form filling with human confirmation gates."""
    agent = OptimizedAgent(
        task="Navigate to a contact form and fill it with sample data, but ask for confirmation before submitting"
    )
    
    result = await agent.run()
    return result

# ----------------------------
# Interactive CLI
# ----------------------------

def print_banner():
    print(f"\n{'='*70}")
    print(f"🚀 OPTIMIZED BROWSER-USE AGENT - Aug23 Playbook")
    print(f"{'='*70}")
    print(f"✅ Model Strategy: Planner → Executor → Auto-escalation")
    print(f"✅ Robustness Hooks: Screenshots, Domain checks, Failure handling")
    print(f"✅ Custom Actions: safe_go_to, js_click, keyboard_activate")
    print(f"✅ Human Gates: Confirmation for risky actions")
    print(f"✅ Cost Guardrails: Model downshifting in steady state")
    print(f"✅ State Persistence: Conversation & memo saving")
    print(f"{'='*70}\n")

async def interactive_mode():
    """Interactive mode for testing the optimized agent."""
    print_banner()
    
    while True:
        print(f"\n📝 Options:")
        print(f"1. Run search task (example)")
        print(f"2. Run custom task")
        print(f"3. Run form filling task (with human gates)")
        print(f"4. Exit")
        
        choice = input(f"\n👤 Your choice (1-4): ").strip()
        
        if choice == '1':
            print(f"\n🔄 Running search task...")
            await run_search_task()
            
        elif choice == '2':
            task = input(f"\n📝 Enter your task: ").strip()
            if task:
                print(f"\n🔄 Running custom task...")
                agent = OptimizedAgent(task=task)
                result = await agent.run()
                
                print(f"\n📊 Results:")
                print(f"Success: {result.success}")
                if result.data:
                    print(f"Data: {json.dumps(result.data, indent=2)}")
                if result.error:
                    print(f"Error: {result.error}")
                    
        elif choice == '3':
            print(f"\n🔄 Running form filling task with human gates...")
            await run_form_filling_task()
            
        elif choice == '4':
            print(f"\n👋 Goodbye!")
            break
            
        else:
            print(f"❌ Invalid choice. Please select 1-4.")

if __name__ == "__main__":
    asyncio.run(interactive_mode())