#!/usr/bin/env python3
"""Debug script to check model names and structure."""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.models import ModelConfigManager

def main():
    manager = ModelConfigManager()
    models = manager.list_models()
    
    print("Available models:")
    for i, model in enumerate(models):
        print(f"{i}: {model.name} (key: {model.name})")
        print(f"   Provider: {model.provider}")
        print(f"   Model ID: {model.model_id}")
        print()
    
    # Test retrieval by name
    if models:
        first_model = models[0]
        print(f"Trying to retrieve model by name: '{first_model.name}'")
        retrieved = manager.get_model_config(first_model.name)
        print(f"Retrieved: {retrieved}")
        
        # Try with model_id instead
        print(f"Trying to retrieve model by model_id: '{first_model.model_id}'")
        retrieved_by_id = manager.get_model_config(first_model.model_id)
        print(f"Retrieved by ID: {retrieved_by_id}")

if __name__ == "__main__":
    main()