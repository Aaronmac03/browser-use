#!/usr/bin/env python3
"""
Debug the actual action schema being used
"""

import json
import sys
from pathlib import Path

# Add browser-use to path
sys.path.insert(0, str(Path(__file__).parent))

def debug_action_schema():
    """Debug the action schema"""
    
    print("🔍 Debugging action schema...")
    
    try:
        from browser_use.tools.views import ClickElementAction, DoneAction
        
        print("ClickElementAction schema:")
        click_schema = ClickElementAction.model_json_schema()
        print(json.dumps(click_schema, indent=2))
        
        print("\nDoneAction schema:")
        done_schema = DoneAction.model_json_schema()
        print(json.dumps(done_schema, indent=2))
        
        # Test creating instances
        print("\nTesting ClickElementAction creation:")
        try:
            click_action = ClickElementAction(index=1)
            print(f"✅ Created: {click_action}")
            print(f"JSON: {click_action.model_dump()}")
        except Exception as e:
            print(f"❌ Failed: {e}")
        
        print("\nTesting DoneAction creation:")
        try:
            done_action = DoneAction(text="Example Domain", success=True)
            print(f"✅ Created: {done_action}")
            print(f"JSON: {done_action.model_dump()}")
        except Exception as e:
            print(f"❌ Failed: {e}")
            
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = debug_action_schema()
    print(f"\n🎯 Schema debug: {'✅ PASS' if success else '❌ FAIL'}")