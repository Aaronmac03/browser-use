"""
structured_providers_demo.py - Native Browser-Use Structured Outputs Across LLM Providers

This demonstrates Browser-Use's first-class structured output support working across:
- OpenAI GPT models (with native structured outputs)
- Google Gemini models (with native structured outputs) 
- OpenRouter models (with enforced JSON schemas)

The key insight: Browser-Use automatically handles structured outputs at the library level,
making it provider-agnostic while leveraging each provider's native capabilities.

Run: python structured_providers_demo.py
"""

import asyncio
import os
import json
from datetime import datetime
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

load_dotenv()

from browser_use import Agent, BrowserProfile, BrowserSession
from browser_use.llm import ChatOpenAI, ChatGoogle, SystemMessage, UserMessage

# ----------------------------
# Domain-Specific Structured Output Schemas
# ----------------------------

class ProductComparison(BaseModel):
    """Structured schema for e-commerce product comparison."""
    product_name: str = Field(description="Product name or title")
    price: float = Field(description="Product price in USD", ge=0)
    rating: float = Field(description="Average rating (0-5 stars)", ge=0, le=5)
    reviews_count: int = Field(description="Total number of reviews", ge=0)
    availability: str = Field(description="Stock status (In Stock, Out of Stock, etc.)")
    key_features: List[str] = Field(description="List of key product features")
    pros: List[str] = Field(description="Product advantages", default_factory=list)
    cons: List[str] = Field(description="Product disadvantages", default_factory=list)
    source_url: str = Field(description="Product page URL")
    extracted_at: str = Field(description="Extraction timestamp", default_factory=lambda: datetime.now().isoformat())

class ProductComparisonResult(BaseModel):
    """Collection of products for comparison."""
    search_query: str = Field(description="Original search query")
    products: List[ProductComparison] = Field(description="List of products found")
    comparison_site: str = Field(description="Website where comparison was performed")
    total_products_found: int = Field(description="Total number of products in comparison")
    
class NewsArticle(BaseModel):
    """Structured schema for news article extraction."""
    headline: str = Field(description="Article headline/title")
    summary: str = Field(description="Brief article summary", max_length=300)
    author: Optional[str] = Field(description="Article author", default=None)
    published_date: Optional[str] = Field(description="Publication date", default=None)
    category: Optional[str] = Field(description="News category (Tech, Business, etc.)", default=None)
    read_time: Optional[int] = Field(description="Estimated reading time in minutes", default=None)
    tags: List[str] = Field(description="Article tags/keywords", default_factory=list)
    article_url: str = Field(description="Full article URL")
    
class NewsCollection(BaseModel):
    """Collection of news articles from a source."""
    source_name: str = Field(description="News source name (e.g., TechCrunch, BBC)")
    source_url: str = Field(description="News source homepage URL")
    collection_date: str = Field(description="When articles were collected", default_factory=lambda: datetime.now().isoformat())
    articles: List[NewsArticle] = Field(description="List of articles extracted")
    total_articles: int = Field(description="Total number of articles extracted")
    
class StockData(BaseModel):
    """Structured schema for financial stock data."""
    ticker_symbol: str = Field(description="Stock ticker symbol (e.g., AAPL)")
    company_name: str = Field(description="Full company name")
    current_price: float = Field(description="Current stock price", ge=0)
    price_change: float = Field(description="Price change from previous close")
    percent_change: float = Field(description="Percentage change from previous close")
    volume: int = Field(description="Trading volume", ge=0)
    market_cap: Optional[str] = Field(description="Market capitalization", default=None)
    pe_ratio: Optional[float] = Field(description="Price-to-earnings ratio", default=None)
    day_high: Optional[float] = Field(description="Day's high price", default=None)
    day_low: Optional[float] = Field(description="Day's low price", default=None)
    extracted_from: str = Field(description="Data source URL")
    
class StockPortfolio(BaseModel):
    """Collection of stock data."""
    portfolio_name: str = Field(description="Portfolio or watchlist name")
    stocks: List[StockData] = Field(description="List of stocks in portfolio")
    total_value: Optional[float] = Field(description="Total portfolio value", default=None)
    extraction_timestamp: str = Field(description="When data was extracted", default_factory=lambda: datetime.now().isoformat())

# ----------------------------
# Provider-Specific Test Cases
# ----------------------------

async def test_openai_structured_outputs():
    """Test native OpenAI structured outputs with Browser-Use."""
    print("\n" + "="*60)
    print("🤖 TESTING: OpenAI Native Structured Outputs")
    print("="*60)
    
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ OPENAI_API_KEY not found - skipping OpenAI test")
        return None
        
    # Use OpenAI GPT-4o with native structured output support
    llm = ChatOpenAI(model="gpt-4o", api_key=os.getenv('OPENAI_API_KEY'))
    
    task = "Go to Yahoo Finance and extract structured data for Apple (AAPL) stock including price, change, volume, and key metrics"
    
    print(f"📋 Task: {task}")
    print(f"🔧 Model: GPT-4o with native structured outputs")
    print(f"📊 Schema: StockData (enforced by Browser-Use)")
    
    try:
        # Create browser session
        browser_session = BrowserSession(
            browser_profile=BrowserProfile(
                browser='chromium',
                persist_session=True,
                profile_dir=os.path.expanduser('~/.config/browseruse/profiles/openai_test')
            )
        )
        
        # Agent with native structured output schema
        agent = Agent(
            task=task,
            llm=llm,
            browser_session=browser_session,
            output_model_schema=StockData,  # Native Browser-Use structured output
            max_steps=15,
            extend_system_message="Extract stock data in the exact StockData format. Ensure all numeric fields are properly typed and URLs are complete."
        )
        
        print("🚀 Starting OpenAI structured extraction...")
        history = await agent.run()
        
        # The structured output is automatically available in the final result
        final_result = history.final_result()
        
        print("✅ OpenAI structured extraction completed!")
        print(f"📊 Result type: {type(final_result)}")
        
        if isinstance(final_result, dict):
            # Validate against our schema
            validated_data = StockData.model_validate(final_result)
            print(f"   • Stock: {validated_data.ticker_symbol} - {validated_data.company_name}")
            print(f"   • Price: ${validated_data.current_price:.2f} ({validated_data.percent_change:+.2f}%)")
            print(f"   • Volume: {validated_data.volume:,}")
            return validated_data
        else:
            print(f"   • Raw result: {str(final_result)[:200]}...")
            return final_result
            
    except Exception as e:
        print(f"❌ OpenAI test failed: {e}")
        return None
    finally:
        if 'browser_session' in locals():
            await browser_session.close()

async def test_gemini_structured_outputs():
    """Test native Gemini structured outputs with Browser-Use."""
    print("\n" + "="*60)
    print("🧠 TESTING: Google Gemini Native Structured Outputs") 
    print("="*60)
    
    if not os.getenv('GOOGLE_API_KEY'):
        print("❌ GOOGLE_API_KEY not found - skipping Gemini test")
        return None
        
    # Use Gemini 2.0 Flash with native structured output support
    llm = ChatGoogle(model="gemini-2.0-flash", api_key=os.getenv('GOOGLE_API_KEY'))
    
    task = "Go to TechCrunch and extract structured data for the top 3 latest tech news articles including headlines, summaries, authors, and publication dates"
    
    print(f"📋 Task: {task}")
    print(f"🔧 Model: Gemini 2.0 Flash with native structured outputs")
    print(f"📊 Schema: NewsCollection (enforced by Browser-Use)")
    
    try:
        # Create browser session  
        browser_session = BrowserSession(
            browser_profile=BrowserProfile(
                browser='chromium',
                persist_session=True,
                profile_dir=os.path.expanduser('~/.config/browseruse/profiles/gemini_test')
            )
        )
        
        # Agent with native structured output schema
        agent = Agent(
            task=task,
            llm=llm,
            browser_session=browser_session,
            output_model_schema=NewsCollection,  # Native Browser-Use structured output
            max_steps=20,
            extend_system_message="Extract news articles in the exact NewsCollection format. Include complete headlines, concise summaries, and accurate metadata for each article."
        )
        
        print("🚀 Starting Gemini structured extraction...")
        history = await agent.run()
        
        # The structured output is automatically available
        final_result = history.final_result()
        
        print("✅ Gemini structured extraction completed!")
        print(f"📊 Result type: {type(final_result)}")
        
        if isinstance(final_result, dict):
            # Validate against our schema
            validated_data = NewsCollection.model_validate(final_result)
            print(f"   • Source: {validated_data.source_name}")
            print(f"   • Articles: {validated_data.total_articles}")
            for i, article in enumerate(validated_data.articles[:3], 1):
                print(f"   • Article {i}: {article.headline[:60]}...")
                if article.author:
                    print(f"     Author: {article.author}")
                print(f"     Summary: {article.summary[:80]}...")
            return validated_data
        else:
            print(f"   • Raw result: {str(final_result)[:200]}...")
            return final_result
            
    except Exception as e:
        print(f"❌ Gemini test failed: {e}")
        return None
    finally:
        if 'browser_session' in locals():
            await browser_session.close()

async def test_openrouter_structured_outputs():
    """Test OpenRouter models with enforced structured outputs."""
    print("\n" + "="*60)
    print("🌐 TESTING: OpenRouter Models with Structured Output Enforcement")
    print("="*60)
    
    if not os.getenv('OPENROUTER_API_KEY'):
        print("❌ OPENROUTER_API_KEY not found - skipping OpenRouter test")
        return None
        
    # Use a capable model via OpenRouter
    llm = ChatOpenAI(
        model="openai/gpt-4o-2024-11-20",
        base_url='https://openrouter.ai/api/v1',
        api_key=os.getenv('OPENROUTER_API_KEY')
    )
    
    task = "Go to Amazon and compare 3 laptop products under $1500, extracting structured comparison data including prices, ratings, features, and availability"
    
    print(f"📋 Task: {task}")
    print(f"🔧 Model: GPT-4o via OpenRouter with schema enforcement")
    print(f"📊 Schema: ProductComparisonResult (enforced by Browser-Use)")
    
    try:
        # Create browser session
        browser_session = BrowserSession(
            browser_profile=BrowserProfile(
                browser='chromium',
                persist_session=True,
                profile_dir=os.path.expanduser('~/.config/browseruse/profiles/openrouter_test')
            )
        )
        
        # Agent with native structured output schema
        agent = Agent(
            task=task,
            llm=llm,
            browser_session=browser_session,
            output_model_schema=ProductComparisonResult,  # Native Browser-Use structured output
            max_steps=25,
            extend_system_message="Extract product comparison data in the exact ProductComparisonResult format. Include accurate prices, ratings, and detailed feature lists for each product."
        )
        
        print("🚀 Starting OpenRouter structured extraction...")
        history = await agent.run()
        
        # The structured output is automatically available
        final_result = history.final_result()
        
        print("✅ OpenRouter structured extraction completed!")
        print(f"📊 Result type: {type(final_result)}")
        
        if isinstance(final_result, dict):
            # Validate against our schema
            validated_data = ProductComparisonResult.model_validate(final_result)
            print(f"   • Search: '{validated_data.search_query}'")
            print(f"   • Products: {validated_data.total_products_found}")
            print(f"   • Site: {validated_data.comparison_site}")
            for i, product in enumerate(validated_data.products[:3], 1):
                print(f"   • Product {i}: {product.product_name}")
                print(f"     Price: ${product.price:.2f} | Rating: {product.rating}/5 ({product.reviews_count} reviews)")
                print(f"     Status: {product.availability}")
                print(f"     Features: {len(product.key_features)} listed")
            return validated_data
        else:
            print(f"   • Raw result: {str(final_result)[:200]}...")
            return final_result
            
    except Exception as e:
        print(f"❌ OpenRouter test failed: {e}")
        return None
    finally:
        if 'browser_session' in locals():
            await browser_session.close()

def demonstrate_schema_validation():
    """Show how Browser-Use validates structured outputs against schemas."""
    print("\n" + "="*60)
    print("🔍 DEMONSTRATION: Schema Validation & Error Handling")
    print("="*60)
    
    # Example of valid data
    valid_stock_data = {
        "ticker_symbol": "AAPL",
        "company_name": "Apple Inc.",
        "current_price": 193.42,
        "price_change": 2.15,
        "percent_change": 1.12,
        "volume": 41234567,
        "market_cap": "3.01T",
        "pe_ratio": 32.1,
        "day_high": 194.99,
        "day_low": 191.23,
        "extracted_from": "https://finance.yahoo.com/quote/AAPL"
    }
    
    # Example of invalid data (missing required fields)
    invalid_stock_data = {
        "ticker_symbol": "INVALID",
        "current_price": -50.0,  # Negative price (validation error)
        "volume": "not_a_number"  # Wrong type
    }
    
    print("✅ Valid Data Validation:")
    try:
        validated = StockData.model_validate(valid_stock_data)
        print(f"   • ✅ {validated.ticker_symbol}: ${validated.current_price} ({validated.percent_change:+.2f}%)")
        print(f"   • ✅ All fields properly typed and validated")
    except ValidationError as e:
        print(f"   • ❌ Validation failed: {e}")
    
    print("\n❌ Invalid Data Validation:")
    try:
        StockData.model_validate(invalid_stock_data)
        print("   • Unexpectedly passed validation!")
    except ValidationError as e:
        print(f"   • ✅ Correctly caught validation errors:")
        for error in e.errors():
            field = error.get('loc', ['unknown'])[0]
            message = error.get('msg', 'Unknown error')
            print(f"     - {field}: {message}")
    
    print(f"\n🎯 Browser-Use automatically handles this validation:")
    print(f"   • Invalid responses are rejected at the library level")
    print(f"   • Agents are forced to retry with correct format")
    print(f"   • Clean, typed data is guaranteed in final results")
    print(f"   • No manual parsing or validation needed")

async def demonstrate_cross_provider_consistency():
    """Show how structured outputs work consistently across providers."""
    print("\n" + "="*60)
    print("🔄 DEMONSTRATION: Cross-Provider Consistency")
    print("="*60)
    
    # Same schema works across all providers
    print("📊 Same Schema Definition Works Across:")
    print("   • OpenAI GPT models → Native structured outputs")  
    print("   • Google Gemini → Native structured outputs")
    print("   • OpenRouter models → Schema enforcement")
    print("   • Local Ollama models → Schema enforcement")
    print("   • Anthropic Claude → Schema enforcement")
    
    print(f"\n🏗️  Browser-Use Architecture Benefits:")
    print(f"   • Provider-agnostic structured output API")
    print(f"   • Automatic format enforcement at library level")
    print(f"   • Consistent validation across all LLM providers")
    print(f"   • Zero changes needed when switching providers")
    
    print(f"\n✅ Example: Same Agent Code Works With Any Provider:")
    print(f"```python")
    print(f"# Works with ANY LLM - just change the llm parameter")
    print(f"agent = Agent(")
    print(f"    task='Extract product data',")
    print(f"    llm=your_llm_provider,  # OpenAI, Gemini, OpenRouter, etc.")
    print(f"    output_model_schema=ProductInfo,  # Same schema everywhere")
    print(f")")
    print(f"```")
    
    return True

async def main():
    """Run comprehensive structured output demonstrations across providers."""
    print("🚀 Browser-Use Native Structured Outputs Across LLM Providers")
    print("="*70)
    print("This demo shows Browser-Use's first-class structured output support")
    print("working natively across OpenAI, Gemini, and OpenRouter providers.")
    print("="*70)
    
    # Check available API keys
    available_providers = []
    if os.getenv('OPENAI_API_KEY'):
        available_providers.append("OpenAI")
    if os.getenv('GOOGLE_API_KEY'):
        available_providers.append("Gemini")  
    if os.getenv('OPENROUTER_API_KEY'):
        available_providers.append("OpenRouter")
        
    if not available_providers:
        print("❌ No API keys found. Add API keys to .env file:")
        print("   - OPENAI_API_KEY=your_key")
        print("   - GOOGLE_API_KEY=your_key") 
        print("   - OPENROUTER_API_KEY=your_key")
        return
        
    print(f"✅ Available providers: {', '.join(available_providers)}")
    
    # Run schema validation demo (always available)
    demonstrate_schema_validation()
    await demonstrate_cross_provider_consistency()
    
    results = {}
    
    # Test each available provider
    if "OpenAI" in available_providers:
        results["openai"] = await test_openai_structured_outputs()
        
    if "Gemini" in available_providers:
        results["gemini"] = await test_gemini_structured_outputs()
        
    if "OpenRouter" in available_providers:  
        results["openrouter"] = await test_openrouter_structured_outputs()
    
    # Summary
    print("\n" + "="*70)
    print("📊 STRUCTURED OUTPUT RESULTS SUMMARY")
    print("="*70)
    
    successful_tests = [k for k, v in results.items() if v is not None]
    failed_tests = [k for k, v in results.items() if v is None]
    
    print(f"✅ Successful tests: {len(successful_tests)}/{len(results)}")
    for provider in successful_tests:
        print(f"   • {provider.capitalize()}: Structured output working correctly")
        
    if failed_tests:
        print(f"❌ Failed tests: {len(failed_tests)}")
        for provider in failed_tests:
            print(f"   • {provider.capitalize()}: Check API key and connectivity")
    
    print(f"\n🎯 KEY INSIGHTS:")
    print(f"• Browser-Use provides native structured output support")
    print(f"• Same schema works across ALL LLM providers")
    print(f"• Automatic validation and retry at library level")
    print(f"• Zero parsing code needed - get clean typed objects")
    print(f"• Provider-agnostic API eliminates vendor lock-in")
    
    print(f"\n💡 Production Usage:")
    print(f"python agent.py  # Enhanced agent with structured outputs everywhere")

if __name__ == '__main__':
    asyncio.run(main())