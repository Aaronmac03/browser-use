# DOM-First Search Optimization

## Overview

This implementation adds a fast DOM-first search optimization to the hybrid agent that can bypass vision processing entirely when search inputs are detectable via CSS selectors. This provides significant speed improvements for common search scenarios.

## Key Features

### 1. Direct CDP DOM Queries
- Uses Chrome DevTools Protocol (CDP) for fastest possible DOM queries
- Bypasses browser-use API overhead when possible
- Falls back to browser-use API if CDP fails

### 2. Common Search Input Detection
The system looks for search inputs using these CSS selectors:
```css
input[type="search"]
input[aria-label*="Search" i]
input[placeholder*="Search" i]
input[name="searchTerm"]
input[id*="search" i]
input[name*="search" i]
input[class*="search" i]
```

### 3. Automatic Triggering
DOM-first search is automatically triggered when:
- The `type` primitive detects a search-related target (contains "search")
- After navigation to search-friendly sites (proactive detection)

### 4. Multi-Layer Fallback
1. **Primary**: Direct CDP DOM queries and input
2. **Secondary**: Browser-use DOM state API
3. **Tertiary**: Standard vision-based approach (existing behavior)

## Implementation Details

### Core Methods

#### `_try_dom_search_input(search_query: str)`
Main entry point for DOM-first search optimization. Tries CDP approach first, then falls back to browser-use API.

#### `_execute_cdp_search_input(cdp_session, node_id, search_query, selector)`
Executes search directly via CDP:
- Focuses the input element
- Clears existing content
- Types search query
- Presses Enter to submit

#### `_probe_dom_search_capability()`
Probes for search inputs without executing a search. Used for proactive detection after navigation.

### Integration Points

#### Type Primitive Handler
```python
elif action.primitive == "type":
    # DOM-first search optimization: Check if this looks like a search operation
    if action.value and action.target and 'search' in action.target.lower():
        print_status("🔍 Detected search operation, trying DOM-first approach...", Colors.BLUE)
        dom_success, dom_result = await self._try_dom_search_input(action.value)
        if dom_success:
            result = dom_result
            skip_vision = True
            print_status("✅ DOM-first search successful, skipping vision", Colors.GREEN)
        else:
            print_status("⚠️ DOM-first search failed, falling back to normal type", Colors.YELLOW)
            result = await self._type(action.target, action.value)
    else:
        result = await self._type(action.target, action.value)
```

#### Navigation Handler
After successful navigation, the system proactively probes for search capabilities:
```python
# DOM-first optimization: After navigation, check if we can proactively detect search inputs
if result.extracted_content and "successfully navigated" in result.extracted_content.lower():
    try:
        # Quick DOM probe for search inputs (no vision needed)
        dom_success, dom_result = await self._probe_dom_search_capability()
        if dom_success:
            print_status("🎯 DOM search capability detected on this page", Colors.GREEN)
        else:
            print_status("ℹ️ No obvious search inputs detected via DOM", Colors.BLUE)
    except Exception as e:
        print_status(f"DOM probe failed: {e}", Colors.YELLOW)
```

## Performance Benefits

### Speed Improvements
- **Vision Bypass**: Eliminates vision model processing time (typically 2-5 seconds)
- **Direct Input**: Uses fastest possible input method via CDP
- **Immediate Detection**: CSS selectors provide instant element detection

### Resource Savings
- **No Screenshot Processing**: Avoids screenshot capture and analysis
- **No Vision Model Calls**: Saves local/cloud vision model usage
- **Reduced Memory**: No image data processing

### Reliability
- **Deterministic**: CSS selectors are more reliable than vision-based element detection
- **Fast Failure**: Quick fallback if DOM approach fails
- **Graceful Degradation**: Maintains existing behavior as fallback

## Usage Examples

### Automatic Triggering
```python
# This will automatically trigger DOM-first optimization
action = GenericAction(
    primitive="type",
    target="search input",  # Contains "search" - triggers optimization
    value="milk 40222",
    notes="Search for milk in zip code 40222"
)
```

### Manual Probing
```python
# Check if DOM search is available on current page
success, result = await agent._probe_dom_search_capability()
if success:
    # DOM search is available, can use fast path
    dom_success, dom_result = await agent._try_dom_search_input("search query")
```

## Testing

Run the test script to see the optimization in action:
```bash
python test_dom_search.py
```

The test demonstrates:
- Navigation to search-friendly sites
- Automatic DOM capability detection
- Fast DOM-first search execution
- Fallback behavior

## Supported Sites

The optimization works particularly well on:
- Google, Bing, DuckDuckGo (search engines)
- Amazon, eBay, Walmart (e-commerce)
- YouTube, GitHub, Stack Overflow (content sites)
- Any site using standard search input patterns

## Future Enhancements

1. **Expanded Selectors**: Add more search input patterns as discovered
2. **Site-Specific Optimizations**: Custom selectors for specific popular sites
3. **Caching**: Cache DOM search capability results per domain
4. **Metrics**: Track DOM-first success rates and performance gains