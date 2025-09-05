# Recommended Fixes for browser-use Runner

## Immediate .env Changes

```env
# Disable problematic features temporarily
USE_REAL_CHROME_PROFILE=0
COPY_PROFILE_ONCE=0
ENABLE_DEFAULT_EXTENSIONS=0

# Increase timeouts for stability
BROWSER_START_TIMEOUT_SEC=180

# Add fallback browser path
CHROME_EXECUTABLE_FALLBACK=C:\Program Files\Google\Chrome\Application\chrome.exe
```

## Code Fixes Needed

### 1. Browser Startup Reliability (runner.py)
```python
# Add to make_browser() function
def make_browser() -> Browser:
    # Try multiple startup strategies
    strategies = [
        {"use_profile": True, "copy_profile": True},
        {"use_profile": True, "copy_profile": False}, 
        {"use_profile": False, "copy_profile": False}  # Clean fallback
    ]
    
    for strategy in strategies:
        try:
            return _create_browser_with_strategy(strategy)
        except Exception as e:
            log(f"Browser strategy failed: {strategy}, error: {e}")
            continue
    
    raise RuntimeError("All browser startup strategies failed")
```

### 2. Local LLM Message Serialization Fix
```python
# Fix in ChatLlamaCpp class
def _serialize_message(self, message):
    if hasattr(message, 'content') and isinstance(message.content, list):
        # Handle ContentPartTextParam serialization
        content_text = ""
        for part in message.content:
            if hasattr(part, 'text'):
                content_text += part.text
        return {"role": message.role, "content": content_text}
    return message
```

### 3. Enhanced Error Recovery
```python
# Add to run_one_subtask()
async def run_one_subtask_with_recovery(local_llm, browser, tools, title, instructions, success_crit, cfg):
    recovery_strategies = [
        {"restart_browser": False, "use_cloud": False},
        {"restart_browser": True, "use_cloud": False},
        {"restart_browser": True, "use_cloud": True}
    ]
    
    for strategy in recovery_strategies:
        try:
            if strategy["restart_browser"]:
                await browser.kill()
                await browser.start()
            
            llm = cloud_llm if strategy["use_cloud"] else local_llm
            return await run_one_subtask(llm, browser, tools, title, instructions, success_crit, cfg)
        except Exception as e:
            log(f"Recovery strategy failed: {strategy}, error: {e}")
            continue
    
    raise RuntimeError("All recovery strategies exhausted")
```

## Testing Priority

1. **P0**: Fix browser startup and CDP connection
2. **P1**: Fix local LLM serialization  
3. **P2**: Test complete E2E workflow
4. **P3**: Optimize for hardware specs (GTX 1660 Ti)

## Success Metrics

- Browser startup < 30 seconds
- Local LLM response time < 10 seconds  
- E2E task completion rate > 80%
- Chrome profile integration working
- Cost per task < $0.10 (mostly local processing)