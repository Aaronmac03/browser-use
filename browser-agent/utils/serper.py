"""
Serper API integration for search functionality.

This module provides the SerperAPI class for integrating with Serper's search API,
supporting different search types including web, news, images, and places search.
"""

import asyncio
import logging
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, Field


class SearchType(str, Enum):
    """Supported search types."""
    WEB = "search"
    NEWS = "news"
    IMAGES = "images"
    VIDEOS = "videos"
    PLACES = "places"
    SHOPPING = "shopping"


class SearchLocation(str, Enum):
    """Common search locations."""
    UNITED_STATES = "us"
    UNITED_KINGDOM = "uk"
    CANADA = "ca"
    AUSTRALIA = "au"
    GERMANY = "de"
    FRANCE = "fr"
    JAPAN = "jp"
    GLOBAL = ""


@dataclass
class SearchResult:
    """Individual search result."""
    title: str
    link: str
    snippet: str
    position: int
    date: Optional[str] = None
    source: Optional[str] = None
    thumbnail: Optional[str] = None
    price: Optional[str] = None
    rating: Optional[float] = None
    additional_data: Optional[Dict[str, Any]] = None


@dataclass
class SearchResponse:
    """Complete search response."""
    query: str
    search_type: SearchType
    results: List[SearchResult]
    total_results: Optional[int] = None
    search_time: Optional[float] = None
    related_searches: Optional[List[str]] = None
    knowledge_graph: Optional[Dict[str, Any]] = None
    answer_box: Optional[Dict[str, Any]] = None
    people_also_ask: Optional[List[str]] = None
    raw_response: Optional[Dict[str, Any]] = None


class SearchFilters(BaseModel):
    """Search filters and parameters."""
    location: Optional[SearchLocation] = None
    language: Optional[str] = "en"
    date_range: Optional[str] = None  # "d" (day), "w" (week), "m" (month), "y" (year)
    safe_search: bool = True
    num_results: int = Field(default=10, ge=1, le=100)
    page: int = Field(default=1, ge=1)


class SerperAPI:
    """Serper API client for search operations."""
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://google.serper.dev",
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Initialize Serper API client.
        
        Args:
            api_key: Serper API key
            base_url: Base URL for Serper API
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)
        
        # Request tracking
        self._request_count = 0
        self._total_cost = 0.0
        self._rate_limit_remaining = None
        self._rate_limit_reset = None
        
        # HTTP client
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def _ensure_client(self):
        """Ensure HTTP client is initialized."""
        if not self._client:
            self._client = httpx.AsyncClient(
                headers={
                    "X-API-KEY": self.api_key,
                    "Content-Type": "application/json"
                },
                timeout=httpx.Timeout(self.timeout)
            )

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def search(
        self,
        query: str,
        search_type: SearchType = SearchType.WEB,
        filters: Optional[SearchFilters] = None
    ) -> SearchResponse:
        """
        Perform a search query.
        
        Args:
            query: Search query string
            search_type: Type of search to perform
            filters: Optional search filters
            
        Returns:
            Search response with results
            
        Raises:
            httpx.HTTPError: If API request fails
            ValueError: If query is empty or invalid
        """
        if not query.strip():
            raise ValueError("Search query cannot be empty")
        
        filters = filters or SearchFilters()
        
        # Prepare request data
        request_data = {
            "q": query.strip(),
            "num": filters.num_results,
            "page": filters.page
        }
        
        # Add optional parameters
        if filters.location and filters.location != SearchLocation.GLOBAL:
            request_data["gl"] = filters.location.value
        
        if filters.language:
            request_data["hl"] = filters.language
        
        if filters.date_range:
            request_data["tbs"] = f"qdr:{filters.date_range}"
        
        if not filters.safe_search:
            request_data["safe"] = "off"
        
        # Make API request with retries
        response_data = await self._make_request(search_type.value, request_data)
        
        # Parse response
        return self._parse_search_response(query, search_type, response_data)

    async def web_search(
        self,
        query: str,
        filters: Optional[SearchFilters] = None
    ) -> SearchResponse:
        """
        Perform a web search.
        
        Args:
            query: Search query
            filters: Optional search filters
            
        Returns:
            Web search results
        """
        return await self.search(query, SearchType.WEB, filters)

    async def news_search(
        self,
        query: str,
        filters: Optional[SearchFilters] = None
    ) -> SearchResponse:
        """
        Perform a news search.
        
        Args:
            query: Search query
            filters: Optional search filters
            
        Returns:
            News search results
        """
        return await self.search(query, SearchType.NEWS, filters)

    async def image_search(
        self,
        query: str,
        filters: Optional[SearchFilters] = None
    ) -> SearchResponse:
        """
        Perform an image search.
        
        Args:
            query: Search query
            filters: Optional search filters
            
        Returns:
            Image search results
        """
        return await self.search(query, SearchType.IMAGES, filters)

    async def places_search(
        self,
        query: str,
        filters: Optional[SearchFilters] = None
    ) -> SearchResponse:
        """
        Perform a places/local search.
        
        Args:
            query: Search query (e.g., "restaurants near me")
            filters: Optional search filters
            
        Returns:
            Places search results
        """
        return await self.search(query, SearchType.PLACES, filters)

    async def shopping_search(
        self,
        query: str,
        filters: Optional[SearchFilters] = None
    ) -> SearchResponse:
        """
        Perform a shopping search.
        
        Args:
            query: Product search query
            filters: Optional search filters
            
        Returns:
            Shopping search results
        """
        return await self.search(query, SearchType.SHOPPING, filters)

    async def batch_search(
        self,
        queries: List[str],
        search_type: SearchType = SearchType.WEB,
        filters: Optional[SearchFilters] = None,
        max_concurrent: int = 5
    ) -> List[SearchResponse]:
        """
        Perform multiple searches concurrently.
        
        Args:
            queries: List of search queries
            search_type: Type of search to perform
            filters: Optional search filters
            max_concurrent: Maximum concurrent requests
            
        Returns:
            List of search responses
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def search_with_semaphore(query: str) -> SearchResponse:
            async with semaphore:
                return await self.search(query, search_type, filters)
        
        tasks = [search_with_semaphore(query) for query in queries]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def get_suggestions(self, query: str) -> List[str]:
        """
        Get search suggestions for a query.
        
        Args:
            query: Partial search query
            
        Returns:
            List of search suggestions
        """
        try:
            # Use a simple web search to get related searches
            response = await self.web_search(query, SearchFilters(num_results=1))
            return response.related_searches or []
        except Exception as e:
            self.logger.warning(f"Failed to get suggestions for '{query}': {e}")
            return []

    async def _make_request(
        self, 
        endpoint: str, 
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make API request with retry logic."""
        await self._ensure_client()
        
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # Check rate limits
                if self._rate_limit_remaining is not None and self._rate_limit_remaining <= 0:
                    if self._rate_limit_reset:
                        wait_time = (self._rate_limit_reset - datetime.now()).total_seconds()
                        if wait_time > 0:
                            self.logger.info(f"Rate limit reached, waiting {wait_time:.1f}s")
                            await asyncio.sleep(wait_time)
                
                response = await self._client.post(
                    f"{self.base_url}/{endpoint}",
                    json=data
                )
                
                # Update rate limit info
                self._update_rate_limit_info(response.headers)
                
                # Handle different response codes
                if response.status_code == 200:
                    self._request_count += 1
                    return response.json()
                elif response.status_code == 429:
                    # Rate limited
                    retry_after = int(response.headers.get("Retry-After", 60))
                    self.logger.warning(f"Rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    continue
                elif response.status_code == 402:
                    # Payment required
                    raise RuntimeError("Serper API quota exceeded or payment required")
                else:
                    response.raise_for_status()
                    
            except httpx.TimeoutException as e:
                last_exception = e
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    self.logger.warning(f"Request timeout, retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
            except httpx.HTTPError as e:
                last_exception = e
                if attempt < self.max_retries and e.response.status_code >= 500:
                    wait_time = 2 ** attempt
                    self.logger.warning(f"Server error, retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise
        
        # All retries failed
        raise last_exception or RuntimeError("All retry attempts failed")

    def _update_rate_limit_info(self, headers: Dict[str, str]):
        """Update rate limit information from response headers."""
        if "X-RateLimit-Remaining" in headers:
            self._rate_limit_remaining = int(headers["X-RateLimit-Remaining"])
        
        if "X-RateLimit-Reset" in headers:
            reset_timestamp = int(headers["X-RateLimit-Reset"])
            self._rate_limit_reset = datetime.fromtimestamp(reset_timestamp)

    def _parse_search_response(
        self,
        query: str,
        search_type: SearchType,
        data: Dict[str, Any]
    ) -> SearchResponse:
        """Parse API response into SearchResponse object."""
        results = []
        
        # Parse organic results
        organic_results = data.get("organic", [])
        for i, result in enumerate(organic_results):
            search_result = SearchResult(
                title=result.get("title", ""),
                link=result.get("link", ""),
                snippet=result.get("snippet", ""),
                position=result.get("position", i + 1),
                date=result.get("date"),
                source=result.get("source"),
                additional_data=result
            )
            results.append(search_result)
        
        # Parse news results
        news_results = data.get("news", [])
        for i, result in enumerate(news_results):
            search_result = SearchResult(
                title=result.get("title", ""),
                link=result.get("link", ""),
                snippet=result.get("snippet", ""),
                position=len(results) + i + 1,
                date=result.get("date"),
                source=result.get("source"),
                thumbnail=result.get("imageUrl"),
                additional_data=result
            )
            results.append(search_result)
        
        # Parse image results
        images_results = data.get("images", [])
        for i, result in enumerate(images_results):
            search_result = SearchResult(
                title=result.get("title", ""),
                link=result.get("link", ""),
                snippet="",
                position=len(results) + i + 1,
                source=result.get("source"),
                thumbnail=result.get("imageUrl"),
                additional_data=result
            )
            results.append(search_result)
        
        # Parse places results
        places_results = data.get("places", [])
        for i, result in enumerate(places_results):
            search_result = SearchResult(
                title=result.get("title", ""),
                link=result.get("link", ""),
                snippet=result.get("address", ""),
                position=len(results) + i + 1,
                rating=result.get("rating"),
                additional_data=result
            )
            results.append(search_result)
        
        # Parse shopping results
        shopping_results = data.get("shopping", [])
        for i, result in enumerate(shopping_results):
            search_result = SearchResult(
                title=result.get("title", ""),
                link=result.get("link", ""),
                snippet=result.get("snippet", ""),
                position=len(results) + i + 1,
                price=result.get("price"),
                source=result.get("source"),
                thumbnail=result.get("imageUrl"),
                rating=result.get("rating"),
                additional_data=result
            )
            results.append(search_result)
        
        # Extract additional information
        related_searches = []
        if "relatedSearches" in data:
            related_searches = [rs.get("query", "") for rs in data["relatedSearches"]]
        
        people_also_ask = []
        if "peopleAlsoAsk" in data:
            people_also_ask = [paa.get("question", "") for paa in data["peopleAlsoAsk"]]
        
        return SearchResponse(
            query=query,
            search_type=search_type,
            results=results,
            total_results=data.get("searchInformation", {}).get("totalResults"),
            search_time=data.get("searchInformation", {}).get("searchTime"),
            related_searches=related_searches,
            knowledge_graph=data.get("knowledgeGraph"),
            answer_box=data.get("answerBox"),
            people_also_ask=people_also_ask,
            raw_response=data
        )

    def extract_key_information(
        self, 
        response: SearchResponse, 
        max_results: int = 5
    ) -> Dict[str, Any]:
        """
        Extract key information from search response.
        
        Args:
            response: Search response
            max_results: Maximum number of results to include
            
        Returns:
            Extracted key information
        """
        key_info = {
            "query": response.query,
            "search_type": response.search_type.value,
            "summary": "",
            "top_results": [],
            "key_facts": [],
            "related_topics": response.related_searches or []
        }
        
        # Extract answer box information
        if response.answer_box:
            key_info["summary"] = response.answer_box.get("answer", "")
            if response.answer_box.get("snippet"):
                key_info["summary"] += f" {response.answer_box['snippet']}"
        
        # Extract knowledge graph information
        if response.knowledge_graph:
            kg = response.knowledge_graph
            if kg.get("description"):
                key_info["summary"] = kg["description"]
            
            # Extract key facts from knowledge graph
            if kg.get("attributes"):
                for attr_name, attr_value in kg["attributes"].items():
                    key_info["key_facts"].append(f"{attr_name}: {attr_value}")
        
        # Extract top results
        for result in response.results[:max_results]:
            key_info["top_results"].append({
                "title": result.title,
                "url": result.link,
                "snippet": result.snippet,
                "source": result.source
            })
        
        # If no summary from answer box or knowledge graph, use first result snippet
        if not key_info["summary"] and response.results:
            key_info["summary"] = response.results[0].snippet
        
        return key_info

    def get_api_stats(self) -> Dict[str, Any]:
        """
        Get API usage statistics.
        
        Returns:
            API usage statistics
        """
        return {
            "total_requests": self._request_count,
            "estimated_cost": self._total_cost,
            "rate_limit_remaining": self._rate_limit_remaining,
            "rate_limit_reset": self._rate_limit_reset.isoformat() if self._rate_limit_reset else None
        }