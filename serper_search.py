"""
Serper API Integration with fallback and caching
Implements step 6 from aug22updates roadmap
"""

import asyncio
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
import hashlib

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel

from browser_use import ActionResult

load_dotenv()

# Configuration
SERPER_API_KEY = os.getenv('SERPER_API_KEY')
CACHE_DIR = Path('serper_cache')
CACHE_DIR.mkdir(exist_ok=True)
CACHE_DURATION_HOURS = 24  # Cache results for 24 hours

# Serper API pricing: $5 per 1000 searches
SERPER_COST_PER_SEARCH = 0.005

# Usage tracking
usage_log_file = Path('serper_usage.json')

def log_serper_usage(query: str, num_results: int, cached: bool = False):
    """Log Serper API usage for cost tracking."""
    cost = 0 if cached else SERPER_COST_PER_SEARCH
    
    usage_entry = {
        'timestamp': datetime.now().isoformat(),
        'query': query[:100] + '...' if len(query) > 100 else query,
        'num_results': num_results,
        'cached': cached,
        'cost': cost
    }
    
    try:
        if usage_log_file.exists():
            with open(usage_log_file, 'r', encoding='utf-8') as f:
                usage_data = json.load(f)
        else:
            usage_data = {'searches': [], 'total_cost': 0, 'cached_hits': 0}
        
        usage_data['searches'].append(usage_entry)
        usage_data['total_cost'] += cost
        if cached:
            usage_data['cached_hits'] += 1
        
        with open(usage_log_file, 'w', encoding='utf-8') as f:
            json.dump(usage_data, f, indent=2)
            
    except Exception as e:
        print(f"Warning: Failed to log Serper usage: {e}")

def get_serper_usage_stats() -> dict:
    """Get current Serper API usage statistics."""
    try:
        if usage_log_file.exists():
            with open(usage_log_file, 'r', encoding='utf-8') as f:
                usage_data = json.load(f)
                
            return {
                'total_searches': len(usage_data.get('searches', [])),
                'total_cost': usage_data.get('total_cost', 0),
                'cached_hits': usage_data.get('cached_hits', 0),
                'cache_hit_rate': usage_data.get('cached_hits', 0) / max(len(usage_data.get('searches', [])), 1) * 100
            }
    except:
        pass
    
    return {'total_searches': 0, 'total_cost': 0, 'cached_hits': 0, 'cache_hit_rate': 0}

class SerperSearchResult(BaseModel):
    """Structured search result from Serper API."""
    title: str
    link: str
    snippet: str
    position: Optional[int] = None
    date: Optional[str] = None

class SerperResponse(BaseModel):
    """Complete Serper API response."""
    query: str
    total_results: int
    results: List[SerperSearchResult]
    search_time_seconds: float
    cached: bool = False
    timestamp: str = ""

def get_cache_key(query: str) -> str:
    """Generate cache key from search query."""
    return hashlib.md5(query.lower().strip().encode()).hexdigest()

def get_cached_result(query: str) -> Optional[SerperResponse]:
    """Retrieve cached search result if it exists and is still valid."""
    cache_key = get_cache_key(query)
    cache_file = CACHE_DIR / f"{cache_key}.json"
    
    if not cache_file.exists():
        return None
    
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cached_data = json.load(f)
        
        # Check if cache is expired
        cached_time = datetime.fromisoformat(cached_data['timestamp'])
        if datetime.now() - cached_time > timedelta(hours=CACHE_DURATION_HOURS):
            cache_file.unlink()  # Remove expired cache
            return None
        
        cached_data['cached'] = True
        return SerperResponse(**cached_data)
    
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        # Invalid cache file, remove it
        if cache_file.exists():
            cache_file.unlink()
        return None

def save_to_cache(query: str, response: SerperResponse):
    """Save search result to cache."""
    cache_key = get_cache_key(query)
    cache_file = CACHE_DIR / f"{cache_key}.json"
    
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(response.model_dump(), f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: Failed to save cache for query '{query}': {e}")

async def serper_search_api(query: str, num_results: int = 10) -> Optional[SerperResponse]:
    """
    Search using Serper API with async HTTP client.
    
    Args:
        query: Search query string
        num_results: Number of results to return (max 100)
        
    Returns:
        SerperResponse object or None if API fails
    """
    if not SERPER_API_KEY:
        print("Warning: SERPER_API_KEY not found in environment variables")
        return None
    
    # Check cache first
    cached_result = get_cached_result(query)
    if cached_result:
        # Log cached usage
        log_serper_usage(query, num_results, cached=True)
        print(f"✅ Using cached result for query: {query}")
        return cached_result
    
    start_time = time.time()
    
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                'q': query,
                'num': min(num_results, 100)  # Serper API max is 100
            }
            
            headers = {
                'X-API-KEY': SERPER_API_KEY,
                'Content-Type': 'application/json'
            }
            
            response = await client.post(
                'https://google.serper.dev/search',
                json=payload,
                headers=headers,
                timeout=10.0
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Parse organic results
            organic_results = data.get('organic', [])
            results = []
            
            for idx, result in enumerate(organic_results):
                results.append(SerperSearchResult(
                    title=result.get('title', ''),
                    link=result.get('link', ''),
                    snippet=result.get('snippet', ''),
                    position=result.get('position', idx + 1),
                    date=result.get('date')
                ))
            
            search_time = time.time() - start_time
            
            serper_response = SerperResponse(
                query=query,
                total_results=len(results),
                results=results,
                search_time_seconds=round(search_time, 2),
                timestamp=datetime.now().isoformat()
            )
            
            # Save to cache
            save_to_cache(query, serper_response)
            
            # Log usage for cost tracking
            log_serper_usage(query, num_results, cached=False)
            
            print(f"✅ Serper API search completed: {len(results)} results in {search_time:.2f}s")
            return serper_response
            
    except httpx.TimeoutException:
        print(f"⚠️ Serper API timeout for query: {query}")
        return None
    except httpx.HTTPStatusError as e:
        print(f"⚠️ Serper API HTTP error {e.response.status_code} for query: {query}")
        return None
    except Exception as e:
        print(f"⚠️ Serper API error for query '{query}': {e}")
        return None

async def search_with_serper_fallback(controller, query: str, num_results: int = 10) -> ActionResult:
    """
    Search using Serper API with browser fallback.
    
    This is the main function to be used as a custom action in browser-use.
    
    Args:
        controller: Browser-use controller instance (for fallback)
        query: Search query string
        num_results: Number of results to return
        
    Returns:
        ActionResult with search results
    """
    print(f"🔍 Searching with Serper API: {query}")
    
    # Try Serper API first
    serper_result = await serper_search_api(query, num_results)
    
    if serper_result and serper_result.results:
        # Format results for the LLM
        results_text = f"Search Results for '{query}' ({serper_result.total_results} results):\n\n"
        
        for i, result in enumerate(serper_result.results[:num_results], 1):
            results_text += f"{i}. **{result.title}**\n"
            results_text += f"   URL: {result.link}\n"
            results_text += f"   Summary: {result.snippet}\n"
            if result.date:
                results_text += f"   Date: {result.date}\n"
            results_text += "\n"
        
        if serper_result.cached:
            results_text += f"\n*Note: Results retrieved from cache*\n"
        else:
            results_text += f"\n*Search completed in {serper_result.search_time_seconds}s*\n"
        
        return ActionResult(
            extracted_content=results_text,
            include_in_memory=True,
            include_extracted_content_only_once=True
        )
    
    else:
        # Fallback to browser search
        print("⚠️ Serper API failed, falling back to browser search...")
        
        try:
            # Navigate to Google and perform search
            await controller.page.goto('https://www.google.com')
            await controller.page.wait_for_load_state('networkidle')
            
            # Find and fill search box
            search_box = controller.page.locator('input[name="q"], textarea[name="q"]')
            await search_box.fill(query)
            await search_box.press('Enter')
            
            # Wait for results
            await controller.page.wait_for_load_state('networkidle')
            
            # Extract search results
            results = await controller.page.locator('div[data-ved] h3, .g h3').all()
            links = await controller.page.locator('div[data-ved] a, .g a').all()
            snippets = await controller.page.locator('div[data-ved] .VwiC3b, .g .VwiC3b, div[data-ved] span:has-text(" "), .g .s').all()
            
            results_text = f"Search Results for '{query}' (Browser fallback):\n\n"
            
            for i in range(min(len(results), num_results)):
                try:
                    title = await results[i].inner_text() if i < len(results) else "No title"
                    link = await links[i].get_attribute('href') if i < len(links) else "No link"
                    snippet = await snippets[i].inner_text() if i < len(snippets) else "No snippet"
                    
                    results_text += f"{i+1}. **{title}**\n"
                    results_text += f"   URL: {link}\n"
                    results_text += f"   Summary: {snippet[:200]}...\n\n"
                except:
                    continue
            
            results_text += f"\n*Note: Results from browser fallback due to API failure*\n"
            
            return ActionResult(
                extracted_content=results_text,
                include_in_memory=True,
                include_extracted_content_only_once=True
            )
            
        except Exception as e:
            error_msg = f"❌ Both Serper API and browser fallback failed for query '{query}': {e}"
            print(error_msg)
            return ActionResult(
                extracted_content=error_msg,
                include_in_memory=True,
                include_extracted_content_only_once=True
            )

# For standalone testing
async def main():
    """Test the Serper search functionality."""
    query = "latest developments in AI 2024"
    print(f"Testing Serper search with query: {query}")
    
    result = await serper_search_api(query, 5)
    if result:
        print(f"\nFound {result.total_results} results:")
        for i, r in enumerate(result.results, 1):
            print(f"{i}. {r.title}")
            print(f"   {r.link}")
            print(f"   {r.snippet[:100]}...")
            print()
    else:
        print("Search failed")

if __name__ == '__main__':
    asyncio.run(main())