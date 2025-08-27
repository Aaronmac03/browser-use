#!/usr/bin/env python3
"""
Simple Hybrid Agent - Modern Browser-Use API Compatible

A simplified version that properly integrates with the current Browser-Use API
while demonstrating hybrid local/cloud concepts.
"""

import asyncio
import os
from dotenv import load_dotenv
from typing import Dict, Any

# Load environment variables
load_dotenv(override=True)

from browser_use import Agent, BrowserProfile, BrowserSession, ChatGoogle
from serper_search import search_with_serper_fallback

class SimpleHybridAgent:
    """A simplified hybrid agent that uses modern Browser-Use API correctly."""
    
    def __init__(self):
        # Initialize Google Gemini for cloud reasoning
        self.cloud_llm = ChatGoogle(
            model_name="gemini-2.0-flash-exp",
            api_key=os.getenv("GOOGLE_API_KEY")
        )
        
        # Create browser profile
        self.browser_profile = BrowserProfile(
            headless=False,
            disable_security=True,
            extra_chromium_args=['--disable-search-engine-choice-screen']
        )
        
        # Create browser session
        self.browser_session = BrowserSession(browser_profile=self.browser_profile)
    
    async def execute_task(self, task: str) -> Dict[str, Any]:
        """Execute a task using the hybrid approach."""
        print(f"🤖 Starting task: {task}")
        
        try:
            # For simple search queries, try Serper first (faster)
            if self._is_simple_search_query(task):
                print("🔍 Attempting search-first approach...")
                try:
                    from browser_use import Controller
                    controller = Controller()
                    search_result = await search_with_serper_fallback(controller, task, 5)
                    
                    # If we get good search results, return them
                    if search_result and search_result.extracted_content:
                        print("✅ Search completed successfully!")
                        return {
                            'success': True,
                            'method': 'search',
                            'result': search_result.extracted_content[:1000] + ("..." if len(search_result.extracted_content) > 1000 else "")
                        }
                except Exception as e:
                    print(f"⚠️ Search failed: {e}, falling back to browser...")
            
            # Fall back to full browser automation using modern Agent API
            print("🌐 Using browser automation...")
            
            # Create agent with our pre-configured browser session
            agent = Agent(
                task=task,
                llm=self.cloud_llm,
                browser_session=self.browser_session,
                use_vision=True,
                max_failures=3,
                generate_gif=False
            )
            
            # Execute the task
            result = await agent.run()
            
            print("✅ Browser task completed!")
            return {
                'success': True,
                'method': 'browser',
                'result': str(result) if result else 'Task completed successfully'
            }
            
        except Exception as e:
            print(f"❌ Task failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'method': 'failed'
            }
    
    def _is_simple_search_query(self, task: str) -> bool:
        """Determine if this is a simple search query that could be handled by search API."""
        search_indicators = [
            'price', 'cost', 'weather', 'temperature', 'news', 'stock',
            'what is', 'how much', 'find', 'search', 'look up'
        ]
        
        task_lower = task.lower()
        return any(indicator in task_lower for indicator in search_indicators)
    
    async def cleanup(self):
        """Clean up resources."""
        try:
            if self.browser_session:
                await self.browser_session.stop()
        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")


async def main():
    """Main interactive loop."""
    print("🤖 Simple Hybrid Agent")
    print("=" * 50)
    print("This agent uses:")
    print("- Serper API for simple search queries")
    print("- Browser automation for complex interactions")
    print("- Modern Browser-Use API")
    print()
    
    agent = SimpleHybridAgent()
    
    try:
        while True:
            task = input("💭 Enter your task (or 'quit' to exit): ").strip()
            
            if task.lower() in ['quit', 'exit', 'q']:
                break
            
            if not task:
                continue
            
            result = await agent.execute_task(task)
            
            print(f"\n📊 Result:")
            print(f"   Success: {result['success']}")
            print(f"   Method: {result.get('method', 'unknown')}")
            
            if result['success'] and 'result' in result:
                print(f"   Output: {result['result'][:500]}{'...' if len(str(result['result'])) > 500 else ''}")
            elif 'error' in result:
                print(f"   Error: {result['error']}")
            
            print()
    
    finally:
        await agent.cleanup()
        print("👋 Goodbye!")


if __name__ == "__main__":
    asyncio.run(main())