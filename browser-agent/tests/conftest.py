"""
Pytest configuration and fixtures for browser-agent testing.

This module provides shared fixtures for browser sessions, models, workflows,
and mock implementations for external services.
"""

import asyncio
import os
import tempfile
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

# Import browser-agent modules
from config.models import ModelConfigManager, ModelConfig, TaskComplexity, ModelProvider, ModelSpecs, ModelCapability
from config.profiles import BrowserProfileManager, ProfileType, SecurityLevel
from config.settings import Settings
from models.model_router import ModelRouter, TaskRequirements, RoutingStrategy
from models.local_handler import OllamaModelHandler
from models.cloud_handler import CloudModelManager
from utils.security import SecurityManager, AuditEventType, SecurityLevel as SecurityLevelEnum
from utils.serper import SerperAPI
from workflows.workflow_base import BaseWorkflow, WorkflowConfig, WorkflowStatus, WorkflowPriority


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def test_env_vars():
    """Set up test environment variables."""
    test_vars = {
        "OPENAI_API_KEY": "test_openai_key",
        "ANTHROPIC_API_KEY": "test_anthropic_key",
        "SERPER_API_KEY": "test_serper_key",
        "BROWSER_AGENT_MASTER_PASSWORD": "test_password",
        "LOG_LEVEL": "DEBUG",
        "HEADLESS": "true",
        "BROWSER_TIMEOUT": "30000"
    }
    
    # Store original values
    original_values = {}
    for key, value in test_vars.items():
        original_values[key] = os.environ.get(key)
        os.environ[key] = value
    
    yield test_vars
    
    # Restore original values
    for key, original_value in original_values.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value


@pytest.fixture
def mock_settings(temp_dir, test_env_vars):
    """Create mock settings for testing."""
    settings = Settings()
    settings.user_data_dir = str(temp_dir / "user_data")
    settings.log_file = str(temp_dir / "test.log")
    settings.credentials_file = str(temp_dir / "credentials.enc")
    settings.audit_log_file = str(temp_dir / "audit.log")
    return settings


@pytest.fixture
def sample_model_configs():
    """Create sample model configurations for testing."""
    return [
        ModelConfig(
            name="gpt-4o-mini",
            provider=ModelProvider.OPENAI,
            model_id="gpt-4o-mini",
            specs=ModelSpecs(
                context_length=128000,
                max_tokens=16384,
                supports_vision=True,
                supports_function_calling=True,
                cost_per_1k_tokens=0.00015,
                tokens_per_second=50.0
            ),
            capabilities=[ModelCapability.TEXT_ONLY, ModelCapability.VISION, ModelCapability.CODE]
        ),
        ModelConfig(
            name="claude-3-5-sonnet",
            provider=ModelProvider.ANTHROPIC,
            model_id="claude-3-5-sonnet-20241022",
            specs=ModelSpecs(
                context_length=200000,
                max_tokens=8192,
                supports_vision=True,
                supports_function_calling=True,
                cost_per_1k_tokens=0.003,
                tokens_per_second=30.0
            ),
            capabilities=[ModelCapability.TEXT_ONLY, ModelCapability.VISION, ModelCapability.CODE]
        ),
        ModelConfig(
            name="llama3.2",
            provider=ModelProvider.OLLAMA,
            model_id="llama3.2:latest",
            specs=ModelSpecs(
                context_length=8192,
                max_tokens=2048,
                supports_vision=False,
                supports_function_calling=True,
                estimated_memory_gb=4.0,
                tokens_per_second=25.0
            ),
            capabilities=[ModelCapability.TEXT_ONLY, ModelCapability.CODE]
        )
    ]


@pytest.fixture
def mock_model_config_manager(sample_model_configs):
    """Create a mock model configuration manager."""
    manager = ModelConfigManager()
    
    # Add sample models
    for model in sample_model_configs:
        manager.add_custom_model(model)
    
    return manager


@pytest.fixture
def mock_browser_profile_manager(temp_dir):
    """Create a mock browser profile manager."""
    profiles_dir = temp_dir / "profiles"
    profiles_dir.mkdir(exist_ok=True)
    
    manager = BrowserProfileManager(profiles_dir=str(profiles_dir))
    
    # Create test profiles
    manager.create_profile(
        name="test_secure",
        profile_type=ProfileType.BANKING,
        security_level=SecurityLevel.HIGH,
        description="High-security test profile"
    )
    
    manager.create_profile(
        name="test_default",
        profile_type=ProfileType.DEFAULT,
        security_level=SecurityLevel.MEDIUM,
        description="Default test profile"
    )
    
    return manager


@pytest.fixture
def mock_security_manager(temp_dir):
    """Create a mock security manager."""
    audit_log_file = temp_dir / "audit.log"
    credentials_file = temp_dir / "credentials.enc"
    
    manager = SecurityManager(
        audit_log_file=str(audit_log_file),
        credentials_file=str(credentials_file),
        master_password="test_password"
    )
    
    return manager


@pytest.fixture
def mock_ollama_handler():
    """Create a mock Ollama model handler."""
    handler = Mock(spec=OllamaModelHandler)
    handler.is_available = AsyncMock(return_value=True)
    handler.list_models = AsyncMock(return_value=["llama3.2:latest", "llama3.2-vision:latest"])
    handler.load_model = AsyncMock(return_value=True)
    handler.unload_model = AsyncMock(return_value=True)
    handler.generate = AsyncMock(return_value="Mock response from Ollama")
    return handler


@pytest.fixture
def mock_cloud_manager():
    """Create a mock cloud model manager."""
    manager = Mock(spec=CloudModelManager)
    manager.is_available = AsyncMock(return_value=True)
    manager.get_available_models = AsyncMock(return_value=["gpt-4o-mini", "claude-3-5-sonnet"])
    manager.generate = AsyncMock(return_value="Mock response from cloud")
    manager.get_token_usage = AsyncMock(return_value={"input_tokens": 100, "output_tokens": 50})
    return manager


@pytest.fixture
def mock_serper_api():
    """Create a mock Serper API client."""
    api = Mock(spec=SerperAPI)
    api.web_search = AsyncMock(return_value={
        "results": [
            {
                "title": "Test Result 1",
                "link": "https://example.com/1",
                "snippet": "Test snippet 1"
            },
            {
                "title": "Test Result 2", 
                "link": "https://example.com/2",
                "snippet": "Test snippet 2"
            }
        ]
    })
    return api


@pytest.fixture
def model_router(mock_model_config_manager, mock_ollama_handler, mock_cloud_manager):
    """Create a model router with mocked dependencies."""
    return ModelRouter(
        model_config_manager=mock_model_config_manager,
        local_handler=mock_ollama_handler,
        cloud_manager=mock_cloud_manager,
        default_strategy=RoutingStrategy.BALANCED
    )


@pytest.fixture
def sample_task_requirements():
    """Create sample task requirements for testing."""
    return {
        "simple": TaskRequirements(
            complexity=TaskComplexity.SIMPLE,
            requires_vision=False,
            requires_code=False,
            max_cost=0.01
        ),
        "moderate_vision": TaskRequirements(
            complexity=TaskComplexity.MODERATE,
            requires_vision=True,
            requires_code=False,
            max_cost=0.05
        ),
        "complex_code": TaskRequirements(
            complexity=TaskComplexity.COMPLEX,
            requires_vision=False,
            requires_code=True,
            max_cost=0.10
        ),
        "expert": TaskRequirements(
            complexity=TaskComplexity.EXPERT,
            requires_vision=True,
            requires_code=True,
            max_cost=0.20
        )
    }


@pytest.fixture
def mock_browser_session():
    """Create a mock browser session."""
    session = Mock()
    session.start = AsyncMock()
    session.stop = AsyncMock()
    session.navigate = AsyncMock()
    session.take_screenshot = AsyncMock(return_value=b"fake_screenshot_data")
    session.get_page_content = AsyncMock(return_value="<html><body>Test content</body></html>")
    session.click_element = AsyncMock()
    session.type_text = AsyncMock()
    session.scroll = AsyncMock()
    return session


@pytest.fixture
def sample_workflow_config():
    """Create sample workflow configuration."""
    return WorkflowConfig(
        workflow_id="test_workflow_001",
        name="Test Workflow",
        description="A test workflow for unit testing",
        priority=WorkflowPriority.NORMAL,
        timeout=300.0,
        max_retries=3,
        browser_profile="test_default",
        security_level="medium",
        parallel_execution=False,
        continue_on_error=False,
        save_screenshots=True,
        save_results=True
    )


class MockWorkflow(BaseWorkflow):
    """Mock workflow implementation for testing."""
    
    def __init__(self, config: WorkflowConfig, model_router=None, profile_manager=None, security_manager=None, **kwargs):
        # Use mock objects if not provided
        if model_router is None:
            model_router = AsyncMock()
            # Mock the select_model method to return a mock model config
            mock_model_config = MagicMock()
            mock_model_config.model_id = "test_model"
            model_router.select_model.return_value = mock_model_config
        if profile_manager is None:
            profile_manager = MagicMock()
        if security_manager is None:
            security_manager = AsyncMock()
            # Mock security validation to always pass
            security_manager.validate_url.return_value = True
            
        super().__init__(config, model_router, profile_manager, security_manager)
        self.executed_steps = []
        self.should_fail = False
        self.fail_at_step = None
    
    async def define_steps(self) -> List[Any]:
        """Define workflow steps."""
        from workflows.workflow_base import WorkflowStep
        return [
            WorkflowStep(name="step1", description="Navigate to test page", task="Navigate to test page"),
            WorkflowStep(name="step2", description="Fill form", task="Fill form"),
            WorkflowStep(name="step3", description="Submit form", task="Submit form")
        ]
    
    async def validate_prerequisites(self) -> bool:
        """Validate workflow prerequisites."""
        return True  # Mock always returns True for testing
    
    async def execute_step(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a workflow step."""
        step_name = step["name"]
        self.executed_steps.append(step_name)
        
        if self.should_fail and (self.fail_at_step is None or step_name == self.fail_at_step):
            raise Exception(f"Mock failure at step {step_name}")
        
        return {"step": step_name, "status": "completed", "result": f"Mock result for {step_name}"}
    
    async def _execute_single_step(self, step):
        """Override to avoid creating real LLM instances in tests."""
        # Track executed steps
        self.executed_steps.append(step.name)
        
        # Check if we should fail at this step
        if self.should_fail and (self.fail_at_step is None or step.name == self.fail_at_step):
            raise Exception(f"Mock failure at step {step.name}")
        
        # Mock step execution without browser-use Agent
        await asyncio.sleep(0.1)  # Simulate some work
        
        # Mock result similar to what Agent.run() would return
        mock_result = {
            "success": True,
            "message": f"Mock execution of step: {step.task}",
            "data": {"step_name": step.name}
        }
        
        return mock_result


@pytest.fixture
def mock_workflow(sample_workflow_config):
    """Create a mock workflow instance."""
    return MockWorkflow(sample_workflow_config)


@pytest.fixture
def mock_system_resources():
    """Mock system resource monitoring."""
    with patch('psutil.virtual_memory') as mock_memory, \
         patch('psutil.cpu_percent') as mock_cpu:
        
        # Mock 8GB available memory, 30% CPU usage
        mock_memory.return_value.available = 8 * 1024 ** 3
        mock_memory.return_value.percent = 60.0
        mock_cpu.return_value = 30.0
        
        yield {
            "available_memory_gb": 8.0,
            "memory_percent": 60.0,
            "cpu_percent": 30.0
        }


@pytest.fixture
def mock_file_system(temp_dir):
    """Create mock file system structure."""
    # Create directory structure
    (temp_dir / "logs").mkdir(exist_ok=True)
    (temp_dir / "screenshots").mkdir(exist_ok=True)
    (temp_dir / "downloads").mkdir(exist_ok=True)
    (temp_dir / "cache").mkdir(exist_ok=True)
    (temp_dir / "profiles").mkdir(exist_ok=True)
    
    # Create some test files
    (temp_dir / "logs" / "test.log").write_text("Test log content")
    (temp_dir / "cache" / "test_cache.json").write_text('{"test": "data"}')
    
    return temp_dir


@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Cleanup after each test."""
    yield
    # Any cleanup code can go here
    pass


# Async fixtures
@pytest_asyncio.fixture
async def async_model_router(model_router):
    """Async version of model router fixture."""
    return model_router


@pytest_asyncio.fixture
async def async_mock_workflow(mock_workflow):
    """Async version of mock workflow fixture."""
    return mock_workflow


# Parametrized fixtures for testing different scenarios
@pytest.fixture(params=[
    RoutingStrategy.COST_OPTIMIZED,
    RoutingStrategy.SPEED_OPTIMIZED,
    RoutingStrategy.QUALITY_OPTIMIZED,
    RoutingStrategy.BALANCED,
    RoutingStrategy.LOCAL_FIRST,
    RoutingStrategy.CLOUD_FIRST
])
def routing_strategy(request):
    """Parametrized routing strategy fixture."""
    return request.param


@pytest.fixture(params=[
    TaskComplexity.SIMPLE,
    TaskComplexity.MODERATE,
    TaskComplexity.COMPLEX,
    TaskComplexity.EXPERT
])
def task_complexity(request):
    """Parametrized task complexity fixture."""
    return request.param


@pytest.fixture(params=[
    SecurityLevelEnum.LOW,
    SecurityLevelEnum.MEDIUM,
    SecurityLevelEnum.HIGH,
    SecurityLevelEnum.CRITICAL
])
def security_level(request):
    """Parametrized security level fixture."""
    return request.param


# Helper functions for tests
def create_test_audit_event(event_type: AuditEventType = AuditEventType.DATA_ACCESS):
    """Create a test audit event."""
    from utils.security import AuditEvent
    
    return AuditEvent(
        timestamp=datetime.now(),
        event_type=event_type,
        security_level=SecurityLevelEnum.MEDIUM,
        user_id="test_user",
        session_id="test_session",
        source_ip="127.0.0.1",
        action="test_action",
        resource="test_resource",
        success=True,
        details={"test": "data"},
        risk_score=0.5
    )


def assert_model_selection_valid(selected_model: ModelConfig, requirements: TaskRequirements):
    """Assert that a selected model meets the requirements."""
    if requirements.requires_vision:
        assert selected_model.supports_capability(ModelCapability.VISION), \
            f"Model {selected_model.name} doesn't support vision but it's required"
    
    if requirements.requires_code:
        assert selected_model.supports_capability(ModelCapability.CODE), \
            f"Model {selected_model.name} doesn't support code but it's required"
    
    if requirements.preferred_providers:
        assert selected_model.provider in requirements.preferred_providers, \
            f"Model {selected_model.name} provider {selected_model.provider} not in preferred providers"
    
    if requirements.avoid_providers:
        assert selected_model.provider not in requirements.avoid_providers, \
            f"Model {selected_model.name} provider {selected_model.provider} in avoided providers"


# Markers for different test categories
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.security = pytest.mark.security
pytest.mark.performance = pytest.mark.performance
pytest.mark.slow = pytest.mark.slow