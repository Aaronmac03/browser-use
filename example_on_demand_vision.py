#!/usr/bin/env python3
"""
Example demonstrating on-demand vision detection in browser-use.

This example shows how the agent can:
1. Start with text-only processing for efficiency
2. Automatically detect when vision is needed
3. Escalate to vision mode when required
4. Learn from experience for future steps
"""

import asyncio
from browser_use import Agent
from browser_use.llm import OpenAILLM

async def compare_vision_strategies():
    """Compare traditional vision vs on-demand vision strategies"""
    
    llm = OpenAILLM(model="gpt-4o-mini")
    
    task = """
    Go to https://example.com and analyze the page layout. 
    Then navigate to a search engine and search for 'python programming'.
    Tell me about the visual elements you can see on both pages.
    """
    
    print("🔄 Comparing vision strategies...")
    
    # Test 1: Traditional always-on vision
    print("\n1️⃣ Testing traditional always-on vision...")
    agent_traditional = Agent(
        task=task,
        llm=llm,
        use_vision=True,
        use_on_demand_vision=False,  # Traditional approach
        max_actions_per_step=2,
    )
    
    try:
        result1 = await agent_traditional.run(max_steps=8)
        print("✅ Traditional vision completed")
    except Exception as e:
        print(f"❌ Traditional vision error: {e}")
    finally:
        await agent_traditional.close()
    
    # Test 2: On-demand vision detection
    print("\n2️⃣ Testing on-demand vision detection...")
    agent_on_demand = Agent(
        task=task,
        llm=llm,
        use_vision=True,  # Base capability
        use_on_demand_vision=True,  # Enable smart detection
        max_actions_per_step=2,
    )
    
    try:
        result2 = await agent_on_demand.run(max_steps=8)
        print("✅ On-demand vision completed")
        
        # Show what the agent learned
        if hasattr(agent_on_demand.state, 'vision_requirements_history'):
            print(f"📚 Vision patterns learned: {agent_on_demand.state.vision_requirements_history}")
            
    except Exception as e:
        print(f"❌ On-demand vision error: {e}")
    finally:
        await agent_on_demand.close()

async def simple_on_demand_example():
    """Simple example showing on-demand vision in action"""
    
    llm = OpenAILLM(model="gpt-4o-mini")
    
    agent = Agent(
        task="Go to google.com and describe what you see. Focus on visual elements like colors and layout.",
        llm=llm,
        use_on_demand_vision=True,
        max_actions_per_step=2,
    )
    
    print("🎯 Simple on-demand vision example...")
    print("📝 Agent will start text-only and request vision when it realizes it needs to describe visual elements")
    
    try:
        result = await agent.run(max_steps=5)
        print(f"✅ Result: {result}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await agent.close()

if __name__ == "__main__":
    print("🚀 On-Demand Vision Detection Examples")
    print("=" * 50)
    
    # Run the simple example
    asyncio.run(simple_on_demand_example())
    
    print("\n" + "=" * 50)
    
    # Uncomment to run the comparison (takes longer)
    # asyncio.run(compare_vision_strategies())