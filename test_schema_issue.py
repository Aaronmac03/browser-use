#!/usr/bin/env python3
"""
Test to reproduce the schema mismatch issue described in roadmap.md
"""

import asyncio
import sys
import json
from pathlib import Path

# Add browser-use to path
sys.path.insert(0, str(Path(__file__).parent))

from runner import make_local_llm
from browser_use.llm.messages import SystemMessage, UserMessage
from browser_use.agent.views import AgentOutput
from browser_use.tools.registry.views import ActionModel

async def test_structured_output_schema():
    """Test if local LLM generates the correct schema format"""
    
    print("Testing structured output schema compatibility...")
    
    try:
        llm = make_local_llm()
        
        # Create a simple action model for testing
        from browser_use.tools.registry.actions.done import DoneAction
        
        # Get the expected schema
        output_model = AgentOutput.type_with_custom_actions(DoneAction)
        schema = output_model.model_json_schema()
        
        print("Expected schema structure:")
        print(json.dumps(schema, indent=2))
        print("\n" + "="*60 + "\n")
        
        # Test with a simple task that should generate structured output
        messages = [
            SystemMessage(content="""You are a web automation agent. You must respond with valid JSON matching the provided schema.
The schema expects:
- thinking: your reasoning (optional)
- evaluation_previous_goal: assessment of previous step
- memory: important information to remember
- next_goal: what to do next
- action: array of actions to take

Respond ONLY with valid JSON, no additional text."""),
            UserMessage(content="""Task: Navigate to example.com and find the main heading.

Current state: Browser is ready to navigate.

Please provide your response as JSON matching the schema.""")
        ]
        
        print("Sending request for structured output...")
        result = await llm.ainvoke(messages, output_format=output_model)
        
        print(f"Response type: {type(result.completion)}")
        print(f"Response content: {result.completion}")
        
        # Try to validate the response
        if hasattr(result.completion, 'model_dump'):
            print("\n✅ Structured output parsed successfully!")
            print("Generated structure:")
            print(json.dumps(result.completion.model_dump(), indent=2))
            return True
        else:
            print(f"\n❌ Response is not structured: {type(result.completion)}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing structured output: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_raw_llm_response():
    """Test what the LLM actually generates without structured output parsing"""
    
    print("\n" + "="*60)
    print("Testing raw LLM response format...")
    
    try:
        llm = make_local_llm()
        
        messages = [
            SystemMessage(content="""You are a web automation agent. Respond with JSON in this exact format:
{
  "thinking": "your reasoning here",
  "evaluation_previous_goal": "assessment of previous step",
  "memory": "important information",
  "next_goal": "what to do next",
  "action": [
    {
      "type": "go_to_url",
      "url": "https://example.com"
    }
  ]
}

Respond ONLY with the JSON, no additional text."""),
            UserMessage(content="Navigate to example.com")
        ]
        
        print("Sending request for raw JSON response...")
        result = await llm.ainvoke(messages)  # No output_format
        
        print(f"Raw response: {result.completion}")
        
        # Try to parse as JSON
        try:
            parsed = json.loads(result.completion)
            print("\n✅ Response is valid JSON!")
            print("Structure:")
            for key in parsed.keys():
                print(f"  - {key}: {type(parsed[key])}")
            
            # Check if it has 'actions' vs 'action'
            if 'actions' in parsed:
                print("\n⚠️ SCHEMA MISMATCH DETECTED!")
                print("LLM generated 'actions' (plural) but schema expects 'action' (singular)")
                return False, parsed
            elif 'action' in parsed:
                print("\n✅ Schema format is correct ('action' field found)")
                return True, parsed
            else:
                print("\n❌ No action field found in response")
                return False, parsed
                
        except json.JSONDecodeError as e:
            print(f"\n❌ Response is not valid JSON: {e}")
            return False, None
            
    except Exception as e:
        print(f"❌ Error testing raw response: {e}")
        return False, None

async def main():
    print("🔍 SCHEMA COMPATIBILITY TEST")
    print("="*60)
    print("Testing the schema mismatch issue described in roadmap.md")
    print("")
    
    # Test 1: Structured output parsing
    structured_success = await test_structured_output_schema()
    
    # Test 2: Raw response format
    raw_success, raw_data = await test_raw_llm_response()
    
    print("\n" + "="*60)
    print("🎯 TEST RESULTS")
    print("="*60)
    
    print(f"Structured output parsing: {'✅ PASS' if structured_success else '❌ FAIL'}")
    print(f"Raw JSON format: {'✅ PASS' if raw_success else '❌ FAIL'}")
    
    if not structured_success and raw_data:
        print("\n🔧 DIAGNOSIS:")
        if 'actions' in raw_data:
            print("❌ CONFIRMED: LLM generates 'actions' but schema expects 'action'")
            print("❌ This matches the issue described in roadmap.md")
            print("❌ Need to fix deserializer to handle 'actions' -> 'action' conversion")
        else:
            print("❓ Different issue - LLM response format needs investigation")
    
    return structured_success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)