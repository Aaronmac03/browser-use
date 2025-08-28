# Centralized Model Configuration System

This document describes the new centralized model configuration system that provides a single source of truth for all model settings, eliminating the need to update multiple files when changing models.

## 🎯 Overview

The centralized configuration implements your specified three-tier routing architecture:

- **Universal Planning**: Every query gets o3-2025-04-16 single-shot planning
- **Simple Tier Progression**: Text → Vision → Cloud with automatic fallback
- **No Complex Decision Trees**: Streamlined routing based on vision requirements
- **Single Source of Truth**: All model configurations in one file

## 📁 File Structure

```
browser-agent/
├── config/
│   ├── central_model_config.py    # ✨ SINGLE SOURCE OF TRUTH
│   ├── models.py                  # Legacy (still needed for compatibility)
│   └── enhanced_models.py         # Legacy (still needed for compatibility)
├── models/
│   ├── enhanced_model_router.py   # Updated to use centralized config
│   ├── model_router.py           # Updated to use centralized config
│   └── task_planner.py          # Updated to use centralized config
└── test_centralized_config.py    # Comprehensive test suite
```

## 🏗️ Architecture

### Universal Planner
```
Every Query → o3-2025-04-16 Planning → Clarified Intent + Strategy
```

### Three-Tier Execution
```
Tier 1: Text Local    → qwen3:8b (primary), qwen3:4b (fallback)
Tier 2: Vision Local  → qwen2.5vl:7b (primary), llava:13b (fallback)  
Tier 3: Cloud         → gemini-2.5-flash (primary), o3-2025-04-16 (secondary)
```

### Escalation Chains
```
Text-first:   Text Local → Vision Local → Cloud
Vision-first: Vision Local → Cloud
```

## 🔧 Making Changes - Super Easy! ⚡

**To change any model, edit ONLY the variables at the top of this file:**
```
browser-agent/config/central_model_config.py
```

### 🎯 Quick Changes (Edit These Variables)

```python
# At the top of central_model_config.py:

PLANNER_MODEL = "claude-3-5-sonnet"      # Change planner
TEXT_PRIMARY = "deepseek-r1:8b"          # Change primary text model  
TEXT_FALLBACK = "qwen3:4b"               # Change fallback text model
VISION_PRIMARY = "minicpm-v:8b"          # Change primary vision model
VISION_FALLBACK = "llava:13b"            # Change fallback vision model
CLOUD_PRIMARY = "gpt-4o"                 # Change primary cloud model
CLOUD_SECONDARY = "claude-3-5-sonnet"   # Change secondary cloud model
```

**That's it! All routers automatically use the new models.** 🚀

### 📋 Examples

#### Switch Planner from o3 to Claude
```python
PLANNER_MODEL = "claude-3-5-sonnet"  # Was: "o3-2025-04-16"
```

#### Switch Text Models to DeepSeek  
```python
TEXT_PRIMARY = "deepseek-r1:8b"    # Was: "qwen3:8b"
TEXT_FALLBACK = "deepseek-r1:4b"   # Was: "qwen3:4b"
```

#### Switch Cloud to OpenAI
```python
CLOUD_PRIMARY = "gpt-4o"              # Was: "gemini-2.5-flash"
CLOUD_SECONDARY = "gpt-4o-mini"       # Was: "o3-2025-04-16"
```

### 🧪 Testing Changes
```bash
cd browser-agent
python3 test_flexible_config.py    # Test your changes
python3 test_centralized_config.py # Full validation
```

## 📊 Current Configuration

### Universal Planner
- **Model**: o3-2025-04-16
- **Purpose**: Query clarification, task coordination, Serper API decisions
- **Usage**: Every single query, regardless of complexity

### Tier 1: Local Text Models
- **Primary**: qwen3:8b (8GB RAM, 45 tok/s)
- **Fallback**: qwen3:4b (4GB RAM, 60 tok/s)
- **Use Cases**: Navigation, form filling, keyboard shortcuts, scrolling

### Tier 2: Local Vision Models  
- **Primary**: qwen2.5vl:7b (6GB RAM, 35 tok/s)
- **Fallback**: llava:13b (8GB RAM, 12 tok/s)
- **Use Cases**: Visual element identification, screenshot analysis, UI understanding

### Tier 3: Cloud Models
- **Primary**: gemini-2.5-flash ($0.0002/1K tokens, 1M context)
- **Secondary**: o3-2025-04-16 ($0.06/1K tokens, 200K context)
- **Use Cases**: Complex reasoning, high-quality responses, fallback for failed local models

## 🧪 Testing

Run the comprehensive test suite:
```bash
cd browser-agent
python3 test_centralized_config.py
```

The test validates:
- ✅ Configuration structure and consistency
- ✅ Universal planner setup (o3-2025-04-16)
- ✅ Three-tier architecture with primary/fallback models
- ✅ Escalation chains (text-first vs vision-first)
- ✅ System compatibility checks
- ✅ Routing scenario demonstrations

## 🔄 Migration Guide

### Before (Multiple Files)
```
browser-agent/models/enhanced_model_router.py:
    self._text_only_models = ["deepseek-r1:32b", ...]
    self._vision_local_models = ["llava:13b", ...]
    
browser-agent/models/model_router.py:
    self._planning_model = "gpt-4o"
    self._execution_chain = ["granite3.2-vision", ...]
    
browser-agent/models/task_planner.py:
    self.planning_model = "o3-2025-04-16"
```

### After (Centralized)
```
browser-agent/config/central_model_config.py:
    # All model configurations in one place
    CENTRAL_MODEL_CONFIG = CentralModelConfig()
    
# All other files import from central config:
from config.central_model_config import (
    get_planner_model,
    get_tier_models, 
    get_escalation_chain
)
```

## 🚦 Integration Points

### Enhanced Model Router
```python
from config.central_model_config import CENTRAL_MODEL_CONFIG, get_tier_models

class EnhancedModelRouter:
    def __init__(self, ...):
        self._central_config = CENTRAL_MODEL_CONFIG
        
    async def _get_tier_models(self, tier):
        return get_tier_models(tier)  # Uses centralized config
```

### Task Planner
```python
from config.central_model_config import get_planner_model

class TaskPlanner:
    def __init__(self, ...):
        planner_config = get_planner_model()
        self.planning_model = planner_config.name  # Always o3-2025-04-16
```

### Base Model Router
```python
from config.central_model_config import get_escalation_chain, ModelTier

class ModelRouter:
    def get_model_for_task(self, task_requirements):
        escalation_chain = get_escalation_chain(
            requires_vision=task_requirements.requires_vision
        )
        first_tier = escalation_chain[0]
        return self._central_config.get_primary_model(first_tier).name
```

## 🎛️ Configuration API

### Core Functions
```python
# Get universal planner
planner = get_planner_model()  # Returns o3-2025-04-16 config

# Get models by tier
text_models = get_tier_models(ModelTier.TEXT_LOCAL)
vision_models = get_tier_models(ModelTier.VISION_LOCAL)  
cloud_models = get_tier_models(ModelTier.CLOUD)

# Get escalation chains
text_chain = get_escalation_chain(requires_vision=False)
# → [TEXT_LOCAL, VISION_LOCAL, CLOUD]

vision_chain = get_escalation_chain(requires_vision=True)  
# → [VISION_LOCAL, CLOUD]

# Get primary/fallback models
primary_text = get_primary_model(ModelTier.TEXT_LOCAL)
fallback_models = CENTRAL_MODEL_CONFIG.get_fallback_models(ModelTier.TEXT_LOCAL)
```

### Configuration Object
```python
CENTRAL_MODEL_CONFIG.get_all_models()          # All configured models
CENTRAL_MODEL_CONFIG.get_model_by_name("qwen3:8b")  # Specific model
CENTRAL_MODEL_CONFIG.validate_system_compatibility(16.0)  # Check system resources
```

## 🔍 Validation

The system includes built-in validation:

```python
from config.central_model_config import validate_configuration

validate_configuration()  # Throws assertion errors if invalid
```

Validates:
- ✅ Exactly one planner model (o3-2025-04-16)
- ✅ Each tier has at least one model  
- ✅ Each tier has exactly one primary model
- ✅ Escalation chains are properly formed
- ✅ No configuration inconsistencies

## 📈 Benefits

### Maintenance
- **Before**: Update 5+ files when changing models
- **After**: Update 1 file (`central_model_config.py`)

### Consistency  
- **Before**: Risk of inconsistent model references across files
- **After**: Single source of truth eliminates inconsistencies

### Architecture Clarity
- **Before**: Complex decision trees and scattered routing logic
- **After**: Clear three-tier progression with vision-based routing

### Testing
- **Before**: Manual verification across multiple files
- **After**: Comprehensive automated test suite

## 🎯 Next Steps

1. **Monitor Production**: Watch routing decisions and escalation patterns
2. **Performance Tuning**: Adjust model parameters based on real usage
3. **Additional Models**: Add new models to tiers as they become available
4. **Resource Optimization**: Fine-tune memory requirements and fallback logic

## 🚨 Important Notes

- **Backward Compatibility**: Legacy config files still exist for compatibility
- **Provider Mapping**: Central config maps to existing ModelConfig objects
- **System Resources**: Local model availability depends on system memory
- **Cost Awareness**: Cloud models have cost implications (tracked in config)

---

**Remember**: To change models, edit ONLY `browser-agent/config/central_model_config.py` 🎯