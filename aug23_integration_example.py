"""
Aug23 Integration Example - How to add optimizations to existing browser-use projects

This shows 3 ways to integrate the aug23 playbook optimizations:
1. Drop-in hooks for existing agents
2. Quick config upgrade
3. Full optimization wrapper

Choose the approach that fits your existing codebase.
"""

import asyncio
from browser_use import Agent, Controller, BrowserProfile
from browser_use.llm import ChatOpenAI

# Import our optimization modules
from aug23_hooks import RobustnessManager, HumanGatekeeper, enhanced_agent_run

# --- Method 1: Drop-in hooks for existing agents ---

async def method_1_drop_in_hooks():
    """Add robustness to existing agent with minimal changes."""
    
    print("🔧 Method 1: Drop-in hooks")
    
    # Your existing agent setup (unchanged)
    agent = Agent(
        task="Search for 'browser automation' and get the first 3 results",
        llm=ChatOpenAI(model="o3"),
        use_vision=True,
    )
    
    # Add robustness manager
    robustness = RobustnessManager()
    
    # Your existing run call - just wrap it
    result = await enhanced_agent_run(
        agent, 
        task="Search for 'browser automation' and get the first 3 results",
        use_human_gates=True,
        use_cost_management=True
    )
    
    print(f"✅ Result: {result}")
    return result

# --- Method 2: Quick config upgrade ---

async def method_2_config_upgrade():
    """Upgrade existing agent config with stability settings."""
    
    print("🔧 Method 2: Config upgrade")
    
    # Aug23 optimized browser profile
    optimized_profile = BrowserProfile(
        wait_for_network_idle_page_load_time=3.0,    # Stability first
        minimum_wait_page_load_time=0.5,
        maximum_wait_page_load_time=8.0,
        wait_between_actions=0.7,                    # Reliability over speed
        default_timeout=10_000,
        default_navigation_timeout=45_000,
        allowed_domains=['*'],
    )
    
    # Model strategy: planner + executor
    planner_llm = ChatOpenAI(model="gpt-4o-mini")  # Cheap reasoning
    executor_llm = ChatOpenAI(model="o3")           # Strong execution
    
    # Enhanced agent
    agent = Agent(
        task="Navigate to GitHub and search for 'browser-use'",
        llm=executor_llm,
        planner_llm=planner_llm,                    # Enable planner strategy
        controller=Controller(browser_profile=optimized_profile),
        use_vision=True,
        vision_detail_level="auto",                 # Dynamic vision cost
        save_conversation_path="browser_queries/conversations",  # Observability
    )
    
    # Run with stability settings
    history = await agent.run(
        max_steps=60,
        max_actions_per_step=2,                     # Controlled steps
        max_failures=3,
        retry_delay=10,                             # Patient retries
    )
    
    print(f"✅ Task completed with {len(history)} steps")
    return history

# --- Method 3: Full optimization wrapper ---

async def method_3_full_wrapper():
    """Complete optimization wrapper - use when you want everything."""
    
    print("🔧 Method 3: Full optimization")
    
    from optimized_agent import OptimizedAgent
    
    # One-liner optimized agent
    agent = OptimizedAgent(
        task="Find the latest release of browser-use on GitHub and extract version info"
    )
    
    # Includes all aug23 features: hooks, custom actions, human gates, cost management
    result = await agent.run(message_context="Looking for version info")
    
    print(f"✅ Optimized result: {result}")
    return result

# --- Method 4: Selective feature integration ---

async def method_4_selective_features():
    """Pick and choose specific optimizations."""
    
    print("🔧 Method 4: Selective features")
    
    # Standard agent setup
    agent = Agent(
        task="Search for AI agent frameworks and compare them",
        llm=ChatOpenAI(model="o3"),
    )
    
    # Only add human gates for safety
    gatekeeper = HumanGatekeeper()
    
    if gatekeeper.requires_confirmation(agent.task):
        if not gatekeeper.get_confirmation(agent.task):
            return {"cancelled": True}
    
    # Only add robustness hooks
    robustness = RobustnessManager()
    
    # Manual hook integration (simplified)
    print("Running with selective optimizations...")
    history = await agent.run(max_steps=30)
    
    # Post-process with state persistence
    from aug23_hooks import StatePersistence
    result = {"success": True, "steps": len(history)}
    StatePersistence.save_state_memo(agent.task, result)
    
    return result

# --- Integration into existing agent.py ---

def integrate_into_existing_agent_file():
    """
    How to integrate into your existing agent.py file:
    
    1. Add this import at the top:
       from aug23_hooks import RobustnessManager, enhanced_agent_run
    
    2. Replace your agent.run() call with:
       result = await enhanced_agent_run(agent, task_description, use_human_gates=True)
    
    3. Or add hooks manually:
       robustness = RobustnessManager()
       # In your run loop:
       await robustness.on_step_start(agent, step_info)
       # ... your existing code ...
       await robustness.on_step_end(agent, step_result)
    
    4. Use optimized browser profile:
       profile = BrowserProfile(
           wait_for_network_idle_page_load_time=3.0,
           wait_between_actions=0.7,
           default_timeout=10_000,
       )
    """
    pass

# --- Demo runner ---

async def main():
    """Run all integration examples."""
    
    print("🚀 Aug23 Playbook Integration Examples")
    print("=" * 50)
    
    examples = [
        ("Drop-in Hooks", method_1_drop_in_hooks),
        ("Config Upgrade", method_2_config_upgrade), 
        ("Full Wrapper", method_3_full_wrapper),
        ("Selective Features", method_4_selective_features),
    ]
    
    for name, func in examples:
        try:
            print(f"\n▶️  Running {name}...")
            result = await func()
            print(f"✅ {name} completed successfully")
            
        except Exception as e:
            print(f"❌ {name} failed: {e}")
        
        print("-" * 30)
    
    print("\n🎯 Integration Tips:")
    print("• Start with Method 1 (drop-in hooks) for existing projects")
    print("• Use Method 2 (config upgrade) for better stability")
    print("• Try Method 3 (full wrapper) for new projects")
    print("• Method 4 (selective) when you only want specific features")

if __name__ == "__main__":
    asyncio.run(main())