"""
Enhanced Model Configuration for Three-Tier Routing.

This module defines the specific models for the three-tier routing strategy:
1. DeepSeek-R1 32B for text-only tasks (local)
2. LLaVA 13B for vision tasks (local)
3. Cloud models for complex/fallback scenarios
"""

SUPERSEDED BY CENTRAL_MODEL_CONFIG.PY import logging
from typing import Dict, List
from config.models import ModelConfigManager, ModelConfig, ModelProvider, ModelCapability, ModelSpecs, TaskComplexity


class EnhancedModelConfigManager(ModelConfigManager):
    """Enhanced model config manager with three-tier specific models."""
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self._initialize_enhanced_models()
    
    def _initialize_enhanced_models(self):
        """Initialize the enhanced three-tier model configurations."""
        
        # ======================
        # TIER 1: TEXT-ONLY LOCAL MODELS
        # ======================
        
        # DeepSeek-R1 32B - Primary text-only model
        self._models["deepseek-r1:32b"] = ModelConfig(
            name="DeepSeek-R1 32B",
            provider=ModelProvider.OLLAMA,
            model_id="deepseek-r1:32b",
            specs=ModelSpecs(
                context_length=128000,
                max_tokens=4096,
                supports_vision=False,
                supports_function_calling=True,
                estimated_memory_gb=20.0,
                tokens_per_second=25.0,  # Estimated for M4 chip
                cost_per_1k_tokens=0.0  # Local model
            ),
            capabilities=[ModelCapability.TEXT_ONLY, ModelCapability.REASONING, ModelCapability.CODE],
            temperature=0.1,
            max_tokens=2048,
            timeout=60
        )
        
        # DeepSeek-R1 1.5B - Fallback text-only model (already installed)
        self._models["deepseek-r1:1.5b"] = ModelConfig(
            name="DeepSeek-R1 1.5B",
            provider=ModelProvider.OLLAMA,
            model_id="deepseek-r1:1.5b",
            specs=ModelSpecs(
                context_length=32768,
                max_tokens=2048,
                supports_vision=False,
                supports_function_calling=True,
                estimated_memory_gb=1.5,
                tokens_per_second=45.0,  # Faster due to smaller size
                cost_per_1k_tokens=0.0
            ),
            capabilities=[ModelCapability.TEXT_ONLY, ModelCapability.REASONING],
            temperature=0.1,
            max_tokens=1024,
            timeout=30
        )
        
        # ======================
        # TIER 2: VISION LOCAL MODELS  
        # ======================
        
        # LLaVA 13B - Primary vision model
        self._models["llava:13b"] = ModelConfig(
            name="LLaVA 13B",
            provider=ModelProvider.OLLAMA,
            model_id="llava:13b",
            specs=ModelSpecs(
                context_length=4096,
                max_tokens=2048,
                supports_vision=True,
                supports_function_calling=False,
                estimated_memory_gb=8.0,
                tokens_per_second=12.0,  # Slower due to vision processing
                cost_per_1k_tokens=0.0
            ),
            capabilities=[ModelCapability.VISION, ModelCapability.MULTIMODAL],
            temperature=0.1,
            max_tokens=1024,
            timeout=90
        )
        
        # Granite 3.2 Vision - Fallback vision model (already installed)
        self._models["granite3.2-vision:latest"] = ModelConfig(
            name="Granite 3.2 Vision",
            provider=ModelProvider.OLLAMA,
            model_id="granite3.2-vision:latest",
            specs=ModelSpecs(
                context_length=8192,
                max_tokens=2048,
                supports_vision=True,
                supports_function_calling=True,
                estimated_memory_gb=2.4,
                tokens_per_second=18.0,
                cost_per_1k_tokens=0.0
            ),
            capabilities=[ModelCapability.VISION, ModelCapability.MULTIMODAL, ModelCapability.CODE],
            temperature=0.1,
            max_tokens=1024,
            timeout=60
        )
        
        # ======================
        # TIER 3: CLOUD MODELS
        # ======================
        
        # Update existing cloud models with more accurate specs
        if "gpt-4o" in self._models:
            self._models["gpt-4o"].specs.cost_per_1k_tokens = 0.005  # Input cost
        
        if "claude-3-5-sonnet" in self._models:
            self._models["claude-3-5-sonnet"].specs.cost_per_1k_tokens = 0.003
            
        # Gemini 2.0 Flash - Cost effective cloud vision
        self._models["gemini-2.0-flash"] = ModelConfig(
            name="Gemini 2.0 Flash",
            provider=ModelProvider.GOOGLE,
            model_id="gemini-2.0-flash-exp",
            specs=ModelSpecs(
                context_length=1000000,
                max_tokens=8192,
                supports_vision=True,
                supports_function_calling=True,
                estimated_memory_gb=None,  # Cloud model
                tokens_per_second=None,
                cost_per_1k_tokens=0.00075  # Very cost effective
            ),
            capabilities=[ModelCapability.VISION, ModelCapability.MULTIMODAL, ModelCapability.CODE, ModelCapability.REASONING],
            temperature=0.1,
            max_tokens=2048,
            timeout=30
        )
    
    def get_tier_models(self, tier: str) -> List[str]:
        """Get model names for a specific tier."""
        tier_models = {
            "text_local": [
                "deepseek-r1:32b",      # Primary
                "deepseek-r1:1.5b",    # Fallback
            ],
            "vision_local": [
                "llava:13b",           # Primary
                "granite3.2-vision:latest",  # Fallback
            ],
            "cloud": [
                "gemini-2.0-flash",    # Cost effective
                "gpt-4o",             # High quality
                "claude-3-5-sonnet",  # Backup
            ]
        }
        return tier_models.get(tier, [])
    
    def get_best_model_for_task(self, requires_vision: bool, prefer_local: bool = True) -> str:
        """Get the best model for a task based on requirements."""
        if not requires_vision:
            # Text-only task
            if prefer_local:
                # Check if DeepSeek 32B is available, fallback to 1.5B
                return "deepseek-r1:32b"
            else:
                return "gpt-4o"  # Cloud text model
        else:
            # Vision task
            if prefer_local:
                # Check if LLaVA is available, fallback to Granite
                return "llava:13b"
            else:
                return "gemini-2.0-flash"  # Cost effective cloud vision
    
    def estimate_routing_savings(self, task_distribution: Dict[str, int]) -> Dict[str, float]:
        """Estimate cost savings from three-tier routing."""
        # Task distribution should have: text_only, vision_local, cloud
        total_tasks = sum(task_distribution.values())
        
        if total_tasks == 0:
            return {"total_cost": 0.0, "savings": 0.0}
        
        # Cost estimates per task type
        costs = {
            "text_only": 0.0,      # Local DeepSeek
            "vision_local": 0.0,   # Local LLaVA
            "cloud": 0.02          # Average cloud cost
        }
        
        # Calculate actual cost
        actual_cost = sum(
            task_distribution.get(task_type, 0) * cost
            for task_type, cost in costs.items()
        )
        
        # Calculate cost if all tasks went to cloud
        all_cloud_cost = total_tasks * 0.02
        
        savings = all_cloud_cost - actual_cost
        savings_percentage = (savings / all_cloud_cost * 100) if all_cloud_cost > 0 else 0
        
        return {
            "total_cost": actual_cost,
            "all_cloud_cost": all_cloud_cost,
            "savings": savings,
            "savings_percentage": savings_percentage,
            "cost_per_task": actual_cost / total_tasks if total_tasks > 0 else 0
        }
    
    def get_model_availability_status(self) -> Dict[str, Dict[str, bool]]:
        """Get availability status of all tier models."""
        # This would normally check with Ollama and cloud APIs
        # For now, return expected availability
        return {
            "text_local": {
                "deepseek-r1:32b": True,     # Downloading
                "deepseek-r1:1.5b": True,    # Available
            },
            "vision_local": {
                "llava:13b": True,           # Downloading  
                "granite3.2-vision:latest": True,  # Available
            },
            "cloud": {
                "gemini-2.0-flash": True,   # API available
                "gpt-4o": True,             # API available
                "claude-3-5-sonnet": True,  # API available
            }
        }