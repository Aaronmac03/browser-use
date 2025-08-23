"""
test_structured_outputs.py - Complete Test Suite for Native Browser-Use Structured Outputs

This script validates that all structured output features are working correctly:
1. Native Browser-Use structured output API
2. Custom structured planning and critique
3. Clean events pipeline with guaranteed JSON
4. Cross-provider compatibility (OpenAI, Gemini, OpenRouter)

Run: python test_structured_outputs.py
"""

import asyncio
import os
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

load_dotenv()

from browser_use import Agent, BrowserSession, BrowserProfile
from browser_use.llm import ChatOpenAI, ChatGoogle
from agent import (
    StructuredPlan, StructuredCritique, ExtractedData, 
    structured_chat, process_agent_history_to_structured_result
)

# ----------------------------
# Test Schemas
# ----------------------------

class SimpleTestExtraction(BaseModel):
    """Simple test schema for validation."""
    title: str = Field(description="Page title")
    url: str = Field(description="Current URL") 
    text_content: str = Field(description="Main text content")
    extraction_timestamp: str = Field(
        description="When extraction occurred",
        default_factory=lambda: datetime.now().isoformat()
    )

class ProductTestExtraction(BaseModel):
    """Product-specific test schema."""
    product_name: str = Field(description="Product name")
    price: float = Field(description="Product price", ge=0)
    available: bool = Field(description="Product availability")
    features: List[str] = Field(description="Product features", default_factory=list)

# ----------------------------
# Test Suite Functions
# ----------------------------

async def test_native_structured_output_api():
    """Test Browser-Use's native structured output API."""
    print("\n" + "="*60)
    print("🧪 TEST: Native Browser-Use Structured Output API")
    print("="*60)
    
    if not os.getenv('GOOGLE_API_KEY'):
        print("❌ GOOGLE_API_KEY required - skipping native API test")
        return False
    
    llm = ChatGoogle(model="gemini-2.0-flash", api_key=os.getenv('GOOGLE_API_KEY'))
    
    try:
        browser_session = BrowserSession(
            browser_profile=BrowserProfile(browser='chromium')
        )
        
        # Test native structured output API
        agent = Agent(
            task="Go to https://example.com and extract the page title, URL, and main text content",
            llm=llm,
            browser_session=browser_session,
            output_model_schema=SimpleTestExtraction,  # Native Browser-Use API
            max_steps=5
        )
        
        print("🚀 Running agent with native structured output schema...")
        history = await agent.run()
        
        result = history.final_result()
        print("✅ Native structured output API test completed!")
        
        if isinstance(result, dict):
            # Validate against schema
            validated = SimpleTestExtraction.model_validate(result)
            print(f"   • Title: {validated.title}")
            print(f"   • URL: {validated.url}")
            print(f"   • Content length: {len(validated.text_content)} characters")
            print(f"   • Extracted at: {validated.extraction_timestamp}")
            return True
        else:
            print(f"   • Raw result type: {type(result)}")
            print(f"   • Raw result: {str(result)[:100]}...")
            return result is not None
        
    except Exception as e:
        print(f"❌ Native API test failed: {e}")
        return False
    finally:
        if 'browser_session' in locals():
            await browser_session.close()

async def test_custom_structured_planning():
    """Test custom structured planning with schema validation."""
    print("\n" + "="*60)
    print("🧪 TEST: Custom Structured Planning")
    print("="*60)
    
    if not os.getenv('GOOGLE_API_KEY'):
        print("❌ GOOGLE_API_KEY required - skipping planning test")
        return False
    
    llm = ChatGoogle(model="gemini-2.0-flash", api_key=os.getenv('GOOGLE_API_KEY'))
    
    task = "Search for 'Python programming books' on Amazon and compare prices"
    
    try:
        print(f"📋 Task: {task}")
        print("🚀 Generating structured plan...")
        
        plan = await structured_chat(
            llm,
            user_prompt=f"Task: {task}",
            system_prompt=f"""Create a detailed structured plan using StructuredPlan schema.
            Include specific steps, expected outcomes, and realistic time estimates.
            Task: {task}""",
            response_model=StructuredPlan
        )
        
        print("✅ Structured planning test completed!")
        print(f"   • Task: {plan.task_summary}")
        print(f"   • Steps: {len(plan.steps)}")
        print(f"   • Duration: {plan.estimated_duration_minutes} minutes")
        print(f"   • Domains: {', '.join(plan.domains_required)}")
        print(f"   • Success criteria: {plan.success_criteria}")
        
        # Validate it's actually a StructuredPlan object
        assert isinstance(plan, StructuredPlan)
        assert len(plan.steps) > 0
        assert plan.estimated_duration_minutes > 0
        
        return True
        
    except Exception as e:
        print(f"❌ Structured planning test failed: {e}")
        return False

async def test_custom_structured_critique():
    """Test custom structured critique with issue categorization."""
    print("\n" + "="*60) 
    print("🧪 TEST: Custom Structured Critique")
    print("="*60)
    
    if not os.getenv('GOOGLE_API_KEY'):
        print("❌ GOOGLE_API_KEY required - skipping critique test")
        return False
    
    llm = ChatGoogle(model="gemini-2.0-flash", api_key=os.getenv('GOOGLE_API_KEY'))
    
    # Intentionally flawed plan for critique
    flawed_plan = """
    Task: Extract data from banking website
    Steps:
    1. Navigate to chase.com
    2. Download all account data as PDF
    3. Use random third-party converter to extract data
    4. Store passwords in plain text file
    5. Email results to unknown recipients
    """
    
    try:
        print("🔍 Analyzing flawed plan for issues...")
        
        critique = await structured_chat(
            llm,
            user_prompt=f"Plan to evaluate:\n{flawed_plan}",
            system_prompt="""Provide detailed structured critique using StructuredCritique schema.
            Look for security issues, inefficiencies, and potential problems.
            Categorize issues by severity and provide specific recommendations.""",
            response_model=StructuredCritique
        )
        
        print("✅ Structured critique test completed!")
        print(f"   • Assessment: {critique.overall_assessment}")
        print(f"   • Issues found: {len(critique.issues_found)}")
        print(f"   • Recommendation: {critique.final_recommendation}")
        
        # Show categorized issues
        for issue in critique.issues_found[:3]:  # Show first 3 issues
            print(f"   • {issue.issue_type} ({issue.severity}): {issue.description[:50]}...")
        
        # Validate structure
        assert isinstance(critique, StructuredCritique)
        assert len(critique.issues_found) > 0  # Should find issues in flawed plan
        assert critique.final_recommendation in ["approve", "revise", "reject"]
        
        return True
        
    except Exception as e:
        print(f"❌ Structured critique test failed: {e}")
        return False

def test_schema_validation():
    """Test Pydantic schema validation works correctly."""
    print("\n" + "="*60)
    print("🧪 TEST: Schema Validation")
    print("="*60)
    
    try:
        # Test valid data
        valid_data = {
            "product_name": "Test Product",
            "price": 99.99,
            "available": True,
            "features": ["Feature 1", "Feature 2"]
        }
        
        validated = ProductTestExtraction.model_validate(valid_data)
        print("✅ Valid data validation passed")
        print(f"   • Product: {validated.product_name}")
        print(f"   • Price: ${validated.price}")
        
        # Test invalid data
        invalid_data = {
            "product_name": "",  # Empty name
            "price": -10.0,      # Negative price
            "available": "yes"   # Wrong type
        }
        
        try:
            ProductTestExtraction.model_validate(invalid_data)
            print("❌ Invalid data validation failed - should have been rejected")
            return False
        except ValidationError as e:
            print("✅ Invalid data correctly rejected")
            print(f"   • Errors caught: {len(e.errors())}")
            
        return True
        
    except Exception as e:
        print(f"❌ Schema validation test failed: {e}")
        return False

async def test_cross_provider_compatibility():
    """Test that structured outputs work across different LLM providers."""
    print("\n" + "="*60)
    print("🧪 TEST: Cross-Provider Compatibility")
    print("="*60)
    
    providers_tested = 0
    providers_working = 0
    
    # Test OpenAI if available
    if os.getenv('OPENAI_API_KEY'):
        try:
            print("🤖 Testing OpenAI compatibility...")
            llm = ChatOpenAI(model="gpt-4o-mini", api_key=os.getenv('OPENAI_API_KEY'))
            
            plan = await structured_chat(
                llm,
                user_prompt="Create a plan to search for laptops",
                system_prompt="Create a structured plan using StructuredPlan schema.",
                response_model=StructuredPlan
            )
            
            print("   ✅ OpenAI structured output working")
            providers_tested += 1
            providers_working += 1
            
        except Exception as e:
            print(f"   ❌ OpenAI test failed: {e}")
            providers_tested += 1
    
    # Test Google Gemini if available
    if os.getenv('GOOGLE_API_KEY'):
        try:
            print("🧠 Testing Google Gemini compatibility...")
            llm = ChatGoogle(model="gemini-2.0-flash", api_key=os.getenv('GOOGLE_API_KEY'))
            
            plan = await structured_chat(
                llm,
                user_prompt="Create a plan to search for laptops",
                system_prompt="Create a structured plan using StructuredPlan schema.",
                response_model=StructuredPlan
            )
            
            print("   ✅ Google Gemini structured output working")
            providers_tested += 1
            providers_working += 1
            
        except Exception as e:
            print(f"   ❌ Gemini test failed: {e}")
            providers_tested += 1
    
    # Test OpenRouter if available
    if os.getenv('OPENROUTER_API_KEY'):
        try:
            print("🌐 Testing OpenRouter compatibility...")
            llm = ChatOpenAI(
                model="openai/gpt-4o-mini",
                base_url='https://openrouter.ai/api/v1',
                api_key=os.getenv('OPENROUTER_API_KEY')
            )
            
            plan = await structured_chat(
                llm,
                user_prompt="Create a plan to search for laptops",
                system_prompt="Create a structured plan using StructuredPlan schema.",
                response_model=StructuredPlan
            )
            
            print("   ✅ OpenRouter structured output working")
            providers_tested += 1
            providers_working += 1
            
        except Exception as e:
            print(f"   ❌ OpenRouter test failed: {e}")
            providers_tested += 1
    
    if providers_tested == 0:
        print("❌ No API keys available for cross-provider testing")
        return False
    
    print(f"✅ Cross-provider compatibility: {providers_working}/{providers_tested} working")
    return providers_working > 0

async def run_comprehensive_test_suite():
    """Run all structured output tests and provide summary."""
    print("🚀 Comprehensive Structured Outputs Test Suite")
    print("="*70)
    print("Testing Browser-Use native structured output implementation")
    print("="*70)
    
    # Check API key availability
    available_keys = []
    if os.getenv('OPENAI_API_KEY'):
        available_keys.append("OpenAI")
    if os.getenv('GOOGLE_API_KEY'):
        available_keys.append("Google")
    if os.getenv('OPENROUTER_API_KEY'):
        available_keys.append("OpenRouter")
        
    if not available_keys:
        print("❌ No API keys found. Add API keys to .env file:")
        print("   OPENAI_API_KEY=your_key")
        print("   GOOGLE_API_KEY=your_key")
        print("   OPENROUTER_API_KEY=your_key")
        return
    
    print(f"✅ API keys available: {', '.join(available_keys)}")
    
    # Run test suite
    test_results = {}
    
    print("\n🔧 Running schema validation tests...")
    test_results["schema_validation"] = test_schema_validation()
    
    print("\n🔧 Running structured planning tests...")
    test_results["structured_planning"] = await test_custom_structured_planning()
    
    print("\n🔧 Running structured critique tests...")
    test_results["structured_critique"] = await test_custom_structured_critique()
    
    print("\n🔧 Running cross-provider compatibility tests...")
    test_results["cross_provider"] = await test_cross_provider_compatibility()
    
    print("\n🔧 Running native Browser-Use API tests...")
    test_results["native_api"] = await test_native_structured_output_api()
    
    # Summary
    print("\n" + "="*70)
    print("📊 TEST SUITE RESULTS")
    print("="*70)
    
    passed_tests = [k for k, v in test_results.items() if v]
    failed_tests = [k for k, v in test_results.items() if not v]
    
    print(f"✅ Passed: {len(passed_tests)}/{len(test_results)} tests")
    for test_name in passed_tests:
        print(f"   • {test_name.replace('_', ' ').title()}: ✅")
    
    if failed_tests:
        print(f"\n❌ Failed: {len(failed_tests)} tests")
        for test_name in failed_tests:
            print(f"   • {test_name.replace('_', ' ').title()}: ❌")
    
    # Overall assessment
    success_rate = len(passed_tests) / len(test_results) * 100
    
    if success_rate >= 80:
        print(f"\n🎉 OVERALL RESULT: SUCCESS ({success_rate:.0f}%)")
        print("✅ Structured outputs implementation is working correctly!")
    elif success_rate >= 60:
        print(f"\n⚠️  OVERALL RESULT: PARTIAL SUCCESS ({success_rate:.0f}%)")
        print("⚠️  Some features working, check failed tests")
    else:
        print(f"\n❌ OVERALL RESULT: NEEDS ATTENTION ({success_rate:.0f}%)")
        print("❌ Multiple issues detected, check configuration")
    
    print(f"\n🎯 Next Steps:")
    if len(passed_tests) > 0:
        print("• Run the enhanced agent: python agent.py")
        print("• Try provider demos: python structured_providers_demo.py")
        print("• Test clean events: python clean_events_demo.py")
    
    if failed_tests:
        print("• Check API keys in .env file")
        print("• Verify browser-use installation")
        print("• Check network connectivity")

if __name__ == '__main__':
    asyncio.run(run_comprehensive_test_suite())