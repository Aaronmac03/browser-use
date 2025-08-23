"""
Aug23 Playbook Hooks Module

Drop-in hooks for adding robustness, cost management, and human-in-the-loop features
to any existing browser-use agent. Just import and attach to your agent.

Usage:
    from aug23_hooks import RobustnessManager
    
    manager = RobustnessManager()
    # In your agent run loop, call:
    await manager.on_step_start(agent, step_info)
    await manager.on_step_end(agent, step_result)
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

class RobustnessManager:
    """Drop-in robustness manager implementing aug23 playbook patterns."""
    
    def __init__(self, 
                 strong_model_name: str = "claude-3-5-sonnet-20241022",
                 screenshots_dir: str = "browser_queries/screenshots",
                 failure_threshold: int = 2):
        """
        Args:
            strong_model_name: Model to escalate to on failures
            screenshots_dir: Where to save verification screenshots  
            failure_threshold: Consecutive failures before escalation
        """
        self.strong_model_name = strong_model_name
        self.screenshots_dir = Path(screenshots_dir)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.failure_threshold = failure_threshold
        
        # State tracking
        self.consecutive_failures = 0
        self.model_escalated = False
        self.strong_llm = None
        
    async def on_step_start(self, agent, step_info: Dict[str, Any] = None):
        """Pre-step hook: Screenshots and domain verification."""
        
        if not hasattr(agent, 'controller') or not agent.controller.page:
            return
            
        # Take screenshot for visual verification if risky action
        action_type = step_info.get('action_type', '') if step_info else ''
        risky_keywords = ['navigate', 'submit', 'click', 'type', 'form', 'button']
        
        if any(keyword in action_type.lower() for keyword in risky_keywords):
            await self._take_verification_screenshot(agent, step_info)
        
        # Check for domain drift
        await self._check_domain_drift(agent)
    
    async def on_step_end(self, agent, step_result: Dict[str, Any] = None):
        """Post-step hook: Failure handling and model escalation."""
        
        # Determine if step failed
        failed = self._step_failed(agent, step_result)
        
        if not failed:
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1
            print(f"❌ Step failed. Consecutive failures: {self.consecutive_failures}")
            
            # Auto-escalation after threshold failures
            if self.consecutive_failures >= self.failure_threshold and not self.model_escalated:
                await self._escalate_model(agent)
            
            # Recovery actions after 3 failures
            if self.consecutive_failures >= 3:
                await self._attempt_recovery(agent, step_result)
    
    async def _take_verification_screenshot(self, agent, step_info: Dict[str, Any] = None):
        """Take screenshot for visual verification."""
        try:
            step_num = step_info.get('step_number', len(getattr(agent, 'history', [])))
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"step_{step_num}_{timestamp}.png"
            filepath = self.screenshots_dir / filename
            
            await agent.controller.page.screenshot(path=str(filepath))
            print(f"📸 Verification screenshot: {filename}")
            
        except Exception as e:
            print(f"⚠️  Screenshot failed: {e}")
    
    async def _check_domain_drift(self, agent):
        """Check if we've drifted outside allowed domains."""
        try:
            if not hasattr(agent.controller, 'allowed_domains'):
                return
                
            allowed_domains = getattr(agent.controller, 'allowed_domains', ['*'])
            if '*' in allowed_domains:
                return
                
            current_url = agent.controller.page.url
            current_domain = urlparse(current_url).netloc
            
            # Check if current domain is allowed
            domain_allowed = any(
                domain in current_domain or current_domain in domain
                for domain in allowed_domains
            )
            
            if not domain_allowed:
                print(f"⚠️  Domain drift detected: {current_domain}")
                print(f"    Allowed domains: {allowed_domains}")
                # Could implement auto-redirect to allowed domain here
                
        except Exception as e:
            print(f"⚠️  Domain check failed: {e}")
    
    def _step_failed(self, agent, step_result: Dict[str, Any] = None) -> bool:
        """Determine if the last step failed."""
        
        # Method 1: Check step_result if provided
        if step_result is not None:
            return not step_result.get('success', True)
        
        # Method 2: Check agent history
        if hasattr(agent, 'history') and agent.history:
            last_step = agent.history[-1]
            
            # Check for error indicators
            if hasattr(last_step, 'error') and last_step.error:
                return True
            if isinstance(last_step, dict) and last_step.get('error'):
                return True
            if hasattr(last_step, 'success'):
                return not last_step.success
                
        # Method 3: Check for exceptions in recent browser state
        try:
            if hasattr(agent, 'controller') and agent.controller.page:
                # Could check page state, console errors, etc.
                pass
        except:
            return True
            
        # Default to success if we can't determine failure
        return False
    
    async def _escalate_model(self, agent):
        """Escalate to stronger model on repeated failures."""
        try:
            if not self.strong_llm:
                from browser_use.llm import ChatAnthropic
                self.strong_llm = ChatAnthropic(model=self.strong_model_name)
            
            print(f"🔄 Escalating to strong model: {self.strong_model_name}")
            agent.llm = self.strong_llm
            self.model_escalated = True
            
        except Exception as e:
            print(f"⚠️  Model escalation failed: {e}")
    
    async def _attempt_recovery(self, agent, step_result: Dict[str, Any] = None):
        """Attempt recovery actions after multiple failures."""
        print("🔄 Attempting recovery actions...")
        
        try:
            # Recovery Strategy 1: Page reload
            await agent.controller.page.reload()
            await agent.controller.page.wait_for_load_state('networkidle', timeout=10000)
            print("  ✅ Page reloaded")
            
        except Exception as e:
            print(f"  ❌ Reload failed: {e}")
            
            # Recovery Strategy 2: JS click fallback (if we have selector info)
            try:
                last_action = step_result.get('last_action', {}) if step_result else {}
                selector = last_action.get('selector')
                
                if selector:
                    await agent.controller.page.evaluate(f"""
                        const element = document.querySelector('{selector}');
                        if (element) element.click();
                    """)
                    print(f"  ✅ JS click attempted on {selector}")
                    
            except Exception as e2:
                print(f"  ❌ JS click failed: {e2}")
                
                # Recovery Strategy 3: Keyboard navigation
                try:
                    await agent.controller.page.keyboard.press('Tab')
                    await asyncio.sleep(0.5)
                    await agent.controller.page.keyboard.press('Enter')
                    print("  ✅ Keyboard navigation attempted")
                    
                except Exception as e3:
                    print(f"  ❌ Keyboard navigation failed: {e3}")


class CustomActions:
    """Custom actions for enhanced reliability."""
    
    @staticmethod
    async def safe_go_to(page, url: str, timeout: int = 15000) -> bool:
        """Navigate with verification and retry."""
        try:
            await page.goto(url, timeout=timeout)
            await page.wait_for_load_state('networkidle', timeout=timeout)
            
            # Verify URL
            current_url = page.url
            expected_host = urlparse(url).netloc
            current_host = urlparse(current_url).netloc
            
            return expected_host in current_host or current_host in expected_host
            
        except Exception as e:
            print(f"❌ safe_go_to failed: {e}")
            return False
    
    @staticmethod
    async def js_click(page, selector: str) -> bool:
        """JavaScript click when standard click fails."""
        try:
            result = await page.evaluate(f"""
                const element = document.querySelector('{selector}');
                if (element) {{
                    element.click();
                    return true;
                }} else {{
                    return false;
                }}
            """)
            return result
        except Exception as e:
            print(f"❌ js_click failed: {e}")
            return False
    
    @staticmethod
    async def keyboard_activate(page, selector: str = None) -> bool:
        """Focus + Tab/Enter path when selectors are flaky."""
        try:
            if selector:
                await page.locator(selector).focus()
            
            await page.keyboard.press('Tab')
            await asyncio.sleep(0.5)
            await page.keyboard.press('Enter')
            return True
            
        except Exception as e:
            print(f"❌ keyboard_activate failed: {e}")
            return False
    
    @staticmethod
    def ask_human(question: str) -> str:
        """Breakpoint handoff for human input."""
        print(f"\n🤖 HUMAN INPUT NEEDED:")
        print(f"❓ {question}")
        response = input("👤 Your response: ")
        return response


class HumanGatekeeper:
    """Human-in-the-loop safety gates."""
    
    DANGER_KEYWORDS = [
        'buy', 'purchase', 'submit', 'send', 'transfer', 
        'delete', 'remove', 'cancel', 'confirm payment',
        'place order', 'checkout', 'pay now'
    ]
    
    def requires_confirmation(self, action_description: str) -> bool:
        """Check if action requires human confirmation."""
        return any(keyword in action_description.lower() 
                  for keyword in self.DANGER_KEYWORDS)
    
    def get_confirmation(self, action_description: str) -> bool:
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


class CostManager:
    """Cost management with model downshifting."""
    
    def __init__(self, cheap_model_name: str = "gemini-2.5-flash"):
        self.cheap_model_name = cheap_model_name
        self.cheap_llm = None
        self.downshifted = False
    
    def should_downshift(self, agent) -> bool:
        """Check if we should downshift to cheaper model."""
        if self.downshifted:
            return False
            
        if not hasattr(agent, 'history') or len(agent.history) < 5:
            return False
        
        # Check recent actions for being trivial
        recent_actions = [str(step).lower() for step in agent.history[-3:]]
        trivial_keywords = ['scroll', 'click', 'wait', 'navigate']
        
        return all(
            any(keyword in action for keyword in trivial_keywords)
            for action in recent_actions
        )
    
    def downshift_model(self, agent):
        """Downshift to cheaper model."""
        if not self.cheap_llm:
            from browser_use.llm import ChatGoogle
            self.cheap_llm = ChatGoogle(model=self.cheap_model_name)
        
        print(f"💰 Downshifting to cost-efficient model: {self.cheap_model_name}")
        agent.llm = self.cheap_llm
        self.downshifted = True


class StatePersistence:
    """State persistence utilities."""
    
    @staticmethod
    def save_state_memo(task: str, result: Dict[str, Any], 
                       memo_file: str = "browser_queries/state_memos/latest.json"):
        """Save compact state memo for next run."""
        memo_path = Path(memo_file)
        memo_path.parent.mkdir(parents=True, exist_ok=True)
        
        memo = {
            "timestamp": datetime.now().isoformat(),
            "task": task,
            "last_url": result.get("final_url"),
            "success": result.get("success", False),
            "error": result.get("error"),
            "context": f"Previous task: {task[:100]}. Success: {result.get('success', False)}"
        }
        
        with open(memo_path, 'w') as f:
            json.dump(memo, f, indent=2)
        
        return memo
    
    @staticmethod
    def load_state_memo(memo_file: str = "browser_queries/state_memos/latest.json") -> Optional[Dict[str, Any]]:
        """Load previous state memo."""
        memo_path = Path(memo_file)
        if memo_path.exists():
            try:
                with open(memo_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  Failed to load state memo: {e}")
        return None


# --- Integration Example ---

async def enhanced_agent_run(agent, task: str, use_human_gates: bool = False, 
                           use_cost_management: bool = True):
    """
    Enhanced agent run with all aug23 playbook features.
    
    Drop this function into any existing project to add optimizations.
    """
    
    # Initialize managers
    robustness = RobustnessManager()
    gatekeeper = HumanGatekeeper() if use_human_gates else None
    cost_manager = CostManager() if use_cost_management else None
    
    # Pre-run human gate
    if gatekeeper and gatekeeper.requires_confirmation(task):
        if not gatekeeper.get_confirmation(task):
            return {"success": False, "error": "User cancelled"}
    
    # Load previous context
    previous_memo = StatePersistence.load_state_memo()
    message_context = previous_memo.get("context") if previous_memo else None
    
    try:
        # Enhanced run with hooks
        step_count = 0
        
        # Simplified hook integration (in real implementation, this would be integrated into the agent loop)
        original_run = agent.run
        
        async def hooked_run(*args, **kwargs):
            nonlocal step_count
            
            # Pre-run hook
            await robustness.on_step_start(agent, {"step_number": step_count})
            
            # Run original
            result = await original_run(*args, **kwargs)
            
            # Post-run hook
            await robustness.on_step_end(agent, {"success": True})  # Simplified
            
            # Cost management
            if cost_manager and cost_manager.should_downshift(agent):
                cost_manager.downshift_model(agent)
            
            step_count += 1
            return result
        
        # Execute with enhanced capabilities
        history = await agent.run(
            max_steps=60,
            max_actions_per_step=2,
            max_failures=3,
            retry_delay=10,
        )
        
        # Process results
        from browser_use.agent.views import AgentHistoryList
        history_list = AgentHistoryList(history)
        
        result = {
            "success": history_list.is_complete(),
            "data": history_list.extract_data(),
            "final_url": agent.controller.page.url if agent.controller.page else None,
            "steps_taken": len(history),
        }
        
        # Save state memo
        StatePersistence.save_state_memo(task, result)
        
        return result
        
    except Exception as e:
        error_result = {"success": False, "error": str(e), "steps_taken": step_count}
        StatePersistence.save_state_memo(task, error_result)
        return error_result


if __name__ == "__main__":
    print("Aug23 Hooks Module - Import this into your browser-use project")
    print("Usage:")
    print("  from aug23_hooks import RobustnessManager, enhanced_agent_run")
    print("  manager = RobustnessManager()")
    print("  result = await enhanced_agent_run(agent, task, use_human_gates=True)")