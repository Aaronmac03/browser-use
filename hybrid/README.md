# Hybrid Local-Vision + Cloud-Reasoning System

This implementation follows the hybrid brief to combine fast local vision processing with powerful cloud reasoning.

## Architecture

### Components

1. **VisionStateBuilder** (`vision_state_builder.py`)
   - Uses MiniCPM-V 2.6 via Ollama for local vision processing
   - Converts screenshots to structured JSON with elements, fields, and affordances
   - Includes caching to avoid redundant processing
   - Generates semantic selector hints for reliable element targeting

2. **LocalActionHeuristics** (`local_action_heuristics.py`)
   - Handles simple actions (click, type, scroll, navigate) locally
   - Uses confidence thresholds to avoid ambiguous actions
   - Escalates to cloud when multiple matches or low confidence

3. **CloudPlannerClient** (`cloud_planner_client.py`)
   - Interfaces with Gemini 2.0 Flash for complex planning
   - Uses structured output for reliable action plans
   - Includes rate limiting and safety settings

4. **HandoffManager** (`handoff_manager.py`)
   - Routes between local and cloud processing
   - Maintains action history for context
   - Implements escalation logic based on failures and confidence

## Setup

### Prerequisites

1. **Ollama with MiniCPM-V 2.6**:
   ```bash
   # Install Ollama: https://ollama.ai/
   ollama pull minicpm-v:2.6
   ollama serve
   ```

2. **Google API Key**:
   - Get from: https://makersuite.google.com/app/apikey
   - Set environment variable:
   ```bash
   export GOOGLE_API_KEY="your_api_key_here"
   ```

3. **Python Dependencies**:
   ```bash
   pip install google-generativeai httpx pillow
   ```

### Configuration

The system can be configured through the component constructors:

```python
# Local vision settings
vision_builder = VisionStateBuilder(
    ollama_base_url="http://localhost:11434",
    model_name="minicpm-v:2.6", 
    confidence_threshold=0.7
)

# Local action settings
local_heuristics = LocalActionHeuristics(
    confidence_threshold=0.8,
    similarity_threshold=0.8,
    max_ambiguous_matches=1
)

# Cloud reasoning settings
cloud_client = CloudPlannerClient(
    api_key=google_api_key,
    model_name="gemini-2.0-flash-exp",
    rate_limit_calls_per_minute=10
)
```

## Usage

### Basic Example

Run the basic example:
```bash
cd examples/hybrid
python basic_example.py
```

This demonstrates:
- Taking screenshots and processing them locally
- Handling simple actions without cloud calls
- Escalating complex scenarios to cloud reasoning
- Maintaining action history and context

### Integration with Browser-Use

The hybrid system can be integrated with existing browser-use agents:

```python
from browser_use import Agent, BrowserSession
from examples.hybrid import HandoffManager, VisionStateBuilder, LocalActionHeuristics, CloudPlannerClient

# Create hybrid components
vision_builder = VisionStateBuilder()
local_heuristics = LocalActionHeuristics()
cloud_client = CloudPlannerClient(api_key="your_key")

handoff_manager = HandoffManager(
    vision_builder=vision_builder,
    local_heuristics=local_heuristics, 
    cloud_client=cloud_client
)

# Use in your automation workflow
async with BrowserSession() as session:
    # Take screenshot
    screenshot = await session.page.screenshot()
    
    # Process with hybrid system
    action, reasoning, used_cloud = await handoff_manager.process_intent(
        "click the login button",
        screenshot,
        session.page.url,
        await session.page.title()
    )
    
    # Execute the action
    # ... implementation specific to your needs
```

## Data Schemas

All components use strongly typed Pydantic schemas:

- **VisionState**: Complete page analysis from local vision
- **Action**: Standardized action format for both local and cloud
- **PlannerRequest/Response**: Cloud reasoning interface
- **HistoryItem**: Action history tracking

## Performance Characteristics

### Local Processing
- **Speed**: ~1-3 seconds per screenshot on CPU
- **Accuracy**: High for simple UI elements
- **Cost**: Free after initial model download

### Cloud Processing  
- **Speed**: ~2-5 seconds per planning request
- **Accuracy**: High for complex multi-step reasoning
- **Cost**: ~$0.01-0.05 per planning request

### Handoff Logic
- **Local first**: Simple, unambiguous actions
- **Cloud escalation**: Multiple matches, failures, complex flows
- **Failure recovery**: Automatic escalation after 2 consecutive failures

## Acceptance Tests

The implementation includes the acceptance scenarios from the brief:

1. **Login page**: Local handles email/password fields and sign-in button
2. **Search + paginate**: Local executes search and pagination clicks
3. **Comparison flow**: Cloud planning for vendor comparison decisions  
4. **Ambiguity**: Multiple "Add to cart" buttons trigger cloud escalation
5. **Failure recovery**: Broken selectors cause cloud re-planning

## Extensions

The brief suggests several enhancements that can be added:

1. **Visual Diff Optimization**: Track element changes between actions
2. **Interaction Zones**: Group related elements for better context
3. **Failure Classification**: Different escalation strategies per failure type
4. **Batch Planning**: Get multiple contingent plans from cloud

## Monitoring

The HandoffManager provides state summaries for monitoring:

```python
state = handoff_manager.get_current_state_summary()
# Returns: failures, history, cloud usage, current page info, etc.
```

## Limitations

- Requires Ollama setup for local vision
- MiniCPM-V may be slower on CPU-only systems
- Selector hint quality depends on vision model accuracy
- Cloud rate limiting applies (10 calls/minute default)

This implementation provides the foundation described in the hybrid brief and can be extended based on specific automation requirements.