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

# Demo data showing what the raw extraction returns
DEMO_RAW_EXTRACTION = {
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

# Demo data showing what the LLM-structured result looks like
DEMO_STRUCTURED_RESULT = {
    "events": [
        {
            "date": "2024-01-15",
            "time": "09:00", 
            "title": "Team Meeting",
            "location": "Conference Room A",
            "attendees": "5",
            "description": None,
            "duration": None,
            "status": None
        },
        {
            "date": "2024-01-15",
            "time": "14:00",
            "title": "Client Call", 
            "location": "Virtual",
            "attendees": "3",
            "description": None,
            "duration": None,
            "status": None
        },
        {
            "date": "2024-01-16",
            "time": "10:00",
            "title": "Project Review",
            "location": "Conference Room B", 
            "attendees": "8",
            "description": None,
            "duration": None,
            "status": None
        },
        {
            "date": "2024-01-16", 
            "time": "15:30",
            "title": "Training Session",
            "location": "Training Room",
            "attendees": "12",
            "description": None,
            "duration": None,
            "status": None
        },
        {
            "date": "2024-01-17",
            "time": "11:00",
            "title": "Sprint Planning",
            "location": "Development Lab",
            "attendees": "6", 
            "description": None,
            "duration": None,
            "status": None
        }
    ],
    "total_count": 5,
    "date_range": "2024-01-15 to 2024-01-17",
    "extraction_source": "llm_structured_from_clipboard_copy"
}

def show_demo():
    """Show what the complete Tabular → Text → JSON pipeline produces."""
    print("="*60)
    print("🔧 COMPLETE TABULAR → TEXT → JSON PIPELINE DEMO")
    print("="*60)
    
    print(f"\n📊 STEP 1: RAW TABLE EXTRACTION")
    print(f"  Extraction Method: {DEMO_RAW_EXTRACTION['extraction_method']}")
    print(f"  Confidence Score: {DEMO_RAW_EXTRACTION['confidence']:.1%}")
    print(f"  Dimensions: {DEMO_RAW_EXTRACTION['row_count']} rows × {DEMO_RAW_EXTRACTION['column_count']} columns")
    
    print(f"\n📋 Headers: {DEMO_RAW_EXTRACTION['headers']}")
    
    print(f"\n📝 Raw Data (first 3 rows):")
    for i, row in enumerate(DEMO_RAW_EXTRACTION['rows'][:3]):
        print(f"  Row {i+1}: {row}")
    if len(DEMO_RAW_EXTRACTION['rows']) > 3:
        print(f"  ... and {len(DEMO_RAW_EXTRACTION['rows']) - 3} more rows")
    
    print(f"\n🧠 STEP 2: LLM STRUCTURING")
    print(f"  Target Schema: EventsSchema")
    print(f"  Total Events: {DEMO_STRUCTURED_RESULT['total_count']}")
    print(f"  Date Range: {DEMO_STRUCTURED_RESULT['date_range']}")
    print(f"  Source: {DEMO_STRUCTURED_RESULT['extraction_source']}")
    
    print(f"\n📅 Structured Events (first 3):")
    for i, event in enumerate(DEMO_STRUCTURED_RESULT['events'][:3]):
        print(f"  Event {i+1}:")
        print(f"    Date: {event['date']} | Time: {event['time']}")
        print(f"    Title: {event['title']}")
        print(f"    Location: {event['location']} | Attendees: {event['attendees']}")
    if len(DEMO_STRUCTURED_RESULT['events']) > 3:
        print(f"  ... and {len(DEMO_STRUCTURED_RESULT['events']) - 3} more events")
    
    print(f"\n🔄 Complete Pipeline:")
    print("  1. EXTRACT: File→Download CSV → Select All→Copy → HTML parsing")
    print("  2. STRUCTURE: LLM maps raw data to target schema")
    print("  3. RETURN: Clean structured JSON ready for use")
    
    print(f"\n💡 Integration with agent.py:")
    print("  • Registered as custom action 'fallback_extract_table'")
    print("  • LLM executor calls it when normal extraction fails")
    print("  • Works universally across any site/app")
    print("  • Returns data in requested schema format")
    
    print(f"\n🎯 Example Usage:")
    print("  Query: 'Extract all events from this Google Calendar'")
    print("  → Agent tries built-in extraction")
    print("  → If that fails, calls fallback_extract_table(target_schema='EventsSchema')")
    print("  → Returns structured EventsSchema JSON")
    
    print("\n" + "="*60)

def show_integration_info():
    """Show how the complete pipeline integrates with agent.py"""
    print("="*60)
    print("🔗 INTEGRATION WITH BROWSER-USE AGENT")
    print("="*60)
    
    print("\n📁 Files Modified:")
    print("  • agent.py - Added fallback extraction function")
    print("  • agent.py - Added LLM structuring function")
    print("  • agent.py - Added EventsSchema and related schemas")
    print("  • agent.py - Added custom action registration with LLM")
    print("  • agent.py - Updated system prompts for complete pipeline")
    
    print("\n🎛️  Custom Action Registration:")
    print("  @controller.action('fallback_extract_table')")
    print("  async def fallback_extract_table_action(")
    print("      want_fields=None, target_schema='EventsSchema', structure_with_llm=True):")
    print("    # 1. Extract raw table data")
    print("    # 2. Use LLM to structure according to target schema")
    print("    # 3. Return clean structured JSON")
    
    print("\n🧠 Complete LLM Integration:")
    print("  • Planner knows about the complete pipeline")
    print("  • System message explains Tabular → Text → JSON flow")
    print("  • LLM executor can specify target schemas")
    print("  • Automatic structuring with schema validation")
    
    print("\n🔄 Enhanced Execution Flow:")
    print("  1. User asks for table/schedule extraction")
    print("  2. Agent tries built-in Browser-Use extraction")
    print("  3. If that struggles, agent calls 'fallback_extract_table'")
    print("  4. EXTRACT: CSV download → clipboard → HTML parsing")
    print("  5. STRUCTURE: LLM maps raw data to target schema")
    print("  6. VALIDATE: Schema validation ensures clean output")
    print("  7. RETURN: Structured JSON ready for immediate use")
    
    print("\n✨ Key Improvements:")
    print("  • Complete end-to-end pipeline")
    print("  • Schema-aware structuring")
    print("  • Universal compatibility")
    print("  • Intelligent field mapping")
    print("  • Error handling and fallbacks")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    print("🤖 Browser-Use Complete Tabular → Text → JSON Pipeline Demo\n")
    
    show_demo()
    print("\n")
    show_integration_info()
    
    print(f"\n📖 To test the complete pipeline:")
    print(f"  1. Run: python agent.py")
    print(f"  2. Try queries like:")
    print(f"     • 'Extract events from this Google Calendar as structured JSON'")
    print(f"     • 'Get the schedule from this sheet and format as EventsSchema'")
    print(f"     • 'Copy all appointments from this table and structure them'")
    print(f"  3. Watch the console for:")
    print(f"     - Raw table extraction messages")  
    print(f"     - LLM structuring progress")
    print(f"     - Final structured JSON output")
    
    print(f"\n🎯 Example Custom Action Call:")
    print(f"   fallback_extract_table(")
    print(f"     want_fields=['date', 'time', 'event', 'location'],")
    print(f"     target_schema='EventsSchema'")
    print(f"   )")
    
    print(f"\n✅ The complete Tabular → Text → JSON pipeline is now fully integrated!")
    print(f"   It provides universal table extraction with intelligent LLM structuring.")
    print(f"   Works on any site/app: Google Sheets, calendars, HTML tables, and more!")