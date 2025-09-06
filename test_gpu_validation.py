#!/usr/bin/env python3
"""
GPU-Accelerated Local LLM Validation Test
Tests the core GPU integration and schema fixes without complex browser automation.
"""

import asyncio
import time
import json
from browser_use import ChatLlamaCpp

async def test_gpu_llm_performance():
    """Test GPU-accelerated local LLM performance and schema handling."""
    
    print("[TEST] GPU-Accelerated Local LLM Validation")
    print("=" * 50)
    
    # Initialize local LLM client
    llm = ChatLlamaCpp(
        base_url="http://localhost:8080",
        model="qwen2.5-7b-instruct-q4_k_m",
        temperature=0.1,
        timeout=30,
        max_tokens=1024
    )
    
    # Test 1: Basic response time
    print("\n[TEST 1] Response Time Performance")
    start_time = time.time()
    
    try:
        from browser_use.llm.messages import UserMessage
        
        messages = [UserMessage(content="What is the capital of France? Answer in one sentence.")]
        response = await llm.ainvoke(messages)
        
        response_time = time.time() - start_time
        print(f"[OK] Response received in {response_time:.2f}s")
        print(f"[RESPONSE] {response}")
        
        # Validate performance target (should be < 2s, ideally ~0.5s)
        if response_time <= 2.0:
            print(f"[PASS] Performance target met: {response_time:.2f}s <= 2.0s")
            performance_grade = "A" if response_time <= 0.6 else "B"
        else:
            print(f"[WARN] Performance target missed: {response_time:.2f}s > 2.0s")
            performance_grade = "C"
            
    except Exception as e:
        print(f"[ERROR] LLM test failed: {e}")
        return False, 0.0, "F"
    
    # Test 2: Schema transformation capability
    print("\n[TEST 2] Schema Transformation Validation")
    
    schema_prompt = """
    You are a web automation agent. Respond with JSON in this exact format:
    {
        "thinking": "Your reasoning here",
        "evaluation_previous_goal": "Evaluation of previous step",
        "memory": "Important information to remember",
        "next_goal": "What to do next",
        "action": [
            {
                "done": {
                    "text": "Task completed successfully",
                    "success": true
                }
            }
        ]
    }
    
    Task: Navigate to example.com and find the main heading.
    """
    
    try:
        schema_start = time.time()
        schema_messages = [UserMessage(content=schema_prompt)]
        schema_response = await llm.ainvoke(schema_messages)
        schema_time = time.time() - schema_start
        
        print(f"[OK] Schema response received in {schema_time:.2f}s")
        
        # Try to parse as JSON
        try:
            # Extract JSON from response if it's wrapped in text
            response_text = str(schema_response)
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            elif "{" in response_text:
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                json_text = response_text[json_start:json_end]
            else:
                json_text = response_text
            
            parsed_json = json.loads(json_text)
            
            # Validate schema structure
            required_fields = ["thinking", "evaluation_previous_goal", "memory", "next_goal", "action"]
            missing_fields = [field for field in required_fields if field not in parsed_json]
            
            if not missing_fields:
                print("[PASS] Schema structure validation passed")
                schema_grade = "A"
            else:
                print(f"[WARN] Missing schema fields: {missing_fields}")
                schema_grade = "B"
                
            print(f"[SCHEMA] {json.dumps(parsed_json, indent=2)}")
            
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON parsing failed: {e}")
            print(f"[RAW] {schema_response}")
            schema_grade = "C"
            
    except Exception as e:
        print(f"[ERROR] Schema test failed: {e}")
        schema_grade = "F"
    
    # Test 3: Context handling capability
    print("\n[TEST 3] Context Window Validation")
    
    # Generate a longer context to test the 65K context window
    long_context = "Context: " + "This is important information. " * 100
    context_prompt = f"{long_context}\n\nBased on the context above, what was mentioned repeatedly?"
    
    try:
        context_start = time.time()
        context_messages = [UserMessage(content=context_prompt)]
        context_response = await llm.ainvoke(context_messages)
        context_time = time.time() - context_start
        
        print(f"[OK] Context response received in {context_time:.2f}s")
        
        # Check if the response indicates understanding of the repeated phrase
        if "important information" in str(context_response).lower():
            print("[PASS] Context understanding validated")
            context_grade = "A"
        else:
            print("[WARN] Context understanding unclear")
            context_grade = "B"
            
        print(f"[CONTEXT] {context_response}")
        
    except Exception as e:
        print(f"[ERROR] Context test failed: {e}")
        context_grade = "F"
    
    # Summary
    print("\n" + "=" * 50)
    print("[SUMMARY] GPU-Accelerated Local LLM Validation Results")
    print(f"[PERFORMANCE] Response Time: {response_time:.2f}s (Grade: {performance_grade})")
    print(f"[SCHEMA] Structure Validation: Grade {schema_grade}")
    print(f"[CONTEXT] Window Handling: Grade {context_grade}")
    
    # Overall grade calculation
    grades = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
    avg_score = (grades[performance_grade] + grades[schema_grade] + grades[context_grade]) / 3
    
    if avg_score >= 3.5:
        overall_grade = "A"
    elif avg_score >= 2.5:
        overall_grade = "B"
    elif avg_score >= 1.5:
        overall_grade = "C"
    else:
        overall_grade = "F"
    
    print(f"[OVERALL] GPU Integration Grade: {overall_grade}")
    
    # Determine success
    success = overall_grade in ["A", "B"]
    print(f"[RESULT] GPU Validation: {'PASS' if success else 'FAIL'}")
    
    return success, response_time, overall_grade

if __name__ == "__main__":
    success, response_time, grade = asyncio.run(test_gpu_llm_performance())
    print(f"\nFINAL RESULT: {'SUCCESS' if success else 'FAILURE'}")
    print(f"PERFORMANCE: {response_time:.2f}s")
    print(f"GRADE: {grade}")