"""
Model configuration and presets for local and cloud-based language models.

This module defines configurations for different types of models and tasks,
including memory usage estimation and performance optimization settings.
"""

import logging
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from pydantic import BaseModel, Field


class ModelProvider(str, Enum):
    """Supported model providers."""
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE = "azure"


class TaskComplexity(str, Enum):
    """Task complexity levels for model selection."""
    SIMPLE = "simple"          # Basic navigation, clicking, form filling
    MODERATE = "moderate"      # Multi-step tasks, simple reasoning
    COMPLEX = "complex"        # Advanced reasoning, planning
    EXPERT = "expert"          # Complex multi-modal tasks, code generation


class ModelCapability(str, Enum):
    """Model capabilities."""
    TEXT_ONLY = "text_only"
    VISION = "vision"
    CODE = "code"
    REASONING = "reasoning"
    MULTIMODAL = "multimodal"


@dataclass
class ModelSpecs:
    """Technical specifications for a model."""
    context_length: int
    max_tokens: int
    supports_vision: bool
    supports_function_calling: bool
    estimated_memory_gb: Optional[float] = None
    tokens_per_second: Optional[float] = None
    cost_per_1k_tokens: Optional[float] = None


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    name: str
    provider: ModelProvider
    model_id: str
    specs: ModelSpecs
    capabilities: List[ModelCapability]
    temperature: float = 0.1
    max_tokens: int = 2048
    timeout: int = 60
    retry_attempts: int = 3
    custom_params: Optional[Dict[str, Any]] = None

    def supports_capability(self, capability: ModelCapability) -> bool:
        """Check if model supports a specific capability."""
        return capability in self.capabilities

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> Optional[float]:
        """Estimate cost for a request."""
        if not self.specs.cost_per_1k_tokens:
            return None
        
        total_tokens = input_tokens + output_tokens
        return (total_tokens / 1000) * self.specs.cost_per_1k_tokens


class ModelConfigManager:
    """Manager for model configurations and presets."""

    def __init__(self):
        """Initialize the model configuration manager."""
        self.logger = logging.getLogger(__name__)
        self._models: Dict[str, ModelConfig] = {}
        self._task_presets: Dict[TaskComplexity, List[str]] = {}
        self._initialize_default_models()
        self._initialize_task_presets()

    def _initialize_default_models(self):
        """Initialize default model configurations."""
        
        # OpenAI Models
        self._models["gpt-4o"] = ModelConfig(
            name="GPT-4o",
            provider=ModelProvider.OPENAI,
            model_id="gpt-4o",
            specs=ModelSpecs(
                context_length=128000,
                max_tokens=4096,
                supports_vision=True,
                supports_function_calling=True,
                cost_per_1k_tokens=0.015
            ),
            capabilities=[
                ModelCapability.TEXT_ONLY,
                ModelCapability.VISION,
                ModelCapability.CODE,
                ModelCapability.REASONING,
                ModelCapability.MULTIMODAL
            ]
        )

        self._models["gpt-4o-mini"] = ModelConfig(
            name="GPT-4o Mini",
            provider=ModelProvider.OPENAI,
            model_id="gpt-4o-mini",
            specs=ModelSpecs(
                context_length=128000,
                max_tokens=16384,
                supports_vision=True,
                supports_function_calling=True,
                cost_per_1k_tokens=0.00015
            ),
            capabilities=[
                ModelCapability.TEXT_ONLY,
                ModelCapability.VISION,
                ModelCapability.CODE,
                ModelCapability.REASONING,
                ModelCapability.MULTIMODAL
            ]
        )

        self._models["o3-mini"] = ModelConfig(
            name="OpenAI O3 Mini",
            provider=ModelProvider.OPENAI,
            model_id="o3-mini",
            specs=ModelSpecs(
                context_length=200000,
                max_tokens=65536,
                supports_vision=True,
                supports_function_calling=True,
                cost_per_1k_tokens=0.060
            ),
            capabilities=[
                ModelCapability.TEXT_ONLY,
                ModelCapability.VISION,
                ModelCapability.CODE,
                ModelCapability.REASONING,
                ModelCapability.MULTIMODAL
            ]
        )

        # Anthropic Models
        self._models["claude-3-5-sonnet"] = ModelConfig(
            name="Claude 3.5 Sonnet",
            provider=ModelProvider.ANTHROPIC,
            model_id="claude-3-5-sonnet-20241022",
            specs=ModelSpecs(
                context_length=200000,
                max_tokens=8192,
                supports_vision=True,
                supports_function_calling=True,
                cost_per_1k_tokens=0.003
            ),
            capabilities=[
                ModelCapability.TEXT_ONLY,
                ModelCapability.VISION,
                ModelCapability.CODE,
                ModelCapability.REASONING,
                ModelCapability.MULTIMODAL
            ]
        )

        # Ollama Models (Local)
        self._models["llama3.2"] = ModelConfig(
            name="Llama 3.2",
            provider=ModelProvider.OLLAMA,
            model_id="llama3.2",
            specs=ModelSpecs(
                context_length=8192,
                max_tokens=2048,
                supports_vision=False,
                supports_function_calling=True,
                estimated_memory_gb=4.0,
                tokens_per_second=50.0
            ),
            capabilities=[
                ModelCapability.TEXT_ONLY,
                ModelCapability.CODE,
                ModelCapability.REASONING
            ]
        )

        self._models["llama3.2-vision"] = ModelConfig(
            name="Llama 3.2 Vision",
            provider=ModelProvider.OLLAMA,
            model_id="llama3.2-vision",
            specs=ModelSpecs(
                context_length=8192,
                max_tokens=2048,
                supports_vision=True,
                supports_function_calling=True,
                estimated_memory_gb=8.0,
                tokens_per_second=30.0
            ),
            capabilities=[
                ModelCapability.TEXT_ONLY,
                ModelCapability.VISION,
                ModelCapability.CODE,
                ModelCapability.REASONING,
                ModelCapability.MULTIMODAL
            ]
        )

        self._models["qwen2.5-coder"] = ModelConfig(
            name="Qwen2.5 Coder",
            provider=ModelProvider.OLLAMA,
            model_id="qwen2.5-coder",
            specs=ModelSpecs(
                context_length=32768,
                max_tokens=4096,
                supports_vision=False,
                supports_function_calling=True,
                estimated_memory_gb=6.0,
                tokens_per_second=40.0
            ),
            capabilities=[
                ModelCapability.TEXT_ONLY,
                ModelCapability.CODE,
                ModelCapability.REASONING
            ]
        )

        # Granite 3.2 Vision - Primary local model for vision + reasoning
        self._models["granite3.2-vision"] = ModelConfig(
            name="Granite 3.2 Vision",
            provider=ModelProvider.OLLAMA,
            model_id="granite3.2-vision",
            specs=ModelSpecs(
                context_length=16384,
                max_tokens=4096,
                supports_vision=True,
                supports_function_calling=True,
                estimated_memory_gb=2.0,
                tokens_per_second=45.0
            ),
            capabilities=[
                ModelCapability.TEXT_ONLY,
                ModelCapability.VISION,
                ModelCapability.CODE,
                ModelCapability.REASONING,
                ModelCapability.MULTIMODAL
            ]
        )

        # Google Models
        self._models["gemini-1.5-pro"] = ModelConfig(
            name="Gemini 1.5 Pro",
            provider=ModelProvider.GOOGLE,
            model_id="gemini-1.5-pro",
            specs=ModelSpecs(
                context_length=2000000,
                max_tokens=8192,
                supports_vision=True,
                supports_function_calling=True,
                cost_per_1k_tokens=0.00125
            ),
            capabilities=[
                ModelCapability.TEXT_ONLY,
                ModelCapability.VISION,
                ModelCapability.CODE,
                ModelCapability.REASONING,
                ModelCapability.MULTIMODAL
            ]
        )

        self._models["gemini-2.5-flash"] = ModelConfig(
            name="Gemini 2.5 Flash",
            provider=ModelProvider.GOOGLE,
            model_id="gemini-2.5-flash-exp",
            specs=ModelSpecs(
                context_length=1000000,
                max_tokens=8192,
                supports_vision=True,
                supports_function_calling=True,
                cost_per_1k_tokens=0.0002
            ),
            capabilities=[
                ModelCapability.TEXT_ONLY,
                ModelCapability.VISION,
                ModelCapability.CODE,
                ModelCapability.REASONING,
                ModelCapability.MULTIMODAL
            ]
        )

    def _initialize_task_presets(self):
        """Initialize task complexity presets with local-first approach."""
        self._task_presets = {
            TaskComplexity.SIMPLE: [
                "granite3.2-vision",
                "llama3.2",
                "gemini-2.5-flash"
            ],
            TaskComplexity.MODERATE: [
                "granite3.2-vision",
                "llama3.2-vision",
                "qwen2.5-coder",
                "gemini-2.5-flash"
            ],
            TaskComplexity.COMPLEX: [
                "granite3.2-vision",
                "llama3.2-vision",
                "gemini-2.5-flash",
                "claude-3-5-sonnet"
            ],
            TaskComplexity.EXPERT: [
                "granite3.2-vision",
                "gemini-2.5-flash",
                "claude-3-5-sonnet",
                "gpt-4o"
            ]
        }

    def get_model_config(self, model_name: str) -> Optional[ModelConfig]:
        """
        Get configuration for a specific model.
        
        Args:
            model_name: Name of the model
            
        Returns:
            Model configuration or None if not found
        """
        return self._models.get(model_name)

    def list_models(
        self, 
        provider: Optional[ModelProvider] = None,
        capability: Optional[ModelCapability] = None
    ) -> List[ModelConfig]:
        """
        List available models with optional filtering.
        
        Args:
            provider: Filter by provider
            capability: Filter by capability
            
        Returns:
            List of model configurations
        """
        models = list(self._models.values())
        
        if provider:
            models = [m for m in models if m.provider == provider]
            
        if capability:
            models = [m for m in models if m.supports_capability(capability)]
            
        return models


    def estimate_local_memory_usage(self, model_names: List[str]) -> float:
        """
        Estimate total memory usage for local models.
        
        Args:
            model_names: List of model names to load
            
        Returns:
            Estimated memory usage in GB
        """
        total_memory = 0.0
        
        for name in model_names:
            model = self._models.get(name)
            if model and model.provider == ModelProvider.OLLAMA:
                if model.specs.estimated_memory_gb:
                    total_memory += model.specs.estimated_memory_gb
                    
        return total_memory

    def get_fastest_local_model(
        self, 
        capability: Optional[ModelCapability] = None
    ) -> Optional[ModelConfig]:
        """
        Get the fastest local model with optional capability requirement.
        
        Args:
            capability: Required capability
            
        Returns:
            Fastest local model configuration
        """
        local_models = self.list_models(provider=ModelProvider.OLLAMA, capability=capability)
        
        if not local_models:
            return None
            
        # Sort by tokens per second (descending)
        local_models.sort(
            key=lambda m: m.specs.tokens_per_second or 0, 
            reverse=True
        )
        
        return local_models[0]

    def get_cheapest_cloud_model(
        self, 
        capability: Optional[ModelCapability] = None
    ) -> Optional[ModelConfig]:
        """
        Get the cheapest cloud model with optional capability requirement.
        
        Args:
            capability: Required capability
            
        Returns:
            Cheapest cloud model configuration
        """
        cloud_models = [
            m for m in self.list_models(capability=capability)
            if m.provider != ModelProvider.OLLAMA and m.specs.cost_per_1k_tokens
        ]
        
        if not cloud_models:
            return None
            
        # Sort by cost per 1k tokens (ascending)
        cloud_models.sort(key=lambda m: m.specs.cost_per_1k_tokens or float('inf'))
        
        return cloud_models[0]

    def add_custom_model(self, config: ModelConfig):
        """
        Add a custom model configuration.
        
        Args:
            config: Model configuration to add
        """
        self._models[config.name] = config
        self.logger.info(f"Added custom model: {config.name}")

    def create_model_preset(
        self,
        name: str,
        models: List[str],
        description: Optional[str] = None
    ):
        """
        Create a custom model preset.
        
        Args:
            name: Preset name
            models: List of model names in priority order
            description: Optional description
        """
        # Validate that all models exist
        for model_name in models:
            if model_name not in self._models:
                raise ValueError(f"Model '{model_name}' not found")
        
        # Store as custom task complexity
        custom_complexity = f"custom_{name}"
        self._task_presets[custom_complexity] = models
        
        self.logger.info(f"Created model preset: {name} with {len(models)} models")

    def get_model_comparison(self, model_names: List[str]) -> Dict[str, Any]:
        """
        Compare multiple models across various metrics.
        
        Args:
            model_names: List of model names to compare
            
        Returns:
            Comparison data
        """
        comparison = {
            "models": [],
            "summary": {
                "total_models": len(model_names),
                "local_models": 0,
                "cloud_models": 0,
                "vision_capable": 0,
                "function_calling": 0
            }
        }
        
        for name in model_names:
            model = self._models.get(name)
            if not model:
                continue
                
            model_data = {
                "name": model.name,
                "provider": model.provider.value,
                "capabilities": [cap.value for cap in model.capabilities],
                "context_length": model.specs.context_length,
                "supports_vision": model.specs.supports_vision,
                "supports_function_calling": model.specs.supports_function_calling,
                "estimated_memory_gb": model.specs.estimated_memory_gb,
                "cost_per_1k_tokens": model.specs.cost_per_1k_tokens
            }
            
            comparison["models"].append(model_data)
            
            # Update summary
            if model.provider == ModelProvider.OLLAMA:
                comparison["summary"]["local_models"] += 1
            else:
                comparison["summary"]["cloud_models"] += 1
                
            if model.specs.supports_vision:
                comparison["summary"]["vision_capable"] += 1
                
            if model.specs.supports_function_calling:
                comparison["summary"]["function_calling"] += 1
        
        return comparison