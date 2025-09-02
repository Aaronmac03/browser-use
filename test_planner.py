#!/usr/bin/env python3

import asyncio
import sys
from dotenv import load_dotenv
from runner import plan_with_o3_then_gemini

async def test_planner():
    load_dotenv()
    goal = "Add bananas and 2% milk to my Walmart cart for pickup at the 40205 Bashford Manor store"
    
    print(f"Testing planner with goal: {goal}")
    print("=" * 80)
    
    try:
        subtasks = await plan_with_o3_then_gemini(goal)
        print(f"Generated {len(subtasks)} subtasks:")
        print()
        
        for i, task in enumerate(subtasks, 1):
            print(f"SUBTASK {i}:")
            print(f"  Title: {task.get('title', 'N/A')}")
            print(f"  Instructions: {task.get('instructions', 'N/A')}")
            print(f"  Success: {task.get('success', 'N/A')}")
            print()
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_planner())