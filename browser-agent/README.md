# Browser Agent: Hybrid Local/Cloud Browser Automation

A sophisticated browser automation system that leverages both local and cloud-based language models for intelligent web interaction and task execution. The system provides intelligent model routing, secure credential management, browser profile management, and comprehensive security features.

## 🚀 Features

### Core Components

- **🧠 Intelligent Model Router**: Automatically selects the best model (local/cloud) based on task complexity, cost, speed, and quality requirements
- **🔒 Security Manager**: Comprehensive security with credential encryption, domain validation, and audit logging
- **🌐 Browser Profile Manager**: Multiple browser profiles with different security levels and configurations
- **🔍 Search Integration**: Built-in search capabilities with result parsing and caching
- **💰 Budget Management**: Cost tracking and budget limits for cloud API usage
- **📊 Performance Monitoring**: Real-time monitoring of model performance and system resources

### Model Support

- **Local Models**: Ollama integration with automatic model loading/unloading
- **Cloud Models**: OpenAI, Anthropic Claude, Google Gemini
- **Hybrid Routing**: Intelligent switching between local and cloud based on requirements
- **Caching**: Response caching to reduce API costs

### Security Features

- **Encrypted Credentials**: Secure storage of API keys and sensitive data
- **Domain Validation**: Automatic detection of suspicious and malicious domains
- **Audit Logging**: Comprehensive logging of all security events
- **Profile-based Security**: Different security levels for different use cases

## 📦 Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd browser-agent
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

4. **Run the application**
   ```bash
   python main.py
   ```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
# API Keys
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
SERPER_API_KEY=your_serper_api_key_here

# Model Configuration
DEFAULT_MODEL=gpt-4o
FALLBACK_MODEL=ollama/llama3.2
OLLAMA_BASE_URL=http://localhost:11434

# Browser Configuration
HEADLESS=true
BROWSER_TIMEOUT=30000
USER_DATA_DIR=./user_data

# Security
BROWSER_AGENT_MASTER_PASSWORD=your_secure_password_here

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/browser-agent.log
```

### Model Configuration

The system supports multiple model providers and automatically selects the best model based on:

- **Task Complexity**: Simple, Moderate, Complex, Expert
- **Required Capabilities**: Vision, Code generation, Reasoning
- **Performance Requirements**: Speed, Cost, Quality
- **Resource Availability**: Local system resources, API budgets

## 🏗️ Architecture

```
browser-agent/
├── config/
│   ├── models.py          # Model configurations and presets
│   ├── profiles.py        # Browser profile management
│   └── settings.py        # Application settings
├── models/
│   ├── local_handler.py   # Ollama local model handler
│   ├── cloud_handler.py   # Cloud provider handlers
│   └── model_router.py    # Intelligent model routing
├── utils/
│   ├── serper.py         # Search API integration
│   ├── security.py       # Security utilities
│   └── logger.py         # Logging configuration
├── main.py               # Main application entry point
└── example_usage.py      # Usage examples
```

## 🔧 Usage Examples

### Basic Model Selection

```python
from config.models import ModelConfigManager, TaskComplexity
from models.model_router import ModelRouter, TaskRequirements

# Initialize components
model_config_manager = ModelConfigManager()
router = ModelRouter(model_config_manager)

# Define task requirements
task = TaskRequirements(
    complexity=TaskComplexity.MODERATE,
    requires_vision=True,
    max_cost=0.05
)

# Select best model
selected_model = await router.select_model(task)
print(f"Selected: {selected_model.name}")
```

### Browser Profile Management

```python
from config.profiles import BrowserProfileManager, ProfileType, SecurityLevel

# Initialize profile manager
profile_manager = BrowserProfileManager()

# Create a secure profile
profile = profile_manager.create_profile(
    name="banking",
    profile_type=ProfileType.BANKING,
    security_level=SecurityLevel.HIGH,
    description="High-security profile for banking"
)

# Get browser configuration
config = profile_manager.get_browser_config("banking")
```

### Security Features

```python
from utils.security import SecurityManager

# Initialize security manager
security_manager = SecurityManager()

# Validate URL
validation = security_manager.validate_and_log_url_access(
    "https://example.com",
    user_id="user123",
    session_id="session456"
)

print(f"Recommendation: {validation['recommendation']}")
print(f"Risk Score: {validation['risk_score']}")
```

### Search Integration

```python
from utils.serper import SerperAPI, SearchFilters

async with SerperAPI(api_key="your_key") as search_api:
    filters = SearchFilters(num_results=5)
    response = await search_api.web_search("browser automation", filters)
    
    for result in response.results:
        print(f"{result.title}: {result.link}")
```

## 🔒 Security

### Credential Management

- **Encryption**: All credentials are encrypted using Fernet (AES 128)
- **Master Password**: Optional master password for additional security
- **Environment Variables**: Secure loading from environment variables
- **Audit Trail**: All credential access is logged

### Domain Security

- **Trusted Domains**: Whitelist of known safe domains
- **Suspicious Patterns**: Detection of potentially malicious domains
- **Risk Scoring**: Automatic risk assessment for all URLs
- **Homograph Detection**: Basic detection of homograph attacks

### Audit Logging

- **Comprehensive Logging**: All security events are logged
- **Event Types**: Authentication, authorization, data access, security violations
- **Risk Scoring**: Automatic risk assessment for events
- **Search and Analysis**: Query audit logs for security analysis

## 📊 Monitoring and Analytics

### Model Performance

- **Response Times**: Track model response times
- **Token Usage**: Monitor token consumption and costs
- **Success Rates**: Track model reliability
- **Resource Usage**: Monitor system resources for local models

### System Health

- **Budget Tracking**: Monitor API spending against limits
- **Cache Performance**: Track cache hit rates and savings
- **Security Events**: Monitor security violations and suspicious activity
- **Profile Usage**: Track browser profile usage patterns

## 🧪 Testing

Run the test suite:

```bash
pytest tests/
```

Run specific test categories:

```bash
# Test model routing
pytest tests/test_model_router.py

# Test security features
pytest tests/test_security.py

# Test browser profiles
pytest tests/test_profiles.py
```

## 🚀 Advanced Usage

### Custom Model Configurations

```python
from config.models import ModelConfig, ModelProvider, ModelSpecs, ModelCapability

# Define custom model
custom_model = ModelConfig(
    name="Custom GPT",
    provider=ModelProvider.OPENAI,
    model_id="gpt-4-custom",
    specs=ModelSpecs(
        context_length=8192,
        max_tokens=2048,
        supports_vision=False,
        supports_function_calling=True
    ),
    capabilities=[ModelCapability.TEXT_ONLY, ModelCapability.CODE]
)

# Add to configuration manager
model_config_manager.add_custom_model(custom_model)
```

### Custom Security Policies

```python
from utils.security import DomainValidator

# Initialize validator
validator = DomainValidator()

# Add custom trusted domains
validator.add_trusted_domain("mycompany.com")
validator.add_blocked_domain("malicious-site.com")

# Custom validation
validation = validator.validate_url("https://example.com")
```

### Workflow Automation

```python
# Complete workflow example
async def automated_workflow():
    # 1. Security validation
    validation = security_manager.validate_and_log_url_access(url)
    if validation["recommendation"] == "BLOCK":
        return
    
    # 2. Model selection
    model = await router.select_model(task_requirements)
    
    # 3. Browser configuration
    config = profile_manager.get_browser_config("secure")
    
    # 4. Execute task with selected model and configuration
    # ... your browser automation code here
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: Check the inline documentation and examples
- **Issues**: Report bugs and request features via GitHub Issues
- **Examples**: See `example_usage.py` for comprehensive usage examples

## 🔮 Roadmap

- [ ] Integration with more cloud providers (Azure OpenAI, AWS Bedrock)
- [ ] Advanced caching strategies (Redis, database backends)
- [ ] Web UI for configuration and monitoring
- [ ] Plugin system for custom extensions
- [ ] Advanced security features (2FA, SSO integration)
- [ ] Performance optimization and benchmarking tools