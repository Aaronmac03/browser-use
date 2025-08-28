"""
Ollama Model Handler for local language model management.

This module provides the OllamaModelHandler class that interfaces with Ollama
for loading, unloading, and querying local language models with both text
and vision capabilities.
"""

import asyncio
import logging
import json
import base64
from typing import Dict, List, Optional, Any, Union, AsyncGenerator
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from pydantic import BaseModel, Field

from config.models import ModelConfig, ModelProvider


class OllamaModelInfo(BaseModel):
    """Information about an Ollama model."""
    name: str
    size: int
    digest: str
    modified_at: datetime
    details: Dict[str, Any] = Field(default_factory=dict)


class OllamaResponse(BaseModel):
    """Response from Ollama API."""
    model: str
    created_at: datetime
    response: str
    done: bool
    context: Optional[List[int]] = None
    total_duration: Optional[int] = None
    load_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    prompt_eval_duration: Optional[int] = None
    eval_count: Optional[int] = None
    eval_duration: Optional[int] = None


class OllamaModelHandler:
    """Handler for Ollama local language models."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        timeout: int = 300,
        max_concurrent_requests: int = 3
    ):
        """
        Initialize the Ollama model handler.
        
        Args:
            base_url: Ollama server base URL
            timeout: Request timeout in seconds
            max_concurrent_requests: Maximum concurrent requests
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_concurrent_requests = max_concurrent_requests
        self.logger = logging.getLogger(__name__)
        
        # Track loaded models and their usage
        self._loaded_models: Dict[str, datetime] = {}
        self._model_stats: Dict[str, Dict[str, Any]] = {}
        self._request_semaphore = asyncio.Semaphore(max_concurrent_requests)
        
        # HTTP client for API requests
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
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
            )

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def is_available(self) -> bool:
        """
        Check if Ollama server is available.
        
        Returns:
            True if server is available, False otherwise
        """
        try:
            await self._ensure_client()
            response = await self._client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except Exception as e:
            self.logger.warning(f"Ollama server not available: {e}")
            return False

    async def list_models(self) -> List[OllamaModelInfo]:
        """
        List all available models on the Ollama server.
        
        Returns:
            List of model information
        """
        try:
            await self._ensure_client()
            response = await self._client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            
            data = response.json()
            models = []
            
            for model_data in data.get("models", []):
                model_info = OllamaModelInfo(
                    name=model_data["name"],
                    size=model_data["size"],
                    digest=model_data["digest"],
                    modified_at=datetime.fromisoformat(
                        model_data["modified_at"].replace("Z", "+00:00")
                    ),
                    details=model_data.get("details", {})
                )
                models.append(model_info)
            
            return models
            
        except Exception as e:
            self.logger.error(f"Failed to list models: {e}")
            return []

    async def pull_model(self, model_name: str) -> bool:
        """
        Pull a model from the Ollama registry.
        
        Args:
            model_name: Name of the model to pull
            
        Returns:
            True if successful, False otherwise
        """
        try:
            await self._ensure_client()
            
            self.logger.info(f"Pulling model: {model_name}")
            
            async with self._client.stream(
                "POST",
                f"{self.base_url}/api/pull",
                json={"name": model_name}
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if "status" in data:
                                self.logger.info(f"Pull status: {data['status']}")
                            if data.get("completed"):
                                self.logger.info(f"Successfully pulled model: {model_name}")
                                return True
                        except json.JSONDecodeError:
                            continue
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to pull model {model_name}: {e}")
            return False

    async def load_model(self, model_name: str) -> bool:
        """
        Load a model into memory.
        
        Args:
            model_name: Name of the model to load
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if model is already loaded
            if model_name in self._loaded_models:
                self._loaded_models[model_name] = datetime.now()
                return True
            
            await self._ensure_client()
            
            # Send a simple request to load the model
            response = await self._client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model_name,
                    "prompt": "Hello",
                    "stream": False,
                    "options": {"num_predict": 1}
                }
            )
            
            if response.status_code == 200:
                self._loaded_models[model_name] = datetime.now()
                self._model_stats[model_name] = {
                    "requests": 0,
                    "total_tokens": 0,
                    "avg_response_time": 0.0,
                    "last_used": datetime.now()
                }
                self.logger.info(f"Loaded model: {model_name}")
                return True
            else:
                self.logger.error(f"Failed to load model {model_name}: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to load model {model_name}: {e}")
            return False

    async def unload_model(self, model_name: str) -> bool:
        """
        Unload a model from memory.
        
        Args:
            model_name: Name of the model to unload
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if model_name not in self._loaded_models:
                return True
            
            # Ollama doesn't have explicit unload, but we can track it
            del self._loaded_models[model_name]
            self.logger.info(f"Unloaded model: {model_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to unload model {model_name}: {e}")
            return False

    async def generate_text(
        self,
        model_name: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        stream: bool = False,
        images: Optional[List[str]] = None
    ) -> Union[str, AsyncGenerator[str, None]]:
        """
        Generate text using a local model.
        
        Args:
            model_name: Name of the model to use
            prompt: Input prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
            images: Optional list of base64-encoded images
            
        Returns:
            Generated text or async generator for streaming
        """
        async with self._request_semaphore:
            try:
                await self._ensure_client()
                
                # Ensure model is loaded
                if not await self.load_model(model_name):
                    raise RuntimeError(f"Failed to load model: {model_name}")
                
                # Prepare request data
                request_data = {
                    "model": model_name,
                    "prompt": prompt,
                    "stream": stream,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    }
                }
                
                if system_prompt:
                    request_data["system"] = system_prompt
                
                if images:
                    request_data["images"] = images
                
                start_time = datetime.now()
                
                if stream:
                    return self._stream_generate(request_data, model_name, start_time)
                else:
                    return await self._single_generate(request_data, model_name, start_time)
                    
            except Exception as e:
                self.logger.error(f"Failed to generate text with {model_name}: {e}")
                raise

    async def _single_generate(
        self, 
        request_data: Dict[str, Any], 
        model_name: str, 
        start_time: datetime
    ) -> str:
        """Handle single (non-streaming) generation."""
        response = await self._client.post(
            f"{self.base_url}/api/generate",
            json=request_data
        )
        response.raise_for_status()
        
        data = response.json()
        generated_text = data.get("response", "")
        
        # Update statistics
        self._update_model_stats(model_name, start_time, len(generated_text.split()))
        
        return generated_text

    async def _stream_generate(
        self, 
        request_data: Dict[str, Any], 
        model_name: str, 
        start_time: datetime
    ) -> AsyncGenerator[str, None]:
        """Handle streaming generation."""
        total_tokens = 0
        
        async with self._client.stream(
            "POST",
            f"{self.base_url}/api/generate",
            json=request_data
        ) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        if "response" in data:
                            chunk = data["response"]
                            total_tokens += len(chunk.split())
                            yield chunk
                            
                        if data.get("done", False):
                            # Update statistics when done
                            self._update_model_stats(model_name, start_time, total_tokens)
                            break
                            
                    except json.JSONDecodeError:
                        continue

    def _update_model_stats(self, model_name: str, start_time: datetime, tokens: int):
        """Update model usage statistics."""
        if model_name not in self._model_stats:
            self._model_stats[model_name] = {
                "requests": 0,
                "total_tokens": 0,
                "avg_response_time": 0.0,
                "last_used": datetime.now()
            }
        
        stats = self._model_stats[model_name]
        response_time = (datetime.now() - start_time).total_seconds()
        
        stats["requests"] += 1
        stats["total_tokens"] += tokens
        stats["avg_response_time"] = (
            (stats["avg_response_time"] * (stats["requests"] - 1) + response_time) 
            / stats["requests"]
        )
        stats["last_used"] = datetime.now()

    async def generate_with_vision(
        self,
        model_name: str,
        prompt: str,
        image_paths: List[str],
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048
    ) -> str:
        """
        Generate text with vision capabilities.
        
        Args:
            model_name: Name of the vision-capable model
            prompt: Text prompt
            image_paths: List of image file paths
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text response
        """
        try:
            # Encode images to base64
            images = []
            for image_path in image_paths:
                path = Path(image_path)
                if not path.exists():
                    raise FileNotFoundError(f"Image not found: {image_path}")
                
                with open(path, "rb") as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                    images.append(image_data)
            
            return await self.generate_text(
                model_name=model_name,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                images=images
            )
            
        except Exception as e:
            self.logger.error(f"Failed to generate with vision: {e}")
            raise

    async def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a model.
        
        Args:
            model_name: Name of the model
            
        Returns:
            Model information dictionary or None if not found
        """
        try:
            await self._ensure_client()
            response = await self._client.post(
                f"{self.base_url}/api/show",
                json={"name": model_name}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get model info for {model_name}: {e}")
            return None

    def get_loaded_models(self) -> List[str]:
        """
        Get list of currently loaded models.
        
        Returns:
            List of loaded model names
        """
        return list(self._loaded_models.keys())

    def get_model_stats(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        Get usage statistics for a model.
        
        Args:
            model_name: Name of the model
            
        Returns:
            Statistics dictionary or None if not found
        """
        return self._model_stats.get(model_name)

    async def cleanup_unused_models(self, max_idle_time: int = 3600):
        """
        Unload models that haven't been used for a specified time.
        
        Args:
            max_idle_time: Maximum idle time in seconds before unloading
        """
        current_time = datetime.now()
        models_to_unload = []
        
        for model_name, last_used in self._loaded_models.items():
            idle_time = (current_time - last_used).total_seconds()
            if idle_time > max_idle_time:
                models_to_unload.append(model_name)
        
        for model_name in models_to_unload:
            await self.unload_model(model_name)
            self.logger.info(f"Unloaded idle model: {model_name}")

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the Ollama service.
        
        Returns:
            Health check results
        """
        health_data = {
            "server_available": False,
            "loaded_models": len(self._loaded_models),
            "total_requests": sum(
                stats["requests"] for stats in self._model_stats.values()
            ),
            "models": {}
        }
        
        try:
            health_data["server_available"] = await self.is_available()
            
            if health_data["server_available"]:
                available_models = await self.list_models()
                health_data["available_models"] = len(available_models)
                
                for model_name, stats in self._model_stats.items():
                    health_data["models"][model_name] = {
                        "loaded": model_name in self._loaded_models,
                        "requests": stats["requests"],
                        "total_tokens": stats["total_tokens"],
                        "avg_response_time": stats["avg_response_time"],
                        "last_used": stats["last_used"].isoformat()
                    }
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            health_data["error"] = str(e)
        
        return health_data