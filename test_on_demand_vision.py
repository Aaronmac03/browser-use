#!/usr/bin/env python3
"""
Test script for on-demand vision detection functionality.
This script demonstrates how the agent can start with text-only mode and escalate to vision when needed.
"""

import asyncio
from browser_use import Agent
from browser_use.llm import OpenAILLM

async def test_on_demand_vision():
    """Test the on-demand vision detection feature"""
    
    # Initialize the LLM
    llm = OpenAILLM(model="gpt-4o-mini")
    
    # Create agent with on-demand vision enabled
    agent = Agent(
        task="Go to google.com and search for 'browser automation'. Tell me what you see on the results page.",
        llm=llm,
        use_on_demand_vision=True,  # Enable on-demand vision detection
        use_vision=True,  # Base vision capability (will be overridden by on-demand logic)
        max_actions_per_step=3,
    )
    
    print("🚀 Starting agent with on-demand vision detection...")
    print("📝 The agent will start with text-only mode and escalate to vision when needed")
    
    try:
        # Run the agent
        result = await agent.run(max_steps=10)
        
        print("\n✅ Agent completed successfully!")
        print(f"📊 Final result: {result}")
        
        # Print vision usage statistics
        if hasattr(agent.state, 'vision_requirements_history'):
            print(f"\n📚 Vision requirements learned: {agent.state.vision_requirements_history}")
        
    except Exception as e:
        print(f"❌ Error during execution: {e}")
    
    finally:
        await agent.close()

if __name__ == "__main__":
    asyncio.run(test_on_demand_vision())