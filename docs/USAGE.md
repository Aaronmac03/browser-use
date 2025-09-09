# Browser-Use Usage Guide

## Overview

This guide covers how to use browser-use with the optimized hybrid LLM architecture for privacy-focused, cost-effective web automation on GTX 1660 Ti hardware.

## Quick Start

### 1. Environment Setup

Copy the example environment file and configure your settings:
```bash
cp .env.example .env
```

Edit `.env` with your configuration:
```bash
# Local LLM Configuration (Primary for privacy)
LOCAL_LLM_URL=http://localhost:8080
LLAMACPP_MODEL_PATH=./models/qwen2.5-14b-instruct-q4_k_m.gguf

# Cloud Models (Strategic use only)
ANTHROPIC_API_KEY=your_claude_api_key
OPENAI_API_KEY=your_openai_api_key

# Web Search
SERPER_API_KEY=your_serper_api_key

# Chrome Profile
CHROME_PROFILE_PATH=C:\Users\YourUsername\AppData\Local\Google\Chrome\User Data\Default
```

### 2. Start Local LLM Server

Launch the optimized llama.cpp server for your GTX 1660 Ti:
```bash
cd browser-use
python hardware_optimization.py
```

This will:
- Auto-detect your GTX 1660 Ti (6GB VRAM)
- Configure 35 GPU layers for optimal performance
- Set up 6 CPU threads for your i7-9750H
- Enable memory optimization for 16GB RAM
- Target <45s response times

### 3. Run Your First Automation

```python
#!/usr/bin/env python3
from browser_use import Agent
from browser_use.browser import create_browser_session
import asyncio

async def main():
    # Create browser session with your Chrome profile
    browser = await create_browser_session(
        profile_path="C:\\Users\\YourUsername\\AppData\\Local\\Google\\Chrome\\User Data\\Default"
    )
    
    # Create agent with hybrid LLM setup
    agent = Agent(
        task="Search for 'Python web scraping' and summarize the first 3 results",
        llm_provider="hybrid",  # Uses local LLM + strategic cloud calls
        browser=browser
    )
    
    # Execute the task
    result = await agent.run()
    print(result)
    
    await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## Hybrid Architecture

### Local LLM (Primary)
- **Model**: Qwen 2.5 7B Instruct Q4_K_M (3.5GB)
- **Purpose**: All web content processing, DOM analysis, action decisions
- **Benefits**: Complete privacy, no data leaves your PC, cost-free operation
- **Performance**: <45s response time with GPU acceleration

### Cloud Models (Strategic)
- **Claude-3.5-Sonnet**: Complex planning, multi-step strategy, edge cases
- **GPT-4**: Fallback for critical decisions requiring high reasoning
- **Usage**: <5% of total operations, only for planning/coordination
- **Privacy**: Web content never sent to cloud, only high-level task descriptions

### Decision Flow
1. **Local First**: All DOM processing and basic actions use local LLM
2. **Cloud Escalation**: Only complex multi-step planning uses cloud
3. **Privacy Boundary**: Web content stays local, only abstract plans go to cloud

## Chrome Profile Integration

### Automatic Profile Setup
The system automatically:
- Copies your Chrome v136+ profile for compatibility
- Preserves all your logged-in accounts
- Maintains cookies and session data
- No domain restrictions (full account access)

### Manual Profile Configuration
```python
# Specify custom profile
browser = await create_browser_session(
    profile_path="/path/to/your/chrome/profile",
    headless=False,  # See browser actions
    window_size=(1920, 1080)
)
```

## Performance Optimization

### GTX 1660 Ti Specific Settings
```python
# Automatically configured by hardware_optimization.py
llm_config = {
    'n_gpu_layers': 35,        # Utilize 6GB VRAM effectively
    'n_threads': 6,            # Optimize for i7-9750H
    'n_ctx': 8192,            # Context size
    'n_batch': 512,           # Batch size for throughput
    'n_ubatch': 128,          # Micro-batch for memory
    'use_mlock': True,        # Memory optimization
    'use_mmap': False,        # Better with GPU acceleration
}
```

### Memory Management
- **Total RAM**: 16GB optimally utilized
- **VRAM Usage**: ~5.5GB of 6GB used (35 layers)
- **System RAM**: ~8GB available for browser and OS
- **Swap**: Minimal usage due to mlock optimization

### Response Time Targets
- **Simple actions**: 15-30 seconds (click, type, navigate)
- **Complex analysis**: 30-45 seconds (DOM processing, multi-element)
- **Planning tasks**: 45-90 seconds (includes cloud coordination)

## Common Workflows

### Research and Information Gathering
```python
# Optimized for privacy - everything stays local
task = "Research the top 5 project management tools, create a comparison table with pricing, features, and ratings"

agent = Agent(
    task=task,
    llm_provider="local_primary",  # Force local-only for sensitive research
    browser=browser
)
```

### Account Management
```python
# Uses your existing logged-in accounts
task = "Check my email inbox and summarize any urgent messages from the last 24 hours"

agent = Agent(
    task=task,
    llm_provider="hybrid",
    browser=browser,
    use_accounts=True  # Leverage existing sessions
)
```

### Complex Multi-Step Tasks
```python
# Hybrid approach for complex workflows
task = "Find 10 relevant scientific papers on 'machine learning in healthcare', download PDFs, and create a summary document with key findings"

agent = Agent(
    task=task,
    llm_provider="hybrid",  # Cloud planning + local execution
    browser=browser,
    max_steps=50  # Allow complex multi-step execution
)
```

### Data Extraction and Processing
```python
# Privacy-first data extraction
task = "Extract all product information from this e-commerce site and save to CSV"

agent = Agent(
    task=task,
    llm_provider="local_only",  # Ensure data never leaves local system
    browser=browser,
    output_format="structured"  # Get clean data format
)
```

## Error Handling and Recovery

### Common Issues and Solutions

**Local LLM Server Not Responding**
```bash
# Check server status
curl http://localhost:8080/health

# Restart with diagnostics
python hardware_optimization.py --verbose --diagnostics
```

**GPU Memory Issues**
```python
# Reduce GPU layers if needed
llm_config['n_gpu_layers'] = 30  # Reduce from 35 to 30
```

**Chrome Profile Errors**
```python
# Create fresh profile copy
browser = await create_browser_session(
    profile_path=None,  # Use temporary profile
    extensions=['ublock_origin']  # Add essential extensions
)
```

### Automatic Recovery
The system includes automatic recovery for:
- Network timeouts (retry with exponential backoff)
- GPU memory issues (automatic layer reduction)
- Chrome crashes (session restart with state preservation)
- LLM server disconnection (automatic reconnection)

## Monitoring and Debugging

### Performance Monitoring
```bash
# Real-time performance metrics
python validate_performance.py --monitor

# Hardware utilization
python check-gpu-status.py
```

### Debug Mode
```python
agent = Agent(
    task=task,
    debug=True,        # Verbose logging
    save_screenshots=True,  # Visual debugging
    log_level="DEBUG"
)
```

### Log Analysis
```bash
# View recent automation logs
tail -f runtime/logs/agent.log

# Performance analysis
python performance_analyzer.py --last-hour
```

## Advanced Configuration

### Custom Model Setup
```python
# Use different local model
llm_config = {
    'model_path': './models/custom-model.gguf',
    'n_gpu_layers': 35,
    'custom_prompt_template': 'custom_template.txt'
}
```

### Multi-Agent Coordination
```python
# Parallel task execution
agents = [
    Agent(task="Research task A", llm_provider="local"),
    Agent(task="Research task B", llm_provider="local"),
    Agent(task="Coordinate results", llm_provider="hybrid")
]

results = await asyncio.gather(*[agent.run() for agent in agents])
```

### Custom Tool Integration
```python
# Add custom tools for specific workflows
from browser_use.tools import register_tool

@register_tool
def custom_data_processor(data):
    """Custom tool for domain-specific data processing."""
    # Your custom logic here
    return processed_data
```

## Security and Privacy

### Data Flow Guarantee
- **Web content**: Never leaves local system
- **Screenshots**: Processed locally only
- **User data**: Remains in local Chrome profile
- **API calls**: Only abstract task descriptions to cloud
- **File downloads**: Saved locally, not uploaded

### Network Configuration
```python
# Restrict network access if needed
browser_config = {
    'allow_external_requests': False,  # Block external API calls
    'whitelist_domains': ['specific-domain.com'],  # Optional restrictions
    'use_proxy': True,  # Route through VPN/proxy
}
```

This usage guide provides everything needed to effectively use the optimized browser-use system on your GTX 1660 Ti hardware with maximum privacy and minimal cost.