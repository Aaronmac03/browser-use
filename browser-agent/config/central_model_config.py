"""
Central Model Configuration for Browser-Use Three-Tier Architecture

This is the SINGLE SOURCE OF TRUTH for all model configurations.
When changing models, edit ONLY this file.

Architecture:
- Every query gets o3-2025-04-16 single-shot planning
- Simple tier progression: Text → Vision → Cloud  
- No complex decision trees
- Automatic fallback/escalation on model failures
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pydantic import BaseModel, Field, ConfigDict


class ModelProvider(str, Enum):
	"""Model providers supported by the system."""
	OLLAMA = "ollama"
	OPENAI = "openai"
	ANTHROPIC = "anthropic"
	GOOGLE = "google"


class ModelTier(str, Enum):
	"""Three-tier model architecture."""
	PLANNER = "planner"		# Universal planning for all queries
	TEXT_LOCAL = "text_local"   # Tier 1: Fast local text-only models
	VISION_LOCAL = "vision_local"  # Tier 2: Local vision models  
	CLOUD = "cloud"			 # Tier 3: Cloud models for complex tasks


class ModelCapabilities(str, Enum):
	"""Model capability flags."""
	TEXT_ONLY = "text_only"
	VISION = "vision"
	REASONING = "reasoning"
	CODE = "code"
	MULTIMODAL = "multimodal"


@dataclass
class ModelSpecs:
	"""Technical specifications for a model."""
	context_length: int
	memory_gb: float
	tokens_per_second: Optional[float] = None
	cost_per_1k_input: Optional[float] = None
	cost_per_1k_output: Optional[float] = None


@dataclass 
class ModelConfig:
	"""Complete configuration for a single model."""
	name: str
	provider: ModelProvider
	tier: ModelTier
	capabilities: List[ModelCapabilities]
	specs: ModelSpecs
	model_id: Optional[str] = None  # Provider-specific model ID
	description: str = ""
	is_primary: bool = False  # Primary model in tier


# ============================================================================
# 🎛️ EASY CONFIGURATION SECTION - EDIT THESE VALUES TO CHANGE MODELS
# ============================================================================

# PLANNER MODEL (Used for ALL queries)
PLANNER_MODEL = "o3-2025-04-16"  # Change this to use a different planner

# TIER 1: TEXT-ONLY LOCAL MODELS (Fastest, Free)
TEXT_PRIMARY = "qwen3:8b"       # Change primary text model here
TEXT_FALLBACK = "qwen3:4b"      # Change fallback text model here

# TIER 2: VISION LOCAL MODELS (Medium Speed, Free)  
VISION_PRIMARY = "qwen2.5vl:7b" # Change primary vision model here
VISION_FALLBACK = "llava:13b"   # Change fallback vision model here

# TIER 3: CLOUD MODELS (Slowest, Most Expensive, Highest Quality)
CLOUD_PRIMARY = "gemini-2.5-flash"    # Change primary cloud model here
CLOUD_SECONDARY = "gpt-4o"            # Change secondary cloud model here

# ============================================================================


class CentralModelConfig:
	"""Central configuration manager for all models.
	
	This class provides the single source of truth for model configurations
	and implements the three-tier routing architecture.
	
	🎯 TO CHANGE MODELS: Edit the variables at the top of this file!
	"""
	
	def __init__(self):
		self._models = self._initialize_models()
		self._tier_models = self._organize_by_tier()
	
	def _initialize_models(self) -> Dict[str, ModelConfig]:
		"""Initialize all model configurations."""
		models = {}
		
		# ============================================================================
		# PLANNER: Universal Planning Model (Used for ALL queries)
		# ============================================================================
		models[PLANNER_MODEL] = ModelConfig(
			name=PLANNER_MODEL,
			provider=ModelProvider.OPENAI,  # Update if changing to different provider
			tier=ModelTier.PLANNER,
			capabilities=[ModelCapabilities.REASONING, ModelCapabilities.TEXT_ONLY],
			specs=ModelSpecs(
				context_length=200000,
				memory_gb=0.0,  # Cloud model
				cost_per_1k_input=0.060,
				cost_per_1k_output=0.240
			),
			model_id=PLANNER_MODEL,
			description=f"Universal planner ({PLANNER_MODEL}) for query clarification and task coordination",
			is_primary=True
		)
		
# ============================================================================
		# TIER 1: Local Text-Only Models (Fastest, Free)
		# ============================================================================
		models[TEXT_PRIMARY] = ModelConfig(
			name=TEXT_PRIMARY, 
			provider=ModelProvider.OLLAMA,
			tier=ModelTier.TEXT_LOCAL,
			capabilities=[ModelCapabilities.TEXT_ONLY, ModelCapabilities.CODE],
			specs=ModelSpecs(
				context_length=32768,
				memory_gb=8.0,
				tokens_per_second=45.0,
				cost_per_1k_input=0.0,
				cost_per_1k_output=0.0
			),
			model_id=TEXT_PRIMARY,
			description=f"Primary local text model ({TEXT_PRIMARY}) for navigation and form filling",
			is_primary=True
		)
		
		models[TEXT_FALLBACK] = ModelConfig(
			name=TEXT_FALLBACK,
			provider=ModelProvider.OLLAMA, 
			tier=ModelTier.TEXT_LOCAL,
			capabilities=[ModelCapabilities.TEXT_ONLY, ModelCapabilities.CODE],
			specs=ModelSpecs(
				context_length=32768,
				memory_gb=4.0,
				tokens_per_second=60.0,
				cost_per_1k_input=0.0,
				cost_per_1k_output=0.0
			),
			model_id=TEXT_FALLBACK,
			description=f"Fallback local text model ({TEXT_FALLBACK}) for resource-constrained execution",
			is_primary=False
		)
		
		# ============================================================================
		# TIER 2: Local Vision Models (Medium Speed, Free)
		# ============================================================================
		models[VISION_PRIMARY] = ModelConfig(
			name=VISION_PRIMARY,
			provider=ModelProvider.OLLAMA,
			tier=ModelTier.VISION_LOCAL,
			capabilities=[ModelCapabilities.VISION, ModelCapabilities.MULTIMODAL],
			specs=ModelSpecs(
				context_length=32768,
				memory_gb=6.0,
				tokens_per_second=35.0,
				cost_per_1k_input=0.0,
				cost_per_1k_output=0.0
			),
			model_id=VISION_PRIMARY, 
			description=f"Primary local vision model ({VISION_PRIMARY}) for visual element identification",
			is_primary=True
		)
		
		models[VISION_FALLBACK] = ModelConfig(
			name=VISION_FALLBACK,
			provider=ModelProvider.OLLAMA,
			tier=ModelTier.VISION_LOCAL,
			capabilities=[ModelCapabilities.VISION, ModelCapabilities.MULTIMODAL],
			specs=ModelSpecs(
				context_length=4096,
				memory_gb=8.0,
				tokens_per_second=12.0,
				cost_per_1k_input=0.0,
				cost_per_1k_output=0.0
			),
			model_id=VISION_FALLBACK,
			description=f"Fallback local vision model ({VISION_FALLBACK}) with proven reliability",
			is_primary=False
		)
		
		# ============================================================================
		# TIER 3: Cloud Models (Slowest, Most Expensive, Highest Quality)
		# ============================================================================
		models[CLOUD_PRIMARY] = ModelConfig(
			name=CLOUD_PRIMARY,
			provider=ModelProvider.GOOGLE,  # Update if changing to different provider
			tier=ModelTier.CLOUD,
			capabilities=[ModelCapabilities.VISION, ModelCapabilities.MULTIMODAL, ModelCapabilities.REASONING],
			specs=ModelSpecs(
				context_length=1000000,
				memory_gb=0.0,  # Cloud model
				cost_per_1k_input=0.0002,
				cost_per_1k_output=0.0008
			),
			model_id=f"models/{CLOUD_PRIMARY}" if "gemini" in CLOUD_PRIMARY else CLOUD_PRIMARY,
			description=f"Primary cloud model ({CLOUD_PRIMARY}) for complex tasks requiring vision and reasoning",
			is_primary=True
		)
		
		models[CLOUD_SECONDARY] = ModelConfig(
			name=CLOUD_SECONDARY,
			provider=ModelProvider.OPENAI,  # Update if changing to different provider
			tier=ModelTier.CLOUD,
			capabilities=[ModelCapabilities.VISION, ModelCapabilities.MULTIMODAL, ModelCapabilities.REASONING],
			specs=ModelSpecs(
				context_length=128000,
				memory_gb=0.0,  # Cloud model
				cost_per_1k_input=0.0025,
				cost_per_1k_output=0.010
			),
			model_id=CLOUD_SECONDARY,
			description=f"Secondary cloud model ({CLOUD_SECONDARY}) for complex multimodal tasks",
			is_primary=False
		)
		
		return models
	
	def _organize_by_tier(self) -> Dict[ModelTier, List[ModelConfig]]:
		"""Organize models by tier with primary models first."""
		tier_models = {tier: [] for tier in ModelTier}
		
		for model in self._models.values():
			tier_models[model.tier].append(model)
		
		# Sort each tier: primary models first, then by memory efficiency
		for tier in tier_models:
			tier_models[tier].sort(
				key=lambda m: (not m.is_primary, m.specs.memory_gb)
			)
		
		return tier_models
	
	# ============================================================================
	# Public API
	# ============================================================================
	
	def get_planner_model(self) -> ModelConfig:
		"""Get the universal planner model (o3-2025-04-16)."""
		return self._models["o3-2025-04-16"]
	
	def get_tier_models(self, tier: ModelTier) -> List[ModelConfig]:
		"""Get all models for a specific tier, ordered by priority."""
		return self._tier_models[tier].copy()
	
	def get_primary_model(self, tier: ModelTier) -> ModelConfig:
		"""Get the primary model for a tier."""
		models = self.get_tier_models(tier)
		return next((m for m in models if m.is_primary), models[0])
	
	def get_fallback_models(self, tier: ModelTier) -> List[ModelConfig]:
		"""Get fallback models for a tier (excluding primary)."""
		models = self.get_tier_models(tier)
		return [m for m in models if not m.is_primary]
	
	def get_escalation_chain(self, requires_vision: bool = False) -> List[ModelTier]:
		"""Get the escalation chain based on vision requirements.
		
		Args:
			requires_vision: If True, starts with VISION_LOCAL, else TEXT_LOCAL
			
		Returns:
			List of tiers in escalation order
		"""
		if requires_vision:
			return [ModelTier.VISION_LOCAL, ModelTier.CLOUD]
		else:
			return [ModelTier.TEXT_LOCAL, ModelTier.VISION_LOCAL, ModelTier.CLOUD]
	
	def get_model_by_name(self, name: str) -> Optional[ModelConfig]:
		"""Get a model by name."""
		return self._models.get(name)
	
	def get_model_config(self, model_name: str) -> Optional[ModelConfig]:
		"""Get model configuration by name (compatibility method for ModelRouter)."""
		return self.get_model_by_name(model_name)
	
	def get_all_models(self) -> Dict[str, ModelConfig]:
		"""Get all configured models."""
		return self._models.copy()
	
	def validate_system_compatibility(self, available_memory_gb: float) -> Dict[str, bool]:
		"""Check which local models can run given system resources."""
		compatibility = {}
		
		for name, model in self._models.items():
			if model.provider == ModelProvider.OLLAMA:
				# Need memory + 1GB buffer for system
				can_run = available_memory_gb >= (model.specs.memory_gb + 1.0)
				compatibility[name] = can_run
			else:
				compatibility[name] = True  # Cloud models always available
		
		return compatibility


# ============================================================================
# Global Configuration Instance
# ============================================================================

# This is the single source of truth for all model configurations
CENTRAL_MODEL_CONFIG = CentralModelConfig()


# ============================================================================
# Convenience Functions
# ============================================================================

def get_planner_model() -> ModelConfig:
	"""Get the universal planner model."""
	return CENTRAL_MODEL_CONFIG.get_planner_model()


def get_current_model_names() -> dict[str, str]:
	"""Get the currently configured model names for easy reference."""
	return {
		"planner": PLANNER_MODEL,
		"text_primary": TEXT_PRIMARY,
		"text_fallback": TEXT_FALLBACK,
		"vision_primary": VISION_PRIMARY,
		"vision_fallback": VISION_FALLBACK,
		"cloud_primary": CLOUD_PRIMARY,
		"cloud_secondary": CLOUD_SECONDARY
	}


def get_tier_models(tier: ModelTier) -> List[ModelConfig]:
	"""Get models for a specific tier."""
	return CENTRAL_MODEL_CONFIG.get_tier_models(tier)


def get_escalation_chain(requires_vision: bool = False) -> List[ModelTier]:
	"""Get the model escalation chain."""
	return CENTRAL_MODEL_CONFIG.get_escalation_chain(requires_vision)


def get_primary_model(tier: ModelTier) -> ModelConfig:
	"""Get the primary model for a tier."""
	return CENTRAL_MODEL_CONFIG.get_primary_model(tier)


# ============================================================================
# Configuration Validation
# ============================================================================

def validate_configuration() -> None:
	"""Validate the model configuration for consistency."""
	config = CENTRAL_MODEL_CONFIG
	
	# Ensure we have exactly one planner
	planner_models = config.get_tier_models(ModelTier.PLANNER)
	assert len(planner_models) == 1, "Must have exactly one planner model"
	assert planner_models[0].name == "o3-2025-04-16", "Planner must be o3-2025-04-16"
	
	# Ensure each tier has at least one model
	for tier in [ModelTier.TEXT_LOCAL, ModelTier.VISION_LOCAL, ModelTier.CLOUD]:
		models = config.get_tier_models(tier)
		assert len(models) > 0, f"Tier {tier} must have at least one model"
		
		# Ensure each tier has exactly one primary model
		primary_models = [m for m in models if m.is_primary]
		assert len(primary_models) == 1, f"Tier {tier} must have exactly one primary model"
	
	# Validate escalation chains
	text_chain = config.get_escalation_chain(requires_vision=False)
	vision_chain = config.get_escalation_chain(requires_vision=True)
	
	assert text_chain == [ModelTier.TEXT_LOCAL, ModelTier.VISION_LOCAL, ModelTier.CLOUD]
	assert vision_chain == [ModelTier.VISION_LOCAL, ModelTier.CLOUD]
	
	print("✅ Model configuration validation passed")


if __name__ == "__main__":
	validate_configuration()