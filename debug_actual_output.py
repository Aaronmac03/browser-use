#!/usr/bin/env python3
"""
Debug the actual output being generated during browser automation
"""

import asyncio
import sys
import json
import logging
from pathlib import Path

# Add browser-use to path
sys.path.insert(0, str(Path(__file__).parent))

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

async def test_with_real_browser_context():
    """Test with the actual browser context that's causing issues"""
    
    print("🔍 Testing with real browser automation context...")
    
    try:
        from runner import make_local_llm
        from browser_use.llm.messages import SystemMessage, UserMessage
        from browser_use.agent.views import AgentOutput
        from browser_use.tools.registry.service import Registry
        
        llm = make_local_llm()
        
        # Create the actual tool registry that browser-use uses
        registry = Registry()
        
        # Get the actual action model that browser-use creates
        action_model = registry.create_action_model()
        output_model = AgentOutput.type_with_custom_actions(action_model)
        
        print("Actual browser-use schema:")
        schema = output_model.model_json_schema()
        print(json.dumps(schema, indent=2)[:1000] + "...")
        
        # Use a realistic system prompt
        system_prompt = """You are a web automation agent. You can navigate websites and interact with elements.

Available actions:
- click_element_by_index: Click on an element by its index
- input_text: Type text into an element  
- done: Complete the task
- extract_structured_data: Extract structured data from the page

You must respond with JSON in this exact format:
{
  "thinking": "your reasoning process",
  "evaluation_previous_goal": "assessment of previous step", 
  "memory": "important information to remember",
  "next_goal": "what to do next",
  "action": [
    {
      "done": {
        "text": "task result",
        "success": true
      }
    }
  ]
}

The "action" field must be an array containing action objects. Each action object should have exactly one action field set to a parameter object."""
        
        user_prompt = """Current page DOM:
[1] <h1>Example Domain</h1>
[2] <p>This domain is for use in illustrative examples in documents. You may use this domain in literature without prior coordination or asking for permission.</p>
[3] <p><a href="https://www.iana.org/domains/example">More information...</a></p>

Task: Extract the main heading text and complete the task.

Please respond with the exact JSON format specified."""
        
        messages = [
            SystemMessage(content=system_prompt),
            UserMessage(content=user_prompt)
        ]
        
        print("\nSending request with structured output...")
        try:
            result = await llm.ainvoke(messages, output_format=output_model)
            
            print(f"✅ Structured output succeeded!")
            print(f"Result type: {type(result.completion)}")
            
            if hasattr(result.completion, 'model_dump'):
                print("Structured result:")
                print(json.dumps(result.completion.model_dump(), indent=2))
                return True
            else:
                print(f"Not structured: {result.completion}")
                return False
                
        except Exception as e:
            print(f"❌ Structured output failed: {e}")
            
            # Try without structured output to see raw response
            print("\nTrying without structured output to see raw response...")
            raw_result = await llm.ainvoke(messages)
            print("Raw response:")
            print("=" * 60)
            print(raw_result.completion)
            print("=" * 60)
            
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("🧪 ACTUAL OUTPUT DEBUG")
    print("="*60)
    
    success = await test_with_real_browser_context()
    
    print("\n" + "="*60)
    print("🎯 DEBUG RESULT")
    print("="*60)
    print(f"Structured output: {'✅ PASS' if success else '❌ FAIL'}")
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)