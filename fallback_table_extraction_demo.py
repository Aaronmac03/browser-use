"""
Fallback Table Extraction Demo

This demo shows how the generic fallback table extraction works with Browser-Use.
The fallback extraction is now integrated into agent.py as a custom action.

Usage:
1. Run the main agent.py script
2. When it encounters a table extraction task, it will automatically use the fallback if needed
3. Or you can trigger it explicitly by asking for table extraction tasks

Key Features:
- Works on any website/app with tabular data
- Tries multiple strategies: CSV download, clipboard copy, HTML parsing  
- Returns structured data that can be mapped to any schema
- Universal compatibility across Google Sheets, web apps, HTML tables

Example queries that will use the fallback extraction:
- "Extract the schedule from this Google Sheet"
- "Get all the data from this table and format it as JSON" 
- "Find the pricing information in this spreadsheet"
- "Copy all rows from this calendar/schedule view"
"""

import asyncio
from pathlib import Path

# Demo data showing what the fallback extraction returns
DEMO_EXTRACTION_RESULT = {
    "headers": ["Date", "Time", "Event", "Location", "Attendees"],
    "rows": [
        ["2024-01-15", "09:00", "Team Meeting", "Conference Room A", "5"],
        ["2024-01-15", "14:00", "Client Call", "Virtual", "3"],
        ["2024-01-16", "10:00", "Project Review", "Conference Room B", "8"],
        ["2024-01-16", "15:30", "Training Session", "Training Room", "12"],
        ["2024-01-17", "11:00", "Sprint Planning", "Development Lab", "6"],
    ],
    "row_count": 5,
    "column_count": 5,
    "extraction_method": "clipboard_copy",
    "confidence": 0.85
}

def show_demo():
    """Show what the fallback extraction produces."""
    print("="*60)
    print("🔧 FALLBACK TABLE EXTRACTION - DEMO OUTPUT")
    print("="*60)
    
    print(f"\n📊 Extraction Method: {DEMO_EXTRACTION_RESULT['extraction_method']}")
    print(f"🎯 Confidence Score: {DEMO_EXTRACTION_RESULT['confidence']:.1%}")
    print(f"📏 Dimensions: {DEMO_EXTRACTION_RESULT['row_count']} rows × {DEMO_EXTRACTION_RESULT['column_count']} columns")
    
    print(f"\n📋 Headers:")
    for i, header in enumerate(DEMO_EXTRACTION_RESULT['headers']):
        print(f"  {i+1}. {header}")
    
    print(f"\n📝 Sample Data (first 3 rows):")
    for i, row in enumerate(DEMO_EXTRACTION_RESULT['rows'][:3]):
        print(f"  Row {i+1}: {row}")
    
    if len(DEMO_EXTRACTION_RESULT['rows']) > 3:
        print(f"  ... and {len(DEMO_EXTRACTION_RESULT['rows']) - 3} more rows")
    
    print(f"\n🔄 How it works:")
    print("  1. Strategy 1: Attempts File → Download CSV (Google Sheets, etc.)")
    print("  2. Strategy 2: Select All → Copy → Parse clipboard TSV/CSV")
    print("  3. Strategy 3: HTML table parsing as last resort")
    print("  4. Returns structured data ready for any schema mapping")
    
    print(f"\n💡 Integration with agent.py:")
    print("  • Registered as custom action 'fallback_extract_table'")
    print("  • LLM can call it when normal extraction fails")
    print("  • Works universally across any site/app")
    print("  • Automatically triggered for table extraction tasks")
    
    print(f"\n🎯 Example Usage in Agent:")
    print("  Query: 'Extract all events from this Google Calendar view'")
    print("  → Agent tries built-in extraction")
    print("  → If that fails, calls fallback_extract_table")
    print("  → Returns structured JSON data")
    
    print("\n" + "="*60)

def show_integration_info():
    """Show how the integration works with agent.py"""
    print("="*60)
    print("🔗 INTEGRATION WITH BROWSER-USE AGENT")
    print("="*60)
    
    print("\n📁 Files Modified:")
    print("  • agent.py - Added fallback extraction function")
    print("  • agent.py - Added custom action registration")
    print("  • agent.py - Updated system prompts")
    
    print("\n🎛️  Custom Action Registration:")
    print("  @controller.action('fallback_extract_table')")
    print("  async def fallback_extract_table_action(want_fields=None):")
    print("    # Calls the main fallback function")
    print("    # Returns structured dict for LLM")
    
    print("\n🧠 LLM Integration:")
    print("  • Planner knows about the fallback action")
    print("  • System message tells executor how to use it")
    print("  • Automatically suggested for table extraction tasks")
    
    print("\n🔄 Execution Flow:")
    print("  1. User asks for table/schedule extraction")
    print("  2. Agent tries built-in Browser-Use extraction")
    print("  3. If that struggles, agent calls 'fallback_extract_table'")
    print("  4. Fallback tries CSV download → clipboard → HTML parsing")
    print("  5. Returns structured data to agent")
    print("  6. Agent maps data to requested format")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    print("🤖 Browser-Use Fallback Table Extraction Demo\n")
    
    show_demo()
    print("\n")
    show_integration_info()
    
    print(f"\n📖 To test the integration:")
    print(f"  1. Run: python agent.py")
    print(f"  2. Try queries like:")
    print(f"     • 'Extract data from this Google Sheet'")
    print(f"     • 'Get the schedule from this calendar view'")
    print(f"     • 'Copy all entries from this table'")
    print(f"  3. Watch the console for fallback extraction messages")
    
    print(f"\n✅ The fallback extraction is now fully integrated!")
    print(f"   It will automatically activate when table extraction is challenging.")