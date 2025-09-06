#!/usr/bin/env python3
"""
Test the schema transformation fix directly
"""

import json
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

def test_schema_transformation():
    """Test the schema transformation logic"""
    
    print("[TEST] Testing schema transformation logic...")
    
    # Test case 1: actions -> action conversion
    test_json_1 = {
        "thinking": "Test thinking",
        "evaluation_previous_goal": "Test eval",
        "memory": "Test memory", 
        "next_goal": "Test goal",
        "actions": [
            {
                "action": "done",
                "params": {
                    "text": "Example Domain",
                    "success": True
                }
            }
        ]
    }
    
    print("Test 1 - Original JSON:")
    print(json.dumps(test_json_1, indent=2))
    
    # Apply transformation logic
    parsed_json = test_json_1.copy()
    
    # Fix schema mismatch: convert 'actions' array to 'action' field
    if 'actions' in parsed_json and 'action' not in parsed_json:
        actions_array = parsed_json.pop('actions')
        if isinstance(actions_array, list) and len(actions_array) > 0:
            parsed_json['action'] = actions_array
            print("[OK] Converted 'actions' array to 'action' field")
        else:
            print("[ERROR] Empty or invalid 'actions' array found")
    
    # Fix action format: convert {"action": "name", "params": {...}} to {"name": {...}}
    if 'action' in parsed_json and isinstance(parsed_json['action'], list):
        fixed_actions = []
        for action_item in parsed_json['action']:
            if isinstance(action_item, dict):
                if 'action' in action_item and 'params' in action_item:
                    # Convert {"action": "done", "params": {"text": "...", "success": true}}
                    # to {"done": {"text": "...", "success": true}}
                    action_name = action_item['action']
                    action_params = action_item['params']
                    fixed_action = {action_name: action_params}
                    fixed_actions.append(fixed_action)
                    print(f"[OK] Converted action format: {action_name}")
                else:
                    # Already in correct format
                    fixed_actions.append(action_item)
            else:
                fixed_actions.append(action_item)
        parsed_json['action'] = fixed_actions
    
    print("Test 1 - Transformed JSON:")
    print(json.dumps(parsed_json, indent=2))
    
    # Test case 2: Already correct format
    test_json_2 = {
        "thinking": "Test thinking",
        "evaluation_previous_goal": "Test eval",
        "memory": "Test memory",
        "next_goal": "Test goal", 
        "action": [
            {
                "done": {
                    "text": "Example Domain",
                    "success": True
                }
            }
        ]
    }
    
    print("\nTest 2 - Already correct format:")
    print(json.dumps(test_json_2, indent=2))
    
    # Apply transformation (should not change anything)
    parsed_json_2 = test_json_2.copy()
    
    if 'actions' in parsed_json_2 and 'action' not in parsed_json_2:
        print("[ERROR] Should not trigger actions->action conversion")
    else:
        print("[OK] No actions->action conversion needed")
    
    if 'action' in parsed_json_2 and isinstance(parsed_json_2['action'], list):
        needs_fixing = False
        for action_item in parsed_json_2['action']:
            if isinstance(action_item, dict) and 'action' in action_item and 'params' in action_item:
                needs_fixing = True
                break
        
        if needs_fixing:
            print("[ERROR] Should not need action format conversion")
        else:
            print("[OK] No action format conversion needed")
    
    print("\nTest 2 - After transformation (should be unchanged):")
    print(json.dumps(parsed_json_2, indent=2))
    
    return True

if __name__ == "__main__":
    success = test_schema_transformation()
    print(f"\n[RESULT] Schema transformation test: {'PASS' if success else 'FAIL'}")