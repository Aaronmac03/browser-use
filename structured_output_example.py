"""
structured_output_example.py - Demonstration of Browser-Use with Structured Outputs

This example shows how the enhanced agent.py enforces JSON schemas at every step:
1. Structured plans with detailed steps and fallbacks
2. Structured critiques with issue categorization
3. Structured data extraction with confidence scores
4. Structured execution events with success tracking

Run: python structured_output_example.py
"""

import asyncio
import os
import json
from datetime import datetime

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

load_dotenv()

# Import the structured schemas from the enhanced agent
from agent import (
    StructuredPlan, StructuredCritique, ExtractedData, StructuredExecutionResult,
    structured_chat, process_agent_history_to_structured_result
)
from browser_use import Agent, BrowserProfile, BrowserSession, Controller
from browser_use.llm import ChatGoogle, SystemMessage, UserMessage

# Example structured output schemas for specific use cases
class ProductInfo(BaseModel):
    """Structured schema for e-commerce product data."""
    name: str = Field(description="Product name")
    price: float = Field(description="Product price in USD")
    rating: float = Field(description="Average rating (0-5 scale)", ge=0, le=5)
    reviews_count: int = Field(description="Number of reviews")
    availability: str = Field(description="Stock status")
    features: list[str] = Field(description="Key product features")
    image_url: str = Field(description="Product image URL", default="")

class NewsArticle(BaseModel):
    """Structured schema for news articles."""
    title: str = Field(description="Article headline")
    summary: str = Field(description="Brief article summary", max_length=500)
    url: str = Field(description="Article URL")
    published_date: str = Field(description="Publication date")
    author: str = Field(description="Article author", default="")
    category: str = Field(description="News category", default="")

class NewsCollection(BaseModel):
    """Collection of news articles."""
    articles: list[NewsArticle] = Field(description="List of news articles")
    source_site: str = Field(description="Source website")
    collection_date: str = Field(description="When articles were collected", default_factory=lambda: datetime.now().isoformat())

async def demonstrate_structured_planning():
    """Show how structured planning works with detailed schemas."""
    print("\n" + "="*60)
    print("🎯 DEMONSTRATION: Structured Planning")
    print("="*60)
    
    # Initialize LLM (using Google Gemini as example)
    llm = ChatGoogle(model="gemini-2.0-flash", api_key=os.getenv('GOOGLE_API_KEY'))
    
    task = "Find the top 3 tech news stories from TechCrunch and extract structured data about each"
    
    try:
        # Generate structured plan
        print("📋 Generating structured plan...")
        plan = await structured_chat(
            llm,
            user_prompt=f"Task: {task}",
            system_prompt="""Create a detailed structured plan using StructuredPlan schema.
            
            Include specific steps, expected outcomes, fallback strategies, and accurate time estimates.
            Consider potential issues like popups, rate limiting, and navigation changes.""",
            response_model=StructuredPlan
        )
        
        print(f"✅ Plan generated successfully!")
        print(f"   • Task: {plan.task_summary}")
        print(f"   • Steps: {len(plan.steps)}")
        print(f"   • Estimated time: {plan.estimated_duration_minutes} minutes")
        print(f"   • Domains: {', '.join(plan.domains_required)}")
        print(f"   • Success criteria: {plan.success_criteria}")
        
        print("\n📝 Detailed Steps:")
        for step in plan.steps:
            print(f"   {step.step_number}. {step.action}")
            print(f"      Expected: {step.expected_outcome}")
            if step.fallback_strategy:
                print(f"      Fallback: {step.fallback_strategy}")
        
        return plan
        
    except Exception as e:
        print(f"❌ Structured planning failed: {e}")
        return None

async def demonstrate_structured_critique():
    """Show how structured critique provides detailed issue analysis."""
    print("\n" + "="*60)
    print("🔍 DEMONSTRATION: Structured Critique")
    print("="*60)
    
    llm = ChatGoogle(model="gemini-2.0-flash", api_key=os.getenv('GOOGLE_API_KEY'))
    
    # Sample plan to critique (with intentional issues)
    sample_plan = """
    Task: Extract product data from Amazon
    Steps:
    1. Go to amazon.com and search for "laptops"
    2. Click on the first result
    3. Download the product page as PDF
    4. Use a third-party converter to extract data
    5. Email the results
    """
    
    try:
        print("🔍 Analyzing plan for issues...")
        critique = await structured_chat(
            llm,
            user_prompt=f"Plan to evaluate:\n{sample_plan}",
            system_prompt="""Provide detailed structured critique using StructuredCritique schema.
            
            Look for security issues, inefficiencies, unnecessary steps, and potential failure points.
            Categorize issues by type and severity, provide specific recommendations.""",
            response_model=StructuredCritique
        )
        
        print(f"✅ Critique completed!")
        print(f"   • Overall assessment: {critique.overall_assessment}")
        print(f"   • Issues found: {len(critique.issues_found)}")
        print(f"   • Final recommendation: {critique.final_recommendation}")
        
        print(f"\n🚨 Issues Identified:")
        for issue in critique.issues_found:
            severity_emoji = {"low": "🟡", "medium": "🟠", "high": "🔴", "critical": "💀"}.get(issue.severity, "❓")
            print(f"   {severity_emoji} {issue.issue_type.upper()} ({issue.severity})")
            print(f"      Problem: {issue.description}")
            print(f"      Solution: {issue.recommendation}")
        
        print(f"\n✅ Strengths:")
        for strength in critique.strengths:
            print(f"   • {strength}")
            
        return critique
        
    except Exception as e:
        print(f"❌ Structured critique failed: {e}")
        return None

async def demonstrate_structured_extraction():
    """Show structured data extraction with custom schemas."""
    print("\n" + "="*60)
    print("📊 DEMONSTRATION: Structured Data Extraction")
    print("="*60)
    
    # Example of how to set up structured extraction for specific data types
    print("🔧 Setting up structured extraction controllers...")
    
    # Controller for product extraction
    product_controller = Controller()
    product_controller.use_structured_output_action(ProductInfo)
    print("   ✅ Product extraction controller configured")
    
    # Controller for news extraction
    news_controller = Controller()
    news_controller.use_structured_output_action(NewsCollection)
    print("   ✅ News extraction controller configured")
    
    # Example of structured data validation
    print("\n📋 Example structured data validation...")
    
    # Mock extracted data
    sample_product_data = {
        "name": "MacBook Pro 16-inch",
        "price": 2499.0,
        "rating": 4.5,
        "reviews_count": 1250,
        "availability": "In Stock",
        "features": ["M3 Max chip", "32GB RAM", "1TB SSD", "Retina Display"],
        "image_url": "https://example.com/macbook.jpg"
    }
    
    try:
        # Validate against schema
        validated_product = ProductInfo.model_validate(sample_product_data)
        print("   ✅ Product data validation successful!")
        print(f"      Product: {validated_product.name}")
        print(f"      Price: ${validated_product.price}")
        print(f"      Rating: {validated_product.rating}/5 ({validated_product.reviews_count} reviews)")
        print(f"      Features: {len(validated_product.features)} features listed")
        
    except ValidationError as e:
        print(f"   ❌ Validation failed: {e}")
    
    return product_controller, news_controller

def demonstrate_structured_logging():
    """Show how structured results are logged."""
    print("\n" + "="*60)
    print("📝 DEMONSTRATION: Structured Logging Format")
    print("="*60)
    
    # Example structured execution result
    sample_extracted_data = ExtractedData(
        data_type="table",
        content={
            "headers": ["Product", "Price", "Rating"],
            "rows": [
                ["MacBook Pro", "$2499", "4.5/5"],
                ["Dell XPS", "$1899", "4.3/5"],
                ["HP Spectre", "$1599", "4.1/5"]
            ]
        },
        confidence=0.92,
        source_url="https://example.com/laptops"
    )
    
    sample_events = [
        {
            "step_number": 1,
            "action_taken": "NavigateToUrl",
            "result": "Successfully navigated to shopping site",
            "success": True,
            "extracted_data": None
        },
        {
            "step_number": 2,
            "action_taken": "ExtractStructuredData",
            "result": "Extracted product comparison table",
            "success": True,
            "extracted_data": sample_extracted_data.model_dump()
        }
    ]
    
    print("📊 Structured Log Entry Example:")
    print("```markdown")
    print("## Structured Execution Result")
    print(f"**Task Completed:** True")
    print(f"**Success Rate:** 100.0%")
    print(f"**Summary:** Successfully extracted product data from shopping site")
    print()
    print("## Extracted Data")
    print(f"**Data Type:** {sample_extracted_data.data_type}")
    print(f"**Confidence:** {sample_extracted_data.confidence}")
    print(f"**Source:** {sample_extracted_data.source_url}")
    print("**Content:**")
    print("```json")
    print(json.dumps(sample_extracted_data.content, indent=2))
    print("```")
    print()
    print("## Execution Events")
    for event in sample_events:
        print(f"- Step {event['step_number']}: {event['action_taken']}")
        print(f"  Result: {event['result']}")
        print(f"  Success: {'✅' if event['success'] else '❌'}")
        if event['extracted_data']:
            print(f"  Data Type: {event['extracted_data']['data_type']}")
        print()
    print("```")

async def main():
    """Run all structured output demonstrations."""
    print("🚀 Browser-Use Structured Output Demonstration")
    print("="*70)
    print("This demo shows how structured outputs eliminate ambiguity and")
    print("provide clean, parseable JSON at every step of the pipeline.")
    
    # Check for required API keys
    if not os.getenv('GOOGLE_API_KEY'):
        print("❌ Missing GOOGLE_API_KEY environment variable")
        print("   Add your Google AI API key to .env file")
        return
    
    try:
        # Run demonstrations
        await demonstrate_structured_planning()
        await demonstrate_structured_critique()
        await demonstrate_structured_extraction()
        demonstrate_structured_logging()
        
        print("\n" + "="*70)
        print("✅ STRUCTURED OUTPUT DEMONSTRATION COMPLETE")
        print("="*70)
        print("Key Benefits:")
        print("• 🎯 Eliminates ambiguous LLM responses")
        print("• 📊 Forces clean JSON schemas for all data")
        print("• 🔄 Auto-retry on invalid responses")
        print("• 🏗️  Modular schemas for different data types")
        print("• 📝 Rich structured logging with confidence scores")
        print("• 🔍 Detailed critique with issue categorization")
        print("• ⚡ Massive reduction in parsing errors and 'thrash'")
        
        print(f"\n💡 To use: python agent.py")
        print("   The enhanced agent automatically applies these patterns!")
        
    except KeyboardInterrupt:
        print("\n❌ Demonstration interrupted by user")
    except Exception as e:
        print(f"\n❌ Demonstration failed: {e}")

if __name__ == '__main__':
    asyncio.run(main())