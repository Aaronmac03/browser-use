# Browser Agent Testing Framework

This directory contains a comprehensive testing framework for the browser-agent project, including unit tests, integration tests, security tests, and performance benchmarks.

## 🏗️ Test Structure

```
tests/
├── conftest.py              # Pytest fixtures and configuration
├── test_model_router.py     # Model routing logic tests
├── test_workflows.py        # Workflow execution tests
├── test_security.py         # Security functionality tests
└── README.md               # This file
```

## 🧪 Test Categories

### Unit Tests (`pytest -m unit`)
- **Fast, isolated tests** that test individual components
- Mock external dependencies
- Focus on business logic and algorithms
- Should run in under 30 seconds total

### Integration Tests (`pytest -m integration`)
- **End-to-end tests** that test component interactions
- May use real external services (with mocking where appropriate)
- Test complete workflows and user scenarios
- May take several minutes to complete

### Security Tests (`pytest -m security`)
- **Security-focused tests** for credential management, domain validation, and audit logging
- Test security policies and access controls
- Verify encryption and data protection
- Test against common attack patterns

### Performance Tests (`pytest -m performance`)
- **Benchmark tests** for performance-critical components
- Memory usage and execution time measurements
- Load testing and stress testing
- Concurrent execution testing

## 🚀 Running Tests

### Using the Test Runner Script

The easiest way to run tests is using the provided test runner:

```bash
# Run unit tests with coverage
python run_tests.py --type unit

# Run all tests
python run_tests.py --type all

# Run specific test file
python run_tests.py --test tests/test_model_router.py

# Run with linting and security scans
python run_tests.py --type unit --lint --security-scan

# Set up test environment only
python run_tests.py --setup-only
```

### Using Pytest Directly

```bash
# Run all unit tests
pytest -m "not integration and not security and not slow" -v

# Run integration tests
pytest -m integration -v

# Run security tests
pytest -m security -v

# Run performance tests
pytest -m performance --benchmark-only -v

# Run specific test class
pytest tests/test_model_router.py::TestModelRouter -v

# Run with coverage
pytest --cov=. --cov-report=html --cov-report=term-missing -v
```

## 🔧 Test Configuration

### Environment Variables

Set these environment variables for testing:

```bash
export BROWSER_AGENT_MASTER_PASSWORD="test_password"
export HEADLESS="true"
export LOG_LEVEL="DEBUG"
export OPENAI_API_KEY="test_key"  # For integration tests
export ANTHROPIC_API_KEY="test_key"  # For integration tests
export SERPER_API_KEY="test_key"  # For integration tests
```

### Pytest Configuration

The `pytest.ini` file contains test configuration including:
- Test discovery patterns
- Markers for different test types
- Coverage settings
- Timeout configuration

## 🏷️ Test Markers

Use pytest markers to categorize and run specific types of tests:

```bash
# Run only model router tests
pytest -m model_router

# Run tests that don't require network
pytest -m "not requires_network"

# Run fast tests only
pytest -m "not slow"

# Run security-related tests
pytest -m "security or credentials or domain_validation"
```

Available markers:
- `unit`, `integration`, `security`, `performance`, `slow`
- `model_router`, `workflows`, `security_manager`
- `credentials`, `domain_validation`, `audit_logging`
- `requires_browser`, `requires_network`, `requires_ollama`, `requires_api_keys`

## 🧩 Test Fixtures

The `conftest.py` file provides numerous fixtures for testing:

### Core Fixtures
- `temp_dir`: Temporary directory for test files
- `test_env_vars`: Test environment variables
- `mock_settings`: Mock application settings

### Component Fixtures
- `mock_model_config_manager`: Mock model configuration
- `mock_browser_profile_manager`: Mock browser profiles
- `mock_security_manager`: Mock security manager
- `model_router`: Configured model router for testing

### Mock Services
- `mock_ollama_handler`: Mock local model handler
- `mock_cloud_manager`: Mock cloud model manager
- `mock_serper_api`: Mock search API client
- `mock_browser_session`: Mock browser session

### Test Data
- `sample_model_configs`: Sample model configurations
- `sample_task_requirements`: Sample task requirements
- `sample_workflow_config`: Sample workflow configuration

## 📊 Coverage Reports

Test coverage reports are generated in multiple formats:

- **Terminal**: Summary displayed after test run
- **HTML**: Detailed report in `htmlcov/` directory
- **XML**: Machine-readable report in `coverage.xml`

View HTML coverage report:
```bash
python -m http.server 8000 -d htmlcov
# Open http://localhost:8000 in browser
```

## 🔍 Debugging Tests

### Running Tests in Debug Mode

```bash
# Run with verbose output and no capture
pytest -v -s tests/test_model_router.py::test_specific_function

# Run with pdb debugger
pytest --pdb tests/test_model_router.py::test_specific_function

# Run with custom logging
pytest --log-cli-level=DEBUG tests/
```

### Common Debug Patterns

```python
# In test files, use these patterns for debugging:

def test_something():
    # Add print statements (use -s flag to see output)
    print(f"Debug info: {some_variable}")
    
    # Use assert with custom messages
    assert result == expected, f"Expected {expected}, got {result}"
    
    # Use pytest.set_trace() for interactive debugging
    import pytest; pytest.set_trace()
```

## 🚨 Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Make sure you're in the browser-agent directory
   cd browser-agent
   
   # Install test dependencies
   pip install -r test_requirements.txt
   ```

2. **Permission Errors**
   ```bash
   # Make sure test runner is executable
   chmod +x run_tests.py
   
   # Check file permissions for test directories
   ls -la tests/
   ```

3. **Browser Tests Failing**
   ```bash
   # Install browser dependencies
   playwright install chromium firefox
   
   # For headless testing, set environment variable
   export HEADLESS=true
   ```

4. **Async Test Issues**
   ```bash
   # Make sure pytest-asyncio is installed
   pip install pytest-asyncio
   
   # Use @pytest.mark.asyncio for async tests
   ```

### Test Data Cleanup

Tests automatically clean up temporary files, but you can manually clean up:

```bash
# Remove test artifacts
rm -rf htmlcov/ .coverage test-results-*.xml *.log
rm -rf logs/ screenshots/ downloads/ cache/ profiles/
rm -f bandit-report.json safety-report.json
```

## 📈 Performance Testing

### Benchmark Tests

Performance tests use `pytest-benchmark` for accurate measurements:

```python
def test_model_selection_performance(benchmark, router, sample_task_requirements):
    requirements = sample_task_requirements["simple"]
    
    # Benchmark the model selection
    result = benchmark(router.select_model, requirements)
    
    assert result is not None
```

### Memory Profiling

Use `memory-profiler` for memory usage testing:

```python
from memory_profiler import profile

@profile
def test_memory_usage():
    # Test code here
    pass
```

### Load Testing

Use `locust` for load testing workflows:

```bash
# Run load test
locust -f tests/load_test.py --headless --users 10 --spawn-rate 2 --run-time 30s
```

## 🔐 Security Testing

### Credential Testing

Security tests verify:
- Credential encryption/decryption
- Master password protection
- Secure storage and retrieval
- Access logging

### Domain Validation Testing

Tests verify:
- Trusted domain recognition
- Suspicious pattern detection
- Homograph attack detection
- Risk scoring accuracy

### Audit Logging Testing

Tests verify:
- Event logging completeness
- Search functionality
- Security event detection
- Report generation

## 🤖 Continuous Integration

The GitHub Actions workflow (`.github/workflows/browser-agent-ci.yml`) runs:

1. **Multi-Python Version Testing** (3.9, 3.10, 3.11, 3.12)
2. **Parallel Test Execution** (unit, integration, security)
3. **Code Quality Checks** (linting, formatting, type checking)
4. **Security Scanning** (vulnerability detection)
5. **Performance Testing** (benchmarks)
6. **Docker Testing** (containerized execution)
7. **Coverage Reporting** (Codecov integration)

### CI Environment Variables

The CI workflow uses these environment variables:
- `BROWSER_AGENT_MASTER_PASSWORD`: Test password
- `HEADLESS`: Browser headless mode
- `LOG_LEVEL`: Logging level for tests

## 📚 Writing New Tests

### Test Naming Convention

```python
# Test files: test_*.py
# Test classes: Test*
# Test functions: test_*

class TestModelRouter:
    def test_select_model_simple_task(self):
        pass
    
    def test_select_model_with_vision_requirement(self):
        pass
```

### Using Fixtures

```python
def test_something(mock_model_config_manager, sample_task_requirements):
    # Use fixtures as function parameters
    requirements = sample_task_requirements["simple"]
    models = mock_model_config_manager.list_models()
    
    assert len(models) > 0
```

### Async Tests

```python
import pytest

@pytest.mark.asyncio
async def test_async_function(async_mock_workflow):
    result = await async_mock_workflow.execute()
    assert result.status == WorkflowStatus.COMPLETED
```

### Parametrized Tests

```python
@pytest.mark.parametrize("complexity", [
    TaskComplexity.SIMPLE,
    TaskComplexity.MODERATE,
    TaskComplexity.COMPLEX
])
def test_model_selection_by_complexity(router, complexity):
    requirements = TaskRequirements(complexity=complexity)
    model = router.select_model(requirements)
    assert model is not None
```

### Mock Usage

```python
from unittest.mock import Mock, patch, AsyncMock

def test_with_mocks():
    # Mock objects
    mock_handler = Mock()
    mock_handler.is_available.return_value = True
    
    # Mock async methods
    mock_handler.generate = AsyncMock(return_value="response")
    
    # Patch methods
    with patch('module.function') as mock_func:
        mock_func.return_value = "mocked"
        # Test code here
```

## 🎯 Best Practices

1. **Test Isolation**: Each test should be independent and not rely on other tests
2. **Clear Naming**: Test names should clearly describe what is being tested
3. **Arrange-Act-Assert**: Structure tests with clear setup, execution, and verification
4. **Mock External Dependencies**: Use mocks for external services and slow operations
5. **Test Edge Cases**: Include tests for error conditions and boundary cases
6. **Keep Tests Fast**: Unit tests should run quickly; use integration tests for slower scenarios
7. **Use Fixtures**: Leverage pytest fixtures for common test setup
8. **Document Complex Tests**: Add comments explaining complex test logic
9. **Test Both Success and Failure**: Test both happy path and error scenarios
10. **Maintain Test Data**: Keep test data realistic but minimal

## 📞 Support

For questions about the testing framework:

1. Check this README for common patterns and solutions
2. Look at existing tests for examples
3. Review the `conftest.py` file for available fixtures
4. Check the GitHub Actions workflow for CI configuration
5. Create an issue for bugs or feature requests