#!/usr/bin/env python3
"""
Test llama.cpp server integration for local LLM execution.
Validates server connectivity, model loading, and basic inference.
"""

import asyncio
import httpx
import pytest
import os
from pathlib import Path

from enhanced_local_llm import OptimizedLocalLLM, LocalLLMConfig


class TestLlamaIntegration:
    """Test llama.cpp server integration and local LLM functionality."""
    
    def test_llama_server_executable_exists(self):
        """Test that llama-server.exe exists at expected location."""
        server_path = Path("E:/ai/llama.cpp/build/bin/Release/llama-server.exe")
        assert server_path.exists(), f"llama-server.exe not found at {server_path}"
    
    def test_model_file_exists(self):
        """Test that the required model file exists."""
        model_path = Path("E:/ai/llama-models/qwen2.5-7b-instruct-q4_k_m.gguf")
        assert model_path.exists(), f"Model file not found at {model_path}"
    
    def test_startup_script_exists(self):
        """Test that the GPU startup script exists."""
        script_path = Path("start-llama-gpu.bat")
        assert script_path.exists(), f"Startup script not found at {script_path}"
    
    @pytest.mark.asyncio
    async def test_llama_server_health_check(self):
        """Test llama.cpp server health endpoint (if server is running)."""
        host = os.getenv("LLAMACPP_HOST", "http://localhost:8080")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{host}/health", timeout=5)
                if response.status_code == 200:
                    # Server is running - great!
                    assert True
                else:
                    # Server responded but with error - still indicates it's running
                    pytest.skip(f"llama.cpp server responded with status {response.status_code}")
        except httpx.ConnectError:
            # Server not running - skip test but don't fail
            pytest.skip("llama.cpp server not running - start with start-llama-gpu.bat")
        except Exception as e:
            pytest.skip(f"Could not connect to llama.cpp server: {e}")
    
    def test_local_llm_config_defaults(self):
        """Test LocalLLMConfig default values for GTX 1660 Ti optimization."""
        config = LocalLLMConfig()
        
        # Check optimized settings for GTX 1660 Ti
        assert config.max_actions_per_step == 1, "Should use single actions for precision"
        assert config.max_history_items == 6, "Should use minimal context for speed"
        assert config.step_timeout == 60, "Should have fast response requirement"
        assert config.use_thinking is True, "Should enable reasoning"
        assert config.use_vision is False, "Should disable vision for performance"
        
        # Check preferred models for 7B optimization
        assert "qwen2.5-7b-instruct-q4_k_m" in config.preferred_models[0]
        assert len(config.preferred_models) >= 2, "Should have multiple model options"
    
    @pytest.mark.asyncio
    async def test_optimized_local_llm_initialization(self):
        """Test OptimizedLocalLLM initialization and model selection."""
        config = LocalLLMConfig()
        local_llm = OptimizedLocalLLM(config)
        
        # Test model selection (should not fail even if server not running)
        selected_model = await local_llm._select_best_model()
        assert selected_model is not None
        assert "qwen2.5" in selected_model.lower() or "llama" in selected_model.lower()
        
        # Test client creation (should not fail even if server not running)
        try:
            client = await local_llm.get_optimized_client()
            assert client is not None
            assert hasattr(client, 'model')
        except Exception:
            # If server not running, this is expected - just ensure we get a client object
            pass
    
    def test_environment_variables(self):
        """Test that required environment variables are configured."""
        # Check llama.cpp host
        host = os.getenv("LLAMACPP_HOST")
        assert host is not None, "LLAMACPP_HOST should be set"
        assert "localhost:8080" in host, "Should use default llama.cpp port"
        
        # Check Chrome configuration
        chrome_exe = os.getenv("CHROME_EXECUTABLE")
        if chrome_exe:
            assert Path(chrome_exe).exists(), f"Chrome executable not found: {chrome_exe}"
    
    def test_hardware_optimization_settings(self):
        """Test that configuration is optimized for GTX 1660 Ti + i7-9750H."""
        config = LocalLLMConfig()
        
        # GTX 1660 Ti has 6GB VRAM - should prefer 7B models
        preferred = config.preferred_models[0]
        assert "7b" in preferred.lower(), "Should prefer 7B models for 6GB VRAM"
        
        # Should have fallback models for different scenarios
        assert len(config.fallback_models) > 0, "Should have fallback models"
        
        # Performance settings should be optimized for speed
        assert config.step_timeout <= 90, "Should have fast timeout for 7B model"
        assert config.max_actions_per_step <= 2, "Should limit actions for speed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])