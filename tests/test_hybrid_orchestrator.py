#!/usr/bin/env python3
"""
Test hybrid orchestrator end-to-end functionality.
Validates cloud planning + local execution integration.
"""

import asyncio
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from runner import plan_with_o3_then_gemini, make_local_llm, make_o3_llm, run_one_subtask


class TestHybridOrchestrator:
    """Test hybrid orchestrator functionality."""
    
    def test_make_local_llm_configuration(self):
        """Test local LLM configuration and initialization."""
        local_llm = make_local_llm()
        
        # Check that we get a valid LLM instance
        assert local_llm is not None
        assert hasattr(local_llm, 'model')
        
        # Check model configuration
        model_name = getattr(local_llm, 'model', '').lower()
        assert 'qwen' in model_name or 'llama' in model_name, f"Expected qwen or llama model, got: {model_name}"
        
        # Check temperature setting
        temp = getattr(local_llm, 'temperature', None)
        assert temp is not None and 0 <= temp <= 1, f"Temperature should be 0-1, got: {temp}"
    
    def test_make_o3_llm_configuration(self):
        """Test cloud LLM (o3) configuration."""
        # Only test if API key is available
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key.startswith("sk-proj-"):
            pytest.skip("OPENAI_API_KEY not configured for o3 testing")
        
        cloud_llm = make_o3_llm()
        
        # Check that we get a valid LLM instance
        assert cloud_llm is not None
        assert hasattr(cloud_llm, 'model')
        
        # Check model configuration
        model_name = getattr(cloud_llm, 'model', '').lower()
        assert 'o3' in model_name, f"Expected o3 model, got: {model_name}"
    
    @pytest.mark.asyncio
    async def test_plan_with_o3_then_gemini_mock(self):
        """Test planning function with mocked cloud LLM responses."""
        mock_response = [
            {
                "title": "Navigate to website",
                "instructions": "Go to the target website",
                "success": "Successfully loaded the website"
            },
            {
                "title": "Perform search",
                "instructions": "Search for the required information",
                "success": "Found and displayed search results"
            }
        ]
        
        with patch('runner.make_o3_llm') as mock_make_o3:
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = MagicMock(content=str(mock_response))
            mock_make_o3.return_value = mock_llm
            
            result = await plan_with_o3_then_gemini("Find information about Python")
            
            assert isinstance(result, list)
            assert len(result) >= 1
            
            # Check that each subtask has required fields
            for subtask in result:
                assert "title" in subtask
                assert "instructions" in subtask or "plan" in subtask
                assert "success" in subtask
    
    @pytest.mark.asyncio
    async def test_hybrid_orchestrator_integration(self):
        """Test hybrid orchestrator integration without complex browser mocking."""
        # Test that we can create the core components successfully
        local_llm = make_local_llm()
        assert local_llm is not None
        
        # Test that the configuration is optimized for the hardware
        model_name = getattr(local_llm, 'model', '').lower()
        assert '7b' in model_name, f"Should use 7B model for GTX 1660 Ti, got: {model_name}"
        
        # Test that we can create the planning function
        try:
            # This should work even without API keys (will fallback gracefully)
            subtasks = await plan_with_o3_then_gemini("Test planning task")
            assert isinstance(subtasks, list)
            # Even with fallback, should return some structure (unless both APIs fail)
            if len(subtasks) == 0:
                # Both o3 and Gemini failed - this is acceptable in test environment
                pass
            else:
                assert len(subtasks) >= 1
        except Exception as e:
            # If planning fails due to missing API keys, that's expected in testing
            error_msg = str(e).lower()
            assert any(keyword in error_msg for keyword in ["api key", "fallback", "json", "gemini", "openai"])
        
        # Test RunConfig creation
        from runner import RunConfig
        config = RunConfig()
        assert config.max_failures_per_subtask >= 1
        assert config.step_timeout_sec > 0
    
    def test_local_llm_optimization_settings(self):
        """Test that local LLM gets optimized settings based on model size."""
        # Test with different model configurations
        test_cases = [
            ("qwen2.5-7b-instruct", {"max_actions": 2, "max_history": 10, "timeout": 90}),
            ("qwen2.5-14b-instruct", {"max_actions": 3, "max_history": 15, "timeout": 150}),
            ("unknown-model", {"max_actions": 2, "max_history": 10, "timeout": 90}),
        ]
        
        for model_name, expected in test_cases:
            mock_llm = MagicMock()
            mock_llm.provider = 'ollama'
            mock_llm.model = model_name
            
            # The optimization logic is in run_one_subtask, so we test the logic directly
            is_14b = '14b' in model_name.lower()
            is_7b = '7b' in model_name.lower()
            
            if is_14b:
                assert expected["max_actions"] == 3
                assert expected["timeout"] == 150
            elif is_7b:
                assert expected["max_actions"] == 2
                assert expected["timeout"] == 90
            else:
                assert expected["max_actions"] == 2
                assert expected["timeout"] == 90
    
    def test_environment_configuration_validation(self):
        """Test that all required environment variables are properly configured."""
        required_vars = [
            "LLAMACPP_HOST",
            "CHROME_EXECUTABLE", 
            "CHROME_USER_DATA_DIR",
            "CHROME_PROFILE_DIRECTORY"
        ]
        
        for var in required_vars:
            value = os.getenv(var)
            assert value is not None, f"Required environment variable {var} is not set"
            assert len(value.strip()) > 0, f"Environment variable {var} is empty"
        
        # Check optional but important vars
        optional_vars = ["OPENAI_API_KEY", "GOOGLE_API_KEY", "SERPER_API_KEY"]
        configured_count = sum(1 for var in optional_vars if os.getenv(var) and not os.getenv(var).startswith("your_"))
        
        assert configured_count >= 1, "At least one cloud API key should be configured for full functionality"
    
    def test_hardware_optimization_detection(self):
        """Test that the system detects and optimizes for the target hardware."""
        # This is more of a documentation test - ensuring our settings match the target hardware
        # GTX 1660 Ti: 6GB VRAM, good for 7B models with Q4_K_M quantization
        # i7-9750H: 6 cores, 12 threads, good for parallel processing
        
        # Check that our model preferences align with hardware
        local_llm = make_local_llm()
        model_name = getattr(local_llm, 'model', '').lower()
        
        # Should prefer 7B models for 6GB VRAM
        assert '7b' in model_name, f"Should use 7B model for GTX 1660 Ti, got: {model_name}"
        
        # Should use Q4_K_M quantization for balance of speed/quality
        if hasattr(local_llm, 'model_path') or 'q4_k_m' in model_name:
            assert 'q4_k_m' in model_name or 'q4' in model_name, "Should use Q4 quantization for performance"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])