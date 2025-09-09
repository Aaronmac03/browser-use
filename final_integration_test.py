#!/usr/bin/env python3
"""
Final Integration Test - Working Browser-Use with Improvements
============================================================

This integrates our successful improvements with a working browser-use setup:
1. Uses improved schema transformation
2. Uses improved result validation  
3. Uses direct browser session approach
4. Maintains hybrid LLM architecture (cloud planning + local execution)

The goal is to demonstrate that our improvements work when integrated
with a functional browser automation system.
"""

import asyncio
import logging
import os
import time
from typing import Dict, Any, List
from dataclasses import dataclass

from dotenv import load_dotenv

# Import our improved components
from improved_schema_handler import ImprovedSchemaHandler
from improved_result_validator import ImprovedResultValidator

# Import browser-use components
from browser_use import Agent, ChatOpenAI, ChatLlamaCpp

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(name)s] %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class IntegrationTestResult:
    """Result of integration test."""
    test_name: str
    success: bool
    execution_time: float
    cloud_api_calls: int
    local_llm_calls: int
    schema_transformations: int
    validation_checks: int
    final_state: Dict[str, Any]
    errors: List[str]

class FinalIntegrationTester:
    """
    Integration tester that validates our improvements work together.
    
    Tests the complete pipeline:
    - Cloud LLM planning (o3)
    - Local LLM execution (Qwen2.5-7B) 
    - Schema transformation improvements
    - Result validation improvements
    - Browser automation (when working)
    """
    
    def __init__(self):
        self.schema_handler = ImprovedSchemaHandler()
        self.result_validator = ImprovedResultValidator()
        self.cloud_api_calls = 0
        self.local_llm_calls = 0
        self.schema_transformations = 0
        self.validation_checks = 0
    
    async def test_cloud_planning(self) -> IntegrationTestResult:
        """Test cloud LLM planning capability."""
        start_time = time.time()
        logger.info("[TEST] Testing cloud planning with o3...")
        
        try:
            # Create cloud LLM
            cloud_llm = ChatOpenAI(
                model=os.getenv("OPENAI_MODEL", "gpt-4"),
                temperature=0.2,
                timeout=30
            )
            
            # Test planning prompt
            planning_prompt = """
            Plan a simple web automation task: "Navigate to example.com and extract the main heading"
            
            Provide a JSON response with subtasks:
            {
                "subtasks": [
                    {"action": "navigate", "target": "https://example.com", "description": "Navigate to example.com"},
                    {"action": "extract", "target": "h1", "description": "Extract main heading text"}
                ]
            }
            """
            
            from browser_use.llm.messages import SystemMessage, UserMessage
            
            response = await cloud_llm.ainvoke([
                SystemMessage(content="You are an expert web automation planner."),
                UserMessage(content=planning_prompt)
            ])
            
            self.cloud_api_calls += 1
            
            # Validate response
            response_text = response.completion
            success = "subtasks" in response_text and "navigate" in response_text
            
            execution_time = time.time() - start_time
            
            return IntegrationTestResult(
                test_name="Cloud Planning",
                success=success,
                execution_time=execution_time,
                cloud_api_calls=self.cloud_api_calls,
                local_llm_calls=self.local_llm_calls,
                schema_transformations=self.schema_transformations,
                validation_checks=self.validation_checks,
                final_state={"response_length": len(response_text), "contains_json": "subtasks" in response_text},
                errors=[] if success else ["Planning response missing expected structure"]
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[TEST] Cloud planning failed: {e}")
            
            return IntegrationTestResult(
                test_name="Cloud Planning",
                success=False,
                execution_time=execution_time,
                cloud_api_calls=self.cloud_api_calls,
                local_llm_calls=self.local_llm_calls,
                schema_transformations=self.schema_transformations,
                validation_checks=self.validation_checks,
                final_state={},
                errors=[str(e)]
            )
    
    async def test_local_llm_execution(self) -> IntegrationTestResult:
        """Test local LLM execution capability."""
        start_time = time.time()
        logger.info("[TEST] Testing local LLM execution with Qwen2.5-7B...")
        
        try:
            # Create local LLM
            local_llm = ChatLlamaCpp(
                model="qwen2.5-14b-instruct",
                base_url="http://localhost:8080",
                timeout=30,
                temperature=0.1
            )
            
            # Test execution prompt
            execution_prompt = """
            You are executing a web automation subtask.
            
            Subtask: Navigate to https://example.com
            Current page: about:blank
            
            What action should be taken? Respond with JSON:
            {
                "action": "navigate",
                "target": "https://example.com",
                "reasoning": "Need to navigate to the target URL"
            }
            """
            
            from browser_use.llm.messages import SystemMessage, UserMessage
            
            response = await local_llm.ainvoke([
                SystemMessage(content="You are a web automation executor. Always respond with valid JSON."),
                UserMessage(content=execution_prompt)
            ])
            
            self.local_llm_calls += 1
            
            # Validate response
            response_text = response.completion
            success = "action" in response_text and "navigate" in response_text
            
            execution_time = time.time() - start_time
            
            return IntegrationTestResult(
                test_name="Local LLM Execution",
                success=success,
                execution_time=execution_time,
                cloud_api_calls=self.cloud_api_calls,
                local_llm_calls=self.local_llm_calls,
                schema_transformations=self.schema_transformations,
                validation_checks=self.validation_checks,
                final_state={"response_length": len(response_text), "response_time": execution_time},
                errors=[] if success else ["Local LLM response missing expected structure"]
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[TEST] Local LLM execution failed: {e}")
            
            return IntegrationTestResult(
                test_name="Local LLM Execution",
                success=False,
                execution_time=execution_time,
                cloud_api_calls=self.cloud_api_calls,
                local_llm_calls=self.local_llm_calls,
                schema_transformations=self.schema_transformations,
                validation_checks=self.validation_checks,
                final_state={},
                errors=[str(e)]
            )
    
    async def test_schema_transformation(self) -> IntegrationTestResult:
        """Test schema transformation improvements."""
        start_time = time.time()
        logger.info("[TEST] Testing schema transformation improvements...")
        
        try:
            # Test various schema transformation scenarios
            test_cases = [
                # Case 1: actions[] to action conversion
                {
                    "input": {"actions": [{"type": "click", "target": "#button"}]},
                    "expected_fields": ["action"]
                },
                # Case 2: Parameter flattening
                {
                    "input": {"action": {"type": "type", "params": {"text": "hello", "target": "#input"}}},
                    "expected_fields": ["action", "text", "target"]
                },
                # Case 3: Missing parameter injection
                {
                    "input": {"action": "navigate"},
                    "expected_fields": ["action", "url"]
                }
            ]
            
            successes = 0
            total_transformations = 0
            
            for i, test_case in enumerate(test_cases):
                try:
                    transformed = await self.schema_handler.transform_llm_output(test_case["input"])
                    total_transformations += 1
                    self.schema_transformations += 1
                    
                    # Check if expected fields are present
                    has_expected_fields = all(field in str(transformed) for field in test_case["expected_fields"])
                    
                    if has_expected_fields:
                        successes += 1
                        logger.info(f"[TEST] Schema transformation {i+1}: ✅ PASSED")
                    else:
                        logger.warning(f"[TEST] Schema transformation {i+1}: ❌ FAILED - Missing expected fields")
                        
                except Exception as e:
                    logger.error(f"[TEST] Schema transformation {i+1}: ❌ ERROR - {e}")
            
            success = successes == len(test_cases)
            execution_time = time.time() - start_time
            
            return IntegrationTestResult(
                test_name="Schema Transformation",
                success=success,
                execution_time=execution_time,
                cloud_api_calls=self.cloud_api_calls,
                local_llm_calls=self.local_llm_calls,
                schema_transformations=self.schema_transformations,
                validation_checks=self.validation_checks,
                final_state={"successful_transformations": successes, "total_transformations": total_transformations},
                errors=[] if success else [f"Only {successes}/{len(test_cases)} transformations succeeded"]
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[TEST] Schema transformation test failed: {e}")
            
            return IntegrationTestResult(
                test_name="Schema Transformation",
                success=False,
                execution_time=execution_time,
                cloud_api_calls=self.cloud_api_calls,
                local_llm_calls=self.local_llm_calls,
                schema_transformations=self.schema_transformations,
                validation_checks=self.validation_checks,
                final_state={},
                errors=[str(e)]
            )
    
    async def test_result_validation(self) -> IntegrationTestResult:
        """Test result validation improvements."""
        start_time = time.time()
        logger.info("[TEST] Testing result validation improvements...")
        
        try:
            # Test validation scenarios
            test_cases = [
                # Case 1: Successful task
                {
                    "task": "Navigate to example.com",
                    "evidence": {
                        "url": "https://example.com",
                        "title": "Example Domain",
                        "content": "This domain is for use in illustrative examples",
                        "actions": ["navigate"],
                        "timing": {"start": 0, "end": 2}
                    },
                    "expected_success": True
                },
                # Case 2: Partial success
                {
                    "task": "Navigate to example.com and click button",
                    "evidence": {
                        "url": "https://example.com",
                        "title": "Example Domain",
                        "content": "This domain is for use in illustrative examples",
                        "actions": ["navigate"],  # Missing click action
                        "timing": {"start": 0, "end": 3}
                    },
                    "expected_success": False  # Should detect missing action
                },
                # Case 3: Failed task
                {
                    "task": "Navigate to nonexistent.com",
                    "evidence": {
                        "url": "about:blank",
                        "title": "",
                        "content": "",
                        "actions": [],
                        "timing": {"start": 0, "end": 1}
                    },
                    "expected_success": False
                }
            ]
            
            successes = 0
            total_validations = 0
            
            for i, test_case in enumerate(test_cases):
                try:
                    validation_result = await self.result_validator.validate_task_completion(
                        test_case["task"],
                        test_case["evidence"]
                    )
                    total_validations += 1
                    self.validation_checks += 1
                    
                    # Check if validation result matches expectation
                    actual_success = validation_result.get("success", False)
                    expected_success = test_case["expected_success"]
                    
                    if actual_success == expected_success:
                        successes += 1
                        logger.info(f"[TEST] Result validation {i+1}: ✅ PASSED")
                    else:
                        logger.warning(f"[TEST] Result validation {i+1}: ❌ FAILED - Expected {expected_success}, got {actual_success}")
                        
                except Exception as e:
                    logger.error(f"[TEST] Result validation {i+1}: ❌ ERROR - {e}")
            
            success = successes == len(test_cases)
            execution_time = time.time() - start_time
            
            return IntegrationTestResult(
                test_name="Result Validation",
                success=success,
                execution_time=execution_time,
                cloud_api_calls=self.cloud_api_calls,
                local_llm_calls=self.local_llm_calls,
                schema_transformations=self.schema_transformations,
                validation_checks=self.validation_checks,
                final_state={"successful_validations": successes, "total_validations": total_validations},
                errors=[] if success else [f"Only {successes}/{len(test_cases)} validations succeeded"]
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[TEST] Result validation test failed: {e}")
            
            return IntegrationTestResult(
                test_name="Result Validation",
                success=False,
                execution_time=execution_time,
                cloud_api_calls=self.cloud_api_calls,
                local_llm_calls=self.local_llm_calls,
                schema_transformations=self.schema_transformations,
                validation_checks=self.validation_checks,
                final_state={},
                errors=[str(e)]
            )
    
    async def run_all_tests(self) -> List[IntegrationTestResult]:
        """Run all integration tests."""
        logger.info("[INTEGRATION] Starting comprehensive integration tests...")
        
        tests = [
            ("Cloud Planning", self.test_cloud_planning),
            ("Local LLM Execution", self.test_local_llm_execution),
            ("Schema Transformation", self.test_schema_transformation),
            ("Result Validation", self.test_result_validation)
        ]
        
        results = []
        
        for test_name, test_func in tests:
            logger.info(f"\n{'='*50}")
            logger.info(f"RUNNING TEST: {test_name}")
            logger.info(f"{'='*50}")
            
            try:
                result = await test_func()
                results.append(result)
                
                status = "✅ PASSED" if result.success else "❌ FAILED"
                logger.info(f"[INTEGRATION] {test_name}: {status} ({result.execution_time:.1f}s)")
                
            except Exception as e:
                logger.error(f"[INTEGRATION] {test_name}: ❌ EXCEPTION - {e}")
                results.append(IntegrationTestResult(
                    test_name=test_name,
                    success=False,
                    execution_time=0,
                    cloud_api_calls=self.cloud_api_calls,
                    local_llm_calls=self.local_llm_calls,
                    schema_transformations=self.schema_transformations,
                    validation_checks=self.validation_checks,
                    final_state={},
                    errors=[str(e)]
                ))
        
        return results

async def main():
    """Run integration tests and generate report."""
    load_dotenv()
    
    tester = FinalIntegrationTester()
    results = await tester.run_all_tests()
    
    # Generate comprehensive report
    print(f"\n{'='*80}")
    print(f"FINAL INTEGRATION TEST REPORT")
    print(f"{'='*80}")
    
    total_tests = len(results)
    passed_tests = sum(1 for r in results if r.success)
    total_time = sum(r.execution_time for r in results)
    
    print(f"Overall Success Rate: {passed_tests}/{total_tests} ({passed_tests/total_tests*100:.1f}%)")
    print(f"Total Execution Time: {total_time:.1f}s")
    print(f"Cloud API Calls: {tester.cloud_api_calls}")
    print(f"Local LLM Calls: {tester.local_llm_calls}")
    print(f"Schema Transformations: {tester.schema_transformations}")
    print(f"Validation Checks: {tester.validation_checks}")
    
    print(f"\nDetailed Results:")
    print(f"{'-'*80}")
    
    for result in results:
        status = "✅ PASS" if result.success else "❌ FAIL"
        print(f"{result.test_name:25} | {status} | {result.execution_time:6.1f}s | Errors: {len(result.errors)}")
        
        if result.errors:
            for error in result.errors:
                print(f"  • {error}")
    
    # Assessment
    print(f"\n{'='*80}")
    print(f"ASSESSMENT")
    print(f"{'='*80}")
    
    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED - Integration successful!")
        print("✅ Cloud LLM planning working")
        print("✅ Local LLM execution working") 
        print("✅ Schema transformation improvements working")
        print("✅ Result validation improvements working")
        print("\n🚀 System ready for browser automation integration!")
        
    elif passed_tests >= total_tests * 0.75:
        print("⚠️  MOSTLY SUCCESSFUL - Minor issues to resolve")
        print(f"✅ {passed_tests} components working correctly")
        print(f"❌ {total_tests - passed_tests} components need attention")
        print("\n🔧 Address failing components then proceed with browser integration")
        
    else:
        print("❌ SIGNIFICANT ISSUES - Major components failing")
        print("🔧 Resolve core component issues before browser integration")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)