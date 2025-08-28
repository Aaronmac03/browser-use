# On-Demand Vision Detection

Browser-use now supports intelligent on-demand vision detection, allowing agents to start with efficient text-only processing and automatically escalate to vision when needed.

## Overview

Traditional browser automation either uses vision for all steps (expensive and slow) or never uses vision (limited capability). On-demand vision detection provides the best of both worlds:

- **Start Efficient**: Begin each step with text-only processing
- **Escalate When Needed**: Automatically detect when vision is required
- **Learn from Experience**: Remember which actions typically need vision
- **Optimize Performance**: Reduce costs and improve speed

## How It Works

### 1. Text-First Strategy
Each step begins with text-only processing using the DOM representation and page content.

### 2. Vision Need Detection
The system detects vision requirements through:
- **Model Feedback**: When models explicitly request vision in their thinking
- **Action Results**: When actions fail due to lack of visual information
- **Error Analysis**: Automatic detection of vision-related error messages
- **Learned Patterns**: Historical data about which actions need vision

### 3. Automatic Escalation
When vision is needed:
- The system flags the current step for vision
- Next iteration includes screenshot and visual analysis
- The model can complete the task with full visual context

### 4. Experience Learning
The system learns and remembers:
- Which action types typically need vision
- URL patterns that require visual processing
- User task patterns that benefit from vision

## Usage

### Basic Setup

```python
from browser_use import Agent
from browser_use.llm import OpenAILLM

llm = OpenAILLM(model="gpt-4o-mini")

agent = Agent(
    task="Navigate to example.com and describe the visual layout",
    llm=llm,
    use_on_demand_vision=True,  # Enable on-demand vision
    use_vision=True,  # Base vision capability
)

result = await agent.run()
```

### Configuration Options

```python
agent = Agent(
    task="Your task here",
    llm=llm,
    
    # On-demand vision settings
    use_on_demand_vision=True,   # Enable the feature
    use_vision=True,             # Base vision capability (required)
    
    # Other settings work as normal
    max_actions_per_step=3,
    max_failures=3,
)
```

## When Vision is Triggered

### Automatic Triggers

1. **Model Requests**: When the model's thinking includes phrases like:
   - "I need to see the page"
   - "I need vision to complete this task"
   - "I can't see the visual elements"

2. **Action Failures**: When actions fail with vision-related errors:
   - "Cannot see the element"
   - "Need visual information"
   - "Unable to locate visually"

3. **Learned Patterns**: Based on historical data:
   - Action types that previously needed vision
   - Specific URLs that require visual processing
   - Task patterns that benefit from screenshots

### Manual Triggers

Models can request vision by including specific phrases in their thinking:

```
"thinking": "I need to see the page layout to understand where to click next"
```

## Benefits

### Performance Improvements
- **Faster Execution**: Text-only processing is significantly faster
- **Lower Costs**: Reduced token usage from unnecessary screenshots
- **Better Efficiency**: Vision only when actually needed

### Intelligent Adaptation
- **Context Aware**: Learns which situations need vision
- **Task Specific**: Adapts to different types of tasks
- **Progressive Learning**: Gets smarter over time

### Maintained Capability
- **Full Vision Access**: When needed, full visual capabilities are available
- **No Functionality Loss**: All existing vision features work normally
- **Backward Compatible**: Existing code continues to work

## Examples

### Simple Navigation Task
```python
# This task will likely start text-only and escalate when describing visuals
agent = Agent(
    task="Go to google.com and describe the visual design elements",
    llm=llm,
    use_on_demand_vision=True,
)
```

### Form Filling Task
```python
# This task might use text-only for navigation, vision for complex forms
agent = Agent(
    task="Fill out the contact form on example.com with my information",
    llm=llm,
    use_on_demand_vision=True,
)
```

### Data Extraction Task
```python
# This task will likely stay text-only throughout
agent = Agent(
    task="Extract all product names and prices from the catalog page",
    llm=llm,
    use_on_demand_vision=True,
)
```

## Best Practices

### Task Design
- Write tasks that allow for progressive complexity
- Include visual requirements explicitly when needed
- Let the system learn your usage patterns

### Model Selection
- Works best with models that have good reasoning capabilities
- Models should be able to express when they need visual information
- GPT-4 and similar models work well with this feature

### Monitoring
- Check the learned patterns to understand your usage
- Monitor escalation frequency to optimize task design
- Use logging to see when and why vision is triggered

## Technical Details

### State Management
The system tracks:
- `current_step_needs_vision`: Whether the current step requires vision
- `vision_requirements_history`: Learned patterns of vision needs

### Detection Keywords
The system looks for these phrases to detect vision needs:
- "need to see", "can't see", "cannot see"
- "visual", "screenshot", "image"
- "need vision", "require vision"
- "see the page", "view the page"

### Learning Algorithm
- Records action type + URL combinations that need vision
- Uses historical data to predict future vision needs
- Balances efficiency with capability

## Migration Guide

### From Traditional Vision
```python
# Old approach - always use vision
agent = Agent(task="...", llm=llm, use_vision=True)

# New approach - on-demand vision
agent = Agent(
    task="...", 
    llm=llm, 
    use_vision=True,           # Keep this True
    use_on_demand_vision=True  # Add this
)
```

### From Text-Only
```python
# Old approach - never use vision
agent = Agent(task="...", llm=llm, use_vision=False)

# New approach - smart vision
agent = Agent(
    task="...", 
    llm=llm, 
    use_vision=True,           # Enable vision capability
    use_on_demand_vision=True  # Use it intelligently
)
```

## Troubleshooting

### Vision Not Triggering
- Ensure `use_vision=True` (base capability required)
- Check that your model can express vision needs in thinking
- Verify task requires visual information

### Too Much Vision Usage
- Review your task descriptions for visual language
- Check learned patterns for over-triggering
- Consider more specific text-based instructions

### Performance Issues
- Monitor escalation frequency
- Optimize task descriptions to be more text-friendly
- Use appropriate model sizes for your needs

## Future Enhancements

- More sophisticated learning algorithms
- Better prediction of vision needs
- Integration with task-specific patterns
- Performance analytics and optimization suggestions