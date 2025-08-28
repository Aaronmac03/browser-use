#!/usr/bin/env python3
"""
Basic functionality test for browser-agent components.
This script tests core functionality without external dependencies.
"""

import sys
import os
import tempfile
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all core modules can be imported."""
    print("Testing imports...")
    
    try:
        from config.models import ModelConfigManager, TaskComplexity, ModelProvider
        print("✓ Config models imported successfully")
    except Exception as e:
        print(f"✗ Failed to import config.models: {e}")
        return False
    
    try:
        from config.profiles import BrowserProfileManager, ProfileType, SecurityLevel
        print("✓ Config profiles imported successfully")
    except Exception as e:
        print(f"✗ Failed to import config.profiles: {e}")
        return False
    
    try:
        from config.settings import Settings
        print("✓ Config settings imported successfully")
    except Exception as e:
        print(f"✗ Failed to import config.settings: {e}")
        return False
    
    try:
        from utils.security import SecurityManager, CredentialManager, DomainValidator, AuditLogger
        print("✓ Security utilities imported successfully")
    except Exception as e:
        print(f"✗ Failed to import utils.security: {e}")
        return False
    
    try:
        from models.model_router import ModelRouter, TaskRequirements
        print("✓ Model router imported successfully")
    except Exception as e:
        print(f"✗ Failed to import models.model_router: {e}")
        return False
    
    return True

def test_credential_manager():
    """Test basic credential manager functionality."""
    print("\nTesting CredentialManager...")
    
    try:
        from utils.security import CredentialManager
        
        with tempfile.TemporaryDirectory() as temp_dir:
            cred_file = Path(temp_dir) / "test_creds.enc"
            
            # Initialize credential manager
            manager = CredentialManager(
                credentials_file=str(cred_file),
                master_password="test_password"
            )
            
            # Store a credential
            manager.store_credential("test_service", "api_key", "secret_value_123")
            print("✓ Credential stored successfully")
            
            # Retrieve the credential
            retrieved = manager.get_credential("test_service", "api_key")
            assert retrieved == "secret_value_123", f"Expected 'secret_value_123', got '{retrieved}'"
            print("✓ Credential retrieved successfully")
            
            # List credentials
            creds = manager.list_credentials()
            assert "test_service" in creds, "Service not found in credentials list"
            assert "api_key" in creds["test_service"], "API key not found in service credentials"
            print("✓ Credentials listed successfully")
            
            # Delete credential
            deleted = manager.delete_credential("test_service", "api_key")
            assert deleted, "Failed to delete credential"
            print("✓ Credential deleted successfully")
            
    except Exception as e:
        print(f"✗ CredentialManager test failed: {e}")
        return False
    
    return True

def test_domain_validator():
    """Test basic domain validator functionality."""
    print("\nTesting DomainValidator...")
    
    try:
        from utils.security import DomainValidator
        
        validator = DomainValidator()
        
        # Test trusted domain
        result = validator.validate_url("https://google.com/search")
        assert result["is_trusted"], "Google.com should be trusted"
        assert result["recommendation"] == "ALLOW", f"Expected ALLOW, got {result['recommendation']}"
        print("✓ Trusted domain validation works")
        
        # Test unknown domain
        result = validator.validate_url("https://unknown-domain-12345.com")
        assert not result["is_trusted"], "Unknown domain should not be trusted"
        print("✓ Unknown domain validation works")
        
        # Test adding trusted domain
        validator.add_trusted_domain("example.com")
        result = validator.validate_url("https://example.com")
        assert result["is_trusted"], "Added domain should be trusted"
        print("✓ Adding trusted domain works")
        
    except Exception as e:
        print(f"✗ DomainValidator test failed: {e}")
        return False
    
    return True

def test_model_config_manager():
    """Test basic model configuration manager functionality."""
    print("\nTesting ModelConfigManager...")
    
    try:
        from config.models import ModelConfigManager, ModelConfig, ModelProvider, ModelSpecs, ModelCapability, TaskComplexity
        
        manager = ModelConfigManager()
        
        # List available models
        models = manager.list_models()
        print(f"✓ Found {len(models)} available models")
        
        # Test model filtering by provider
        openai_models = manager.list_models(provider=ModelProvider.OPENAI)
        print(f"✓ Found {len(openai_models)} OpenAI models")
        
        # Test model filtering by capability
        vision_models = manager.list_models(capability=ModelCapability.VISION)
        print(f"✓ Found {len(vision_models)} vision-capable models")
        
        # Test getting model by model_id
        if models:
            first_model = models[0]
            retrieved_model = manager.get_model_config(first_model.model_id)
            assert retrieved_model is not None, "Failed to retrieve model by model_id"
            assert retrieved_model.name == first_model.name, "Retrieved model name mismatch"
            print("✓ Model retrieval by model_id works")
        
        # Test task-based model recommendations
        simple_models = manager.get_models_for_task(TaskComplexity.SIMPLE)
        print(f"✓ Found {len(simple_models)} models for simple tasks")
        
    except Exception as e:
        print(f"✗ ModelConfigManager test failed: {e}")
        return False
    
    return True

def test_security_manager():
    """Test basic security manager functionality."""
    print("\nTesting SecurityManager...")
    
    try:
        from utils.security import SecurityManager
        
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_file = Path(temp_dir) / "audit.log"
            cred_file = Path(temp_dir) / "creds.enc"
            
            manager = SecurityManager(
                audit_log_file=str(audit_file),
                credentials_file=str(cred_file),
                master_password="test_password"
            )
            
            # Test URL validation with logging
            result = manager.validate_and_log_url_access("https://google.com")
            assert result["is_trusted"], "Google should be trusted"
            print("✓ URL validation with logging works")
            
            # Test credential access with logging
            manager.credential_manager.store_credential("test", "key", "value")
            retrieved = manager.get_secure_credential("test", "key", user_id="test_user")
            assert retrieved == "value", "Failed to retrieve credential securely"
            print("✓ Secure credential access works")
            
    except Exception as e:
        print(f"✗ SecurityManager test failed: {e}")
        return False
    
    return True

def main():
    """Run all basic tests."""
    print("=== Browser Agent Basic Functionality Tests ===\n")
    
    tests = [
        test_imports,
        test_credential_manager,
        test_domain_validator,
        test_model_config_manager,
        test_security_manager
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
                print("✓ PASSED\n")
            else:
                failed += 1
                print("✗ FAILED\n")
        except Exception as e:
            failed += 1
            print(f"✗ FAILED with exception: {e}\n")
    
    print("=== Test Summary ===")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total: {passed + failed}")
    
    if failed == 0:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n❌ {failed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())