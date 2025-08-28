#!/usr/bin/env python3
"""
Example usage of the Browser Agent system.

This script demonstrates how to use the various components of the browser agent
for different types of tasks and scenarios.
"""

import asyncio
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def example_model_selection():
    """Example of intelligent model selection based on task requirements."""
    print("\n=== Model Selection Example ===")
    
    from config.models import ModelConfigManager, TaskComplexity
    from models.model_router import ModelRouter, TaskRequirements, RoutingStrategy
    from models.cloud_handler import CloudModelManager, BudgetManager, ResponseCache
    
    # Initialize components
    model_config_manager = ModelConfigManager()
    budget_manager = BudgetManager(daily_limit=10.0)  # Low limit for demo
    cache = ResponseCache()
    
    # Initialize cloud manager (you'll need API keys in .env)
    cloud_manager = CloudModelManager(
        budget_manager=budget_manager,
        cache=cache
    )
    
    # Initialize model router
    router = ModelRouter(
        model_config_manager=model_config_manager,
        cloud_manager=cloud_manager,
        default_strategy=RoutingStrategy.COST_OPTIMIZED
    )
    
    # Example 1: Simple web navigation task
    simple_task = TaskRequirements(
        complexity=TaskComplexity.SIMPLE,
        requires_vision=False,
        max_cost=0.01  # Very low cost requirement
    )
    
    try:
        model = await router.select_model(simple_task)
        print(f"✓ Selected for simple task: {model.name} ({model.provider.value})")
    except Exception as e:
        print(f"✗ Simple task selection failed: {e}")
    
    # Example 2: Complex task with vision
    complex_task = TaskRequirements(
        complexity=TaskComplexity.COMPLEX,
        requires_vision=True,
        max_response_time=30.0
    )
    
    try:
        model = await router.select_model(complex_task, RoutingStrategy.QUALITY_OPTIMIZED)
        print(f"✓ Selected for complex vision task: {model.name}")
    except Exception as e:
        print(f"✗ Complex task selection failed: {e}")
    
    # Show routing statistics
    stats = router.get_routing_stats()
    print(f"Total routing decisions: {stats.get('total_routing_decisions', 0)}")
    
    await cloud_manager.close()


async def example_browser_profiles():
    """Example of browser profile management."""
    print("\n=== Browser Profile Management Example ===")
    
    from config.profiles import BrowserProfileManager, ProfileType, SecurityLevel
    
    # Initialize profile manager
    profile_manager = BrowserProfileManager()
    
    # Create a custom profile for e-commerce
    try:
        ecommerce_profile = profile_manager.create_profile(
            name="shopping",
            profile_type=ProfileType.ECOMMERCE,
            security_level=SecurityLevel.MEDIUM,
            description="Profile optimized for online shopping",
            custom_settings={"headless": False}  # Show browser for shopping
        )
        print(f"✓ Created shopping profile: {ecommerce_profile.name}")
    except ValueError as e:
        print(f"Profile already exists: {e}")
    
    # List all profiles
    profiles = profile_manager.list_profiles()
    print(f"Available profiles: {[p.name for p in profiles]}")
    
    # Get browser configuration for a profile
    try:
        config = profile_manager.get_browser_config("shopping")
        print(f"Shopping profile config: headless={config['headless']}")
        print(f"Security args: {len(config['args'])} arguments")
    except ValueError as e:
        print(f"Profile not found: {e}")


async def example_security_features():
    """Example of security features."""
    print("\n=== Security Features Example ===")
    
    from utils.security import SecurityManager
    
    # Initialize security manager
    security_manager = SecurityManager()
    
    # Test URLs with different risk levels
    test_urls = [
        "https://amazon.com",
        "https://suspicious-domain.tk",
        "https://github.com",
        "https://phishing-site-example.com",
        "https://legitimate-bank.com"
    ]
    
    print("URL Security Analysis:")
    for url in test_urls:
        validation = security_manager.validate_and_log_url_access(
            url, 
            user_id="example_user", 
            session_id="demo_session"
        )
        
        status_icon = {
            "ALLOW": "✓",
            "CAUTION": "⚠",
            "WARN": "⚠",
            "BLOCK": "✗"
        }.get(validation["recommendation"], "?")
        
        print(f"  {status_icon} {url}")
        print(f"    Risk: {validation['risk_score']:.2f}, Action: {validation['recommendation']}")
        
        if validation.get("suspicious_reasons"):
            print(f"    Reasons: {', '.join(validation['suspicious_reasons'])}")
    
    # Store and retrieve credentials securely
    print("\nCredential Management:")
    try:
        # Store a test credential
        security_manager.credential_manager.store_credential(
            service="test_service",
            credential_type="api_key",
            value="test_key_12345",
            metadata={"created_by": "example_script"}
        )
        print("✓ Stored test credential")
        
        # Retrieve the credential
        retrieved = security_manager.get_secure_credential(
            service="test_service",
            credential_type="api_key",
            user_id="example_user"
        )
        print(f"✓ Retrieved credential: {retrieved[:8]}..." if retrieved else "✗ Failed to retrieve")
        
    except Exception as e:
        print(f"✗ Credential management failed: {e}")
    
    security_manager.close()


async def example_search_integration():
    """Example of search API integration."""
    print("\n=== Search Integration Example ===")
    
    import os
    from utils.serper import SerperAPI, SearchFilters, SearchType
    
    # Check if Serper API key is available
    serper_key = os.getenv("SERPER_API_KEY")
    if not serper_key:
        print("✗ Serper API key not found in environment variables")
        print("  Set SERPER_API_KEY to test search functionality")
        return
    
    async with SerperAPI(serper_key) as search_api:
        try:
            # Perform a web search
            filters = SearchFilters(num_results=5, language="en")
            response = await search_api.web_search("browser automation python", filters)
            
            print(f"✓ Found {len(response.results)} search results")
            
            # Show top results
            for i, result in enumerate(response.results[:3], 1):
                print(f"  {i}. {result.title}")
                print(f"     {result.link}")
                print(f"     {result.snippet[:100]}...")
            
            # Extract key information
            key_info = search_api.extract_key_information(response, max_results=3)
            if key_info["summary"]:
                print(f"\nSummary: {key_info['summary'][:200]}...")
            
            # Show related searches
            if key_info["related_topics"]:
                print(f"Related topics: {', '.join(key_info['related_topics'][:3])}")
            
        except Exception as e:
            print(f"✗ Search failed: {e}")


async def example_complete_workflow():
    """Example of a complete workflow using multiple components."""
    print("\n=== Complete Workflow Example ===")
    
    from config.models import ModelConfigManager, TaskComplexity
    from config.profiles import BrowserProfileManager, ProfileType, SecurityLevel
    from models.model_router import ModelRouter, TaskRequirements, RoutingStrategy
    from utils.security import SecurityManager
    
    # Initialize all components
    model_config_manager = ModelConfigManager()
    profile_manager = BrowserProfileManager()
    security_manager = SecurityManager()
    
    router = ModelRouter(
        model_config_manager=model_config_manager,
        default_strategy=RoutingStrategy.BALANCED
    )
    
    print("Simulating a complete browser automation workflow...")
    
    # Step 1: Security check for target URL
    target_url = "https://example.com"
    validation = security_manager.validate_and_log_url_access(
        target_url, 
        user_id="workflow_user", 
        session_id="workflow_123"
    )
    
    if validation["recommendation"] == "BLOCK":
        print(f"✗ Workflow stopped: URL {target_url} is blocked")
        return
    
    print(f"✓ URL validation passed: {target_url}")
    
    # Step 2: Select appropriate browser profile
    profile = profile_manager.get_profile("default")
    if not profile:
        print("✗ No suitable browser profile found")
        return
    
    print(f"✓ Selected browser profile: {profile.name}")
    
    # Step 3: Select appropriate model for the task
    task_requirements = TaskRequirements(
        complexity=TaskComplexity.MODERATE,
        requires_vision=True,
        max_response_time=60.0
    )
    
    try:
        selected_model = await router.select_model(task_requirements)
        print(f"✓ Selected model: {selected_model.name} ({selected_model.provider.value})")
    except Exception as e:
        print(f"✗ Model selection failed: {e}")
        return
    
    # Step 4: Get browser configuration
    browser_config = profile_manager.get_browser_config(profile.name)
    print(f"✓ Browser configuration ready (headless: {browser_config['headless']})")
    
    # Step 5: Simulate task execution
    print("✓ Workflow completed successfully!")
    print("  - Security validation: PASSED")
    print("  - Browser profile: CONFIGURED")
    print("  - Model selection: COMPLETED")
    print("  - Ready for browser automation")
    
    security_manager.close()


async def main():
    """Run all examples."""
    print("Browser Agent - Usage Examples")
    print("=" * 50)
    
    try:
        await example_model_selection()
        await example_browser_profiles()
        await example_security_features()
        await example_search_integration()
        await example_complete_workflow()
        
        print("\n" + "=" * 50)
        print("All examples completed successfully!")
        print("\nTo use the browser agent in your own projects:")
        print("1. Set up your API keys in .env file")
        print("2. Import the required components")
        print("3. Initialize the managers and routers")
        print("4. Use the components as shown in these examples")
        
    except Exception as e:
        print(f"\nExample execution failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())