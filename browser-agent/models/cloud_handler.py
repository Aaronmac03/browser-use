"""
Cloud Model Handler for managing different cloud-based language model providers.

This module provides handlers for various cloud providers including OpenAI, Anthropic,
and Google, with token counting, budget management, and caching mechanisms.
"""

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from pathlib import Path

import httpx
from pydantic import BaseModel, Field

from config.models import ModelConfig, ModelProvider


@dataclass
class TokenUsage:
    """Token usage tracking."""
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: Optional[float] = None


@dataclass
class RequestMetrics:
    """Request performance metrics."""
    response_time: float
    tokens_per_second: float
    success: bool
    error_message: Optional[str] = None


class CacheEntry(BaseModel):
    """Cache entry for API responses."""
    key: str
    response: str
    token_usage: Dict[str, int]
    timestamp: datetime
    expires_at: datetime
    model_name: str


class BudgetManager:
    """Budget management for cloud API usage."""
    
    def __init__(self, daily_limit: float = 100.0, monthly_limit: float = 1000.0):
        """
        Initialize budget manager.
        
        Args:
            daily_limit: Daily spending limit in USD
            monthly_limit: Monthly spending limit in USD
        """
        self.daily_limit = daily_limit
        self.monthly_limit = monthly_limit
        self.logger = logging.getLogger(__name__)
        
        # Track spending
        self._daily_spending = 0.0
        self._monthly_spending = 0.0
        self._last_reset_date = datetime.now().date()
        self._spending_history: List[Dict[str, Any]] = []

    def can_spend(self, amount: float) -> bool:
        """
        Check if spending amount is within budget limits.
        
        Args:
            amount: Amount to spend in USD
            
        Returns:
            True if within budget, False otherwise
        """
        self._reset_if_needed()
        
        return (
            self._daily_spending + amount <= self.daily_limit and
            self._monthly_spending + amount <= self.monthly_limit
        )

    def record_spending(self, amount: float, model_name: str, tokens: int):
        """
        Record spending for budget tracking.
        
        Args:
            amount: Amount spent in USD
            model_name: Name of the model used
            tokens: Number of tokens used
        """
        self._reset_if_needed()
        
        self._daily_spending += amount
        self._monthly_spending += amount
        
        self._spending_history.append({
            "timestamp": datetime.now().isoformat(),
            "amount": amount,
            "model_name": model_name,
            "tokens": tokens,
            "daily_total": self._daily_spending,
            "monthly_total": self._monthly_spending
        })
        
        # Keep only last 1000 entries
        if len(self._spending_history) > 1000:
            self._spending_history = self._spending_history[-1000:]

    def get_budget_status(self) -> Dict[str, Any]:
        """
        Get current budget status.
        
        Returns:
            Budget status information
        """
        self._reset_if_needed()
        
        return {
            "daily_spending": self._daily_spending,
            "daily_limit": self.daily_limit,
            "daily_remaining": max(0, self.daily_limit - self._daily_spending),
            "monthly_spending": self._monthly_spending,
            "monthly_limit": self.monthly_limit,
            "monthly_remaining": max(0, self.monthly_limit - self._monthly_spending),
            "last_reset_date": self._last_reset_date.isoformat()
        }

    def _reset_if_needed(self):
        """Reset daily spending if date has changed."""
        current_date = datetime.now().date()
        
        if current_date > self._last_reset_date:
            # Reset daily spending
            self._daily_spending = 0.0
            self._last_reset_date = current_date
            
            # Reset monthly spending if month has changed
            if current_date.month != self._last_reset_date.month:
                self._monthly_spending = 0.0


class ResponseCache:
    """Cache for API responses to reduce costs."""
    
    def __init__(self, cache_dir: str = "./cache", max_age_hours: int = 24):
        """
        Initialize response cache.
        
        Args:
            cache_dir: Directory to store cache files
            max_age_hours: Maximum age of cache entries in hours
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_age = timedelta(hours=max_age_hours)
        self.logger = logging.getLogger(__name__)
        
        self._cache: Dict[str, CacheEntry] = {}
        self._load_cache()

    def _generate_cache_key(
        self, 
        model_name: str, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048
    ) -> str:
        """Generate cache key for request parameters."""
        content = f"{model_name}:{prompt}:{system_prompt}:{temperature}:{max_tokens}"
        return hashlib.sha256(content.encode()).hexdigest()

    def get(
        self, 
        model_name: str, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048
    ) -> Optional[CacheEntry]:
        """
        Get cached response if available and not expired.
        
        Args:
            model_name: Name of the model
            prompt: Input prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            
        Returns:
            Cache entry if found and valid, None otherwise
        """
        key = self._generate_cache_key(model_name, prompt, system_prompt, temperature, max_tokens)
        entry = self._cache.get(key)
        
        if entry and datetime.now() < entry.expires_at:
            self.logger.debug(f"Cache hit for key: {key[:16]}...")
            return entry
        elif entry:
            # Remove expired entry
            del self._cache[key]
            self.logger.debug(f"Cache expired for key: {key[:16]}...")
        
        return None

    def set(
        self,
        model_name: str,
        prompt: str,
        response: str,
        token_usage: TokenUsage,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048
    ):
        """
        Cache a response.
        
        Args:
            model_name: Name of the model
            prompt: Input prompt
            response: Generated response
            token_usage: Token usage information
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens
        """
        key = self._generate_cache_key(model_name, prompt, system_prompt, temperature, max_tokens)
        
        entry = CacheEntry(
            key=key,
            response=response,
            token_usage={
                "input_tokens": token_usage.input_tokens,
                "output_tokens": token_usage.output_tokens,
                "total_tokens": token_usage.total_tokens
            },
            timestamp=datetime.now(),
            expires_at=datetime.now() + self.max_age,
            model_name=model_name
        )
        
        self._cache[key] = entry
        self._save_cache()
        self.logger.debug(f"Cached response for key: {key[:16]}...")

    def _load_cache(self):
        """Load cache from disk."""
        cache_file = self.cache_dir / "response_cache.json"
        
        if not cache_file.exists():
            return
        
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            for entry_data in data.get('entries', []):
                entry = CacheEntry(**entry_data)
                # Only load non-expired entries
                if datetime.now() < entry.expires_at:
                    self._cache[entry.key] = entry
            
            self.logger.info(f"Loaded {len(self._cache)} cache entries")
            
        except Exception as e:
            self.logger.error(f"Failed to load cache: {e}")

    def _save_cache(self):
        """Save cache to disk."""
        cache_file = self.cache_dir / "response_cache.json"
        
        try:
            # Convert cache entries to serializable format
            entries = []
            for entry in self._cache.values():
                entry_dict = entry.dict()
                entry_dict['timestamp'] = entry.timestamp.isoformat()
                entry_dict['expires_at'] = entry.expires_at.isoformat()
                entries.append(entry_dict)
            
            data = {
                'entries': entries,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to save cache: {e}")

    def clear_expired(self):
        """Remove expired cache entries."""
        current_time = datetime.now()
        expired_keys = [
            key for key, entry in self._cache.items()
            if current_time >= entry.expires_at
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            self._save_cache()
            self.logger.info(f"Cleared {len(expired_keys)} expired cache entries")


class BaseCloudHandler(ABC):
    """Base class for cloud model handlers."""
    
    def __init__(
        self,
        api_key: str,
        budget_manager: Optional[BudgetManager] = None,
        cache: Optional[ResponseCache] = None
    ):
        """
        Initialize base cloud handler.
        
        Args:
            api_key: API key for the provider
            budget_manager: Optional budget manager
            cache: Optional response cache
        """
        self.api_key = api_key
        self.budget_manager = budget_manager
        self.cache = cache
        self.logger = logging.getLogger(__name__)
        
        # Request tracking
        self._request_count = 0
        self._total_tokens = 0
        self._total_cost = 0.0
        self._metrics: List[RequestMetrics] = []

    @abstractmethod
    async def generate_text(
        self,
        model_config: ModelConfig,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048
    ) -> tuple[str, TokenUsage]:
        """Generate text using the cloud model."""
        pass

    @abstractmethod
    def count_tokens(self, text: str, model_name: str) -> int:
        """Count tokens in text for the specific provider."""
        pass

    def record_request(self, metrics: RequestMetrics, token_usage: TokenUsage):
        """Record request metrics and token usage."""
        self._request_count += 1
        self._total_tokens += token_usage.total_tokens
        if token_usage.cost:
            self._total_cost += token_usage.cost
        
        self._metrics.append(metrics)
        
        # Keep only last 1000 metrics
        if len(self._metrics) > 1000:
            self._metrics = self._metrics[-1000:]

    def get_stats(self) -> Dict[str, Any]:
        """Get handler statistics."""
        if not self._metrics:
            return {
                "request_count": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "avg_response_time": 0.0,
                "success_rate": 0.0
            }
        
        successful_requests = [m for m in self._metrics if m.success]
        
        return {
            "request_count": self._request_count,
            "total_tokens": self._total_tokens,
            "total_cost": self._total_cost,
            "avg_response_time": sum(m.response_time for m in self._metrics) / len(self._metrics),
            "avg_tokens_per_second": sum(m.tokens_per_second for m in successful_requests) / max(1, len(successful_requests)),
            "success_rate": len(successful_requests) / len(self._metrics),
            "recent_errors": [m.error_message for m in self._metrics[-10:] if not m.success]
        }


class OpenAIHandler(BaseCloudHandler):
    """Handler for OpenAI models."""
    
    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        self.base_url = "https://api.openai.com/v1"
        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self):
        """Ensure HTTP client is initialized."""
        if not self._client:
            self._client = httpx.AsyncClient(
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=httpx.Timeout(60.0)
            )

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def generate_text(
        self,
        model_config: ModelConfig,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048
    ) -> tuple[str, TokenUsage]:
        """Generate text using OpenAI API."""
        start_time = time.time()
        
        try:
            # Check cache first
            if self.cache:
                cached = self.cache.get(model_config.model_id, prompt, system_prompt, temperature, max_tokens)
                if cached:
                    token_usage = TokenUsage(**cached.token_usage)
                    return cached.response, token_usage
            
            await self._ensure_client()
            
            # Prepare messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # Make API request
            response = await self._client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": model_config.model_id,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }
            )
            response.raise_for_status()
            
            data = response.json()
            generated_text = data["choices"][0]["message"]["content"]
            
            # Extract token usage
            usage = data["usage"]
            token_usage = TokenUsage(
                input_tokens=usage["prompt_tokens"],
                output_tokens=usage["completion_tokens"],
                total_tokens=usage["total_tokens"],
                cost=model_config.estimate_cost(usage["prompt_tokens"], usage["completion_tokens"])
            )
            
            # Record metrics
            response_time = time.time() - start_time
            metrics = RequestMetrics(
                response_time=response_time,
                tokens_per_second=token_usage.output_tokens / response_time,
                success=True
            )
            self.record_request(metrics, token_usage)
            
            # Record spending
            if self.budget_manager and token_usage.cost:
                self.budget_manager.record_spending(
                    token_usage.cost, model_config.model_id, token_usage.total_tokens
                )
            
            # Cache response
            if self.cache:
                self.cache.set(
                    model_config.model_id, prompt, generated_text, token_usage,
                    system_prompt, temperature, max_tokens
                )
            
            return generated_text, token_usage
            
        except Exception as e:
            response_time = time.time() - start_time
            metrics = RequestMetrics(
                response_time=response_time,
                tokens_per_second=0.0,
                success=False,
                error_message=str(e)
            )
            self.record_request(metrics, TokenUsage(0, 0, 0))
            raise

    def count_tokens(self, text: str, model_name: str) -> int:
        """Estimate token count for OpenAI models."""
        # Simple estimation: ~4 characters per token
        return len(text) // 4


class AnthropicHandler(BaseCloudHandler):
    """Handler for Anthropic Claude models."""
    
    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        self.base_url = "https://api.anthropic.com/v1"
        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self):
        """Ensure HTTP client is initialized."""
        if not self._client:
            self._client = httpx.AsyncClient(
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01"
                },
                timeout=httpx.Timeout(60.0)
            )

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def generate_text(
        self,
        model_config: ModelConfig,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048
    ) -> tuple[str, TokenUsage]:
        """Generate text using Anthropic API."""
        start_time = time.time()
        
        try:
            # Check cache first
            if self.cache:
                cached = self.cache.get(model_config.model_id, prompt, system_prompt, temperature, max_tokens)
                if cached:
                    token_usage = TokenUsage(**cached.token_usage)
                    return cached.response, token_usage
            
            await self._ensure_client()
            
            # Prepare request
            request_data = {
                "model": model_config.model_id,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}]
            }
            
            if system_prompt:
                request_data["system"] = system_prompt
            
            # Make API request
            response = await self._client.post(
                f"{self.base_url}/messages",
                json=request_data
            )
            response.raise_for_status()
            
            data = response.json()
            generated_text = data["content"][0]["text"]
            
            # Extract token usage
            usage = data["usage"]
            token_usage = TokenUsage(
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                total_tokens=usage["input_tokens"] + usage["output_tokens"],
                cost=model_config.estimate_cost(usage["input_tokens"], usage["output_tokens"])
            )
            
            # Record metrics
            response_time = time.time() - start_time
            metrics = RequestMetrics(
                response_time=response_time,
                tokens_per_second=token_usage.output_tokens / response_time,
                success=True
            )
            self.record_request(metrics, token_usage)
            
            # Record spending
            if self.budget_manager and token_usage.cost:
                self.budget_manager.record_spending(
                    token_usage.cost, model_config.model_id, token_usage.total_tokens
                )
            
            # Cache response
            if self.cache:
                self.cache.set(
                    model_config.model_id, prompt, generated_text, token_usage,
                    system_prompt, temperature, max_tokens
                )
            
            return generated_text, token_usage
            
        except Exception as e:
            response_time = time.time() - start_time
            metrics = RequestMetrics(
                response_time=response_time,
                tokens_per_second=0.0,
                success=False,
                error_message=str(e)
            )
            self.record_request(metrics, TokenUsage(0, 0, 0))
            raise

    def count_tokens(self, text: str, model_name: str) -> int:
        """Estimate token count for Anthropic models."""
        # Simple estimation: ~4 characters per token
        return len(text) // 4


class CloudModelManager:
    """Manager for all cloud model handlers."""
    
    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        budget_manager: Optional[BudgetManager] = None,
        cache: Optional[ResponseCache] = None
    ):
        """
        Initialize cloud model manager.
        
        Args:
            openai_api_key: OpenAI API key
            anthropic_api_key: Anthropic API key
            budget_manager: Budget manager instance
            cache: Response cache instance
        """
        self.logger = logging.getLogger(__name__)
        self.budget_manager = budget_manager or BudgetManager()
        self.cache = cache or ResponseCache()
        
        # Initialize handlers
        self._handlers: Dict[ModelProvider, BaseCloudHandler] = {}
        
        if openai_api_key:
            self._handlers[ModelProvider.OPENAI] = OpenAIHandler(
                openai_api_key, budget_manager=self.budget_manager, cache=self.cache
            )
        
        if anthropic_api_key:
            self._handlers[ModelProvider.ANTHROPIC] = AnthropicHandler(
                anthropic_api_key, budget_manager=self.budget_manager, cache=self.cache
            )

    async def generate_text(
        self,
        model_config: ModelConfig,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048
    ) -> tuple[str, TokenUsage]:
        """
        Generate text using the appropriate cloud handler.
        
        Args:
            model_config: Model configuration
            prompt: Input prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text and token usage
        """
        handler = self._handlers.get(model_config.provider)
        if not handler:
            raise ValueError(f"No handler available for provider: {model_config.provider}")
        
        # Check budget before making request
        if self.budget_manager:
            estimated_cost = model_config.estimate_cost(
                self._estimate_input_tokens(prompt, system_prompt),
                max_tokens
            )
            
            if estimated_cost and not self.budget_manager.can_spend(estimated_cost):
                raise RuntimeError("Request would exceed budget limits")
        
        return await handler.generate_text(
            model_config, prompt, system_prompt, temperature, max_tokens
        )

    def _estimate_input_tokens(self, prompt: str, system_prompt: Optional[str] = None) -> int:
        """Estimate input tokens for budget checking."""
        text = prompt
        if system_prompt:
            text += system_prompt
        return len(text) // 4  # Simple estimation

    async def close(self):
        """Close all handlers."""
        for handler in self._handlers.values():
            await handler.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all handlers."""
        stats = {
            "budget": self.budget_manager.get_budget_status(),
            "handlers": {}
        }
        
        for provider, handler in self._handlers.items():
            stats["handlers"][provider.value] = handler.get_stats()
        
        return stats