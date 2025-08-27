"""
query.py - Interactive Browser-Use Query Tool with Structured Outputs
Run with: python query.py

This script uses a true planner → executor → critic pipeline with STRUCTURED OUTPUTS:
- All LLM interactions return validated JSON schemas
- Planner/Critic (GPT-4o-mini by default) create structured plans and critiques
- Executor (Gemini 2.5 Flash by default) drives the browser with structured extraction
- Data is extracted as clean JSON objects instead of prose

Cost tracking uses browser-use's built-in usage accounting.
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
import json
import csv
import re
import subprocess
import platform
from io import StringIO
from typing import List, Optional, Any, Dict, Union

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

# Freshly load env (useful when switching providers)
for k in ("OPENAI_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY"):
    if k in os.environ:
        del os.environ[k]
load_dotenv(override=True)

from browser_use import Agent, BrowserProfile, BrowserSession, Controller
from browser_use.agent.views import AgentHistoryList
from browser_use.llm import ChatOpenAI, ChatGoogle, SystemMessage, UserMessage  # NOTE: imports from browser_use.llm

# Import Serper search integration
from serper_search import search_with_serper_fallback

# ----------------------------
# Structured Output Schemas
# ----------------------------
class PlanStep(BaseModel):
    """Single step in execution plan."""
    step_number: int = Field(description="Step number in sequence")
    action: str = Field(description="What action to take")
    expected_outcome: str = Field(description="What should happen after this step")
    fallback_strategy: Optional[str] = Field(description="What to do if this step fails", default=None)

class StructuredPlan(BaseModel):
    """Complete execution plan with structured steps."""
    task_summary: str = Field(description="Brief summary of the overall task")
    steps: List[PlanStep] = Field(description="Ordered list of execution steps")
    success_criteria: str = Field(description="How to know when the task is complete")
    estimated_duration_minutes: int = Field(description="Estimated time to complete in minutes")
    domains_required: List[str] = Field(description="List of websites/domains needed")
    
class CritiqueIssue(BaseModel):
    """Individual issue found in plan or execution."""
    issue_type: str = Field(description="Type of issue (risk, error, improvement, etc.)")
    description: str = Field(description="Detailed description of the issue")
    severity: str = Field(description="Severity level: low, medium, high, critical")
    recommendation: str = Field(description="Specific recommendation to fix the issue")

class StructuredCritique(BaseModel):
    """Structured critique of plan or execution."""
    overall_assessment: str = Field(description="Overall quality assessment: excellent, good, fair, poor")
    issues_found: List[CritiqueIssue] = Field(description="List of issues identified")
    strengths: List[str] = Field(description="Things that are done well")
    final_recommendation: str = Field(description="Final recommendation: approve, revise, reject")

# Replace the ExtractedData class in your script with this version:

from typing import Any, Dict, Union, List, Optional
from pydantic import BaseModel, Field

class ExtractedData(BaseModel):
    """Generic structured data extraction result."""
    data_type: str = Field(description="Type of data extracted (table, list, text, product, etc.)")
    # Changed from Dict[str, Any] to Any to avoid Gemini schema validation issues
    content: Any = Field(description="The actual extracted data in structured format (can be dict, list, string, etc.)")
    confidence: float = Field(description="Confidence score 0-1 for extraction quality")
    source_url: Optional[str] = Field(description="URL where data was extracted from", default=None)
    timestamp: str = Field(description="When the data was extracted", default_factory=lambda: datetime.now().isoformat())

# Alternative approach if you need more type safety:
# You can use a Union type to be explicit about what content can contain
class ExtractedDataAlternative(BaseModel):
    """Generic structured data extraction result with explicit type union."""
    data_type: str = Field(description="Type of data extracted (table, list, text, product, etc.)")
    # Explicitly define possible types for content
    content: Union[Dict[str, Union[str, int, float, bool, list, dict]], List[Any], str] = Field(
        description="The actual extracted data - can be a dictionary, list, or string"
    )
    confidence: float = Field(description="Confidence score 0-1 for extraction quality")
    source_url: Optional[str] = Field(description="URL where data was extracted from", default=None)
    timestamp: str = Field(description="When the data was extracted", default_factory=lambda: datetime.now().isoformat())
    
# Common schema for events/appointments (example target schema)
class EventEntry(BaseModel):
    """Single event/appointment entry."""
    date: str = Field(description="Event date in YYYY-MM-DD format")
    time: Optional[str] = Field(description="Event time (e.g. '09:00', '14:30')", default=None)
    title: str = Field(description="Event title/name")
    description: Optional[str] = Field(description="Event description or notes", default=None)
    location: Optional[str] = Field(description="Event location", default=None)
    attendees: Optional[str] = Field(description="Number of attendees or attendee list", default=None)
    duration: Optional[str] = Field(description="Event duration", default=None)
    status: Optional[str] = Field(description="Event status (confirmed, tentative, etc.)", default=None)

class EventsSchema(BaseModel):
    """Collection of events extracted from a table/schedule."""
    events: List[EventEntry] = Field(description="List of events/appointments")
    total_count: int = Field(description="Total number of events found")
    date_range: Optional[str] = Field(description="Date range covered (e.g. '2024-01-15 to 2024-01-20')", default=None)
    extraction_source: str = Field(description="How the data was extracted")

class ExecutionEvent(BaseModel):
    """Single event in execution history."""
    step_number: int = Field(description="Which step this event belongs to")
    action_taken: str = Field(description="Action that was performed")
    result: str = Field(description="Result of the action")
    success: bool = Field(description="Whether the action succeeded")
    extracted_data: Optional[ExtractedData] = Field(description="Any data extracted during this event", default=None)
    error_message: Optional[str] = Field(description="Error message if action failed", default=None)

class StructuredExecutionResult(BaseModel):
    """Complete structured result of task execution."""
    task_completed: bool = Field(description="Whether the overall task was completed successfully")
    summary: str = Field(description="Brief summary of what was accomplished")
    events: List[ExecutionEvent] = Field(description="Chronological list of execution events")
    final_data: Optional[ExtractedData] = Field(description="Final extracted data if applicable", default=None)
    total_steps: int = Field(description="Total number of steps taken")
    success_rate: float = Field(description="Percentage of successful steps")
    
# ----------------------------
# Fallback Table Extraction Schema
# ----------------------------
class TableData(BaseModel):
    """Structured representation of extracted table data."""
    headers: List[str] = Field(description="Column headers from the table")
    rows: List[List[str]] = Field(description="Data rows as lists of strings")
    row_count: int = Field(description="Number of data rows")
    column_count: int = Field(description="Number of columns")
    extraction_method: str = Field(description="How the data was extracted (csv_download, clipboard_copy, html_parse)")
    confidence: float = Field(description="Confidence in extraction quality (0-1)")

# ----------------------------
# Configuration
# ----------------------------
CHROME_PROFILE_DIR = 'C:/Users/drmcn/.config/browseruse/profiles/default'
LOGS_DIR = Path('browser_queries')
LOGS_DIR.mkdir(exist_ok=True)

# Force specific models (ignore env vars to avoid invalid model issues)
PLANNER_MODEL  = "openai/gpt-oss-120b"  # OpenRouter - GPT OSS 120B
EXECUTOR_MODEL = "gemini-2.5-flash"      # Google - forced default

# ----------------------------
# Terminal colors
# ----------------------------
class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header():
    print(f"\n{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}🤖 Browser-Use Query Tool with Structured Outputs{Colors.END}")
    print(f"{Colors.GREEN}📊 Enforces JSON schemas for plans, critiques & data extraction{Colors.END}")
    print(f"{Colors.BOLD}{'='*70}{Colors.END}\n")

def print_status(message, color=Colors.BLUE):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{ts}] {message}{Colors.END}")

# ----------------------------
# Logging helpers
# ----------------------------
def save_query_log(query, result, cost_info=None):
    timestamp = datetime.now()
    date_str = timestamp.strftime("%Y-%m-%d")
    time_str = timestamp.strftime("%H-%M-%S")

    daily_dir = LOGS_DIR / date_str
    daily_dir.mkdir(exist_ok=True)

    log_file = daily_dir / f"{time_str}_query.md"
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(f"# Browser Query Log\n")
        f.write(f"**Date:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## Query\n```\n{query}\n```\n\n")
        f.write(f"## Result\n{result}\n\n")
        if cost_info:
            f.write("## Cost Information\n")
            f.write(f"- Planner/Critic Model: {cost_info.get('planner_model', 'N/A')}\n")
            f.write(f"- Executor Model: {cost_info.get('executor_model', 'N/A')}\n")
            f.write(f"- Prompt tokens: {cost_info.get('prompt_tokens', 'N/A')}\n")
            f.write(f"- Completion tokens: {cost_info.get('completion_tokens', 'N/A')}\n")
            f.write(f"- Total tokens: {cost_info.get('total_tokens', 'N/A')}\n")
            f.write(f"- Estimated cost: ${cost_info.get('estimated_cost', 0):.4f}\n")

    summary_file = daily_dir / "daily_summary.json"
    summary_entry = {
        "time": time_str,
        "query": query[:100] + "..." if len(query) > 100 else query,
        "log_file": str(log_file.name),
        "cost": cost_info.get('estimated_cost', 0) if cost_info else 0,
    }

    if summary_file.exists():
        with open(summary_file, 'r', encoding='utf-8') as f:
            summary = json.load(f)
    else:
        summary = {"queries": [], "total_cost": 0}

    summary["queries"].append(summary_entry)
    summary["total_cost"] += summary_entry["cost"]

    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    return log_file

# ----------------------------
# Fallback Table Extraction Implementation
# ----------------------------

async def fallback_extract_table(controller, want_fields: List[str] = None) -> TableData:
    """
    Generic fallback table extraction that works on any schedule/table.
    Tries multiple strategies:
    1. File → Download as CSV (for Google Sheets, etc.)
    2. Select All → Copy to get TSV from clipboard
    3. HTML table parsing as last resort
    
    Args:
        controller: Browser-use controller instance
        want_fields: Optional list of field names we're looking for
    
    Returns:
        TableData: Structured table data with headers and rows
    """
    print_status("🔄 Attempting fallback table extraction...", Colors.YELLOW)
    
    extraction_method = "unknown"
    headers = []
    rows = []
    confidence = 0.5
    
    try:
        # Strategy 1: Try to download as CSV (works for Google Sheets, some web apps)
        print_status("  📥 Strategy 1: Attempting CSV download...", Colors.BLUE)
        
        # Look for File menu or download options
        try:
            # Try common download patterns
            download_selectors = [
                "//button[contains(text(), 'Download')]",
                "//a[contains(text(), 'Download')]",
                "//button[contains(text(), 'Export')]",
                "//a[contains(text(), 'Export')]",
                "//div[contains(text(), 'File')]/..//button",
                "[aria-label*='File']",
                "[data-testid*='download']",
                "[data-testid*='export']"
            ]
            
            download_clicked = False
            for selector in download_selectors:
                try:
                    element = await controller.page.locator(selector).first
                    if await element.is_visible():
                        await element.click()
                        download_clicked = True
                        print_status("  ✅ Found download option", Colors.GREEN)
                        
                        # Wait a bit and look for CSV option
                        await controller.page.wait_for_timeout(1000)
                        
                        # Look for CSV in dropdown or popup
                        csv_selectors = [
                            "//button[contains(text(), 'CSV')]",
                            "//a[contains(text(), 'CSV')]",
                            "//div[contains(text(), 'CSV')]",
                            "//li[contains(text(), 'CSV')]"
                        ]
                        
                        for csv_sel in csv_selectors:
                            try:
                                csv_element = await controller.page.locator(csv_sel).first
                                if await csv_element.is_visible():
                                    await csv_element.click()
                                    print_status("  ✅ CSV download initiated", Colors.GREEN)
                                    
                                    # Wait for download and try to read it
                                    await controller.page.wait_for_timeout(3000)
                                    # TODO: In a real implementation, you'd handle the download
                                    # For now, we'll fall back to other methods
                                    break
                            except:
                                continue
                        break
                except:
                    continue
                    
            if not download_clicked:
                print_status("  ⚠️  No download option found", Colors.YELLOW)
                
        except Exception as e:
            print_status(f"  ⚠️  CSV download failed: {e}", Colors.YELLOW)
        
        # Strategy 2: Select All + Copy (most reliable fallback)
        print_status("  📋 Strategy 2: Attempting select all + copy...", Colors.BLUE)
        
        try:
            # Focus on the page body first
            await controller.page.locator("body").click()
            
            # Select all content
            select_all_key = "Ctrl+A" if platform.system() != "Darwin" else "Cmd+A"
            await controller.page.keyboard.press(select_all_key)
            await controller.page.wait_for_timeout(500)
            
            # Copy to clipboard
            copy_key = "Ctrl+C" if platform.system() != "Darwin" else "Cmd+C"
            await controller.page.keyboard.press(copy_key)
            await controller.page.wait_for_timeout(1000)
            
            # Get clipboard content
            try:
                if platform.system() == "Windows":
                    result = subprocess.run(["powershell", "-command", "Get-Clipboard"], capture_output=True, text=True)
                    clipboard_content = result.stdout
                elif platform.system() == "Darwin":  # macOS
                    result = subprocess.run(["pbpaste"], capture_output=True, text=True)
                    clipboard_content = result.stdout
                else:  # Linux
                    result = subprocess.run(["xclip", "-selection", "clipboard", "-o"], capture_output=True, text=True)
                    clipboard_content = result.stdout
                
                if clipboard_content and len(clipboard_content.strip()) > 10:
                    print_status("  ✅ Clipboard content retrieved", Colors.GREEN)
                    
                    # Parse the clipboard content as TSV/CSV
                    lines = clipboard_content.strip().split('\n')
                    if len(lines) >= 2:  # At least header + one data row
                        
                        # Try to detect delimiter (tab or comma)
                        first_line = lines[0]
                        delimiter = '\t' if '\t' in first_line else ','
                        
                        # Parse with CSV reader
                        csv_reader = csv.reader(lines, delimiter=delimiter)
                        parsed_rows = list(csv_reader)
                        
                        if parsed_rows and len(parsed_rows) >= 2:
                            headers = [h.strip() for h in parsed_rows[0]]
                            rows = [row for row in parsed_rows[1:] if any(cell.strip() for cell in row)]  # Skip empty rows
                            
                            extraction_method = "clipboard_copy"
                            confidence = 0.8
                            
                            print_status(f"  ✅ Parsed {len(rows)} rows with {len(headers)} columns", Colors.GREEN)
                            
                        else:
                            print_status("  ⚠️  Could not parse clipboard content as table", Colors.YELLOW)
                else:
                    print_status("  ⚠️  Clipboard content too short or empty", Colors.YELLOW)
                    
            except Exception as e:
                print_status(f"  ⚠️  Clipboard access failed: {e}", Colors.YELLOW)
                
        except Exception as e:
            print_status(f"  ⚠️  Select all + copy failed: {e}", Colors.YELLOW)
        
        # Strategy 3: HTML table parsing (last resort)
        if not rows:
            print_status("  🔍 Strategy 3: Attempting HTML table parsing...", Colors.BLUE)
            
            try:
                # Look for HTML tables
                tables = await controller.page.locator("table").all()
                if tables:
                    print_status(f"  Found {len(tables)} HTML table(s)", Colors.GREEN)
                    
                    # Use the largest table
                    largest_table = None
                    max_rows = 0
                    
                    for table in tables:
                        try:
                            table_rows = await table.locator("tr").all()
                            if len(table_rows) > max_rows:
                                max_rows = len(table_rows)
                                largest_table = table
                        except:
                            continue
                    
                    if largest_table:
                        table_rows = await largest_table.locator("tr").all()
                        
                        # Extract headers (first row or th elements)
                        if table_rows:
                            header_row = table_rows[0]
                            header_cells = await header_row.locator("th, td").all()
                            headers = []
                            for cell in header_cells:
                                text = await cell.inner_text()
                                headers.append(text.strip())
                            
                            # Extract data rows
                            for row in table_rows[1:]:
                                data_cells = await row.locator("td").all()
                                if data_cells:
                                    row_data = []
                                    for cell in data_cells:
                                        text = await cell.inner_text()
                                        row_data.append(text.strip())
                                    if any(cell for cell in row_data):  # Skip empty rows
                                        rows.append(row_data)
                            
                            extraction_method = "html_parse"
                            confidence = 0.6  # Lower confidence for HTML parsing
                            
                            print_status(f"  ✅ Parsed HTML table: {len(rows)} rows, {len(headers)} columns", Colors.GREEN)
                else:
                    print_status("  ⚠️  No HTML tables found", Colors.YELLOW)
                    
            except Exception as e:
                print_status(f"  ⚠️  HTML table parsing failed: {e}", Colors.YELLOW)
        
        # Final validation and cleanup
        if headers and rows:
            # Ensure all rows have the same number of columns as headers
            target_cols = len(headers)
            normalized_rows = []
            
            for row in rows:
                # Pad or trim to match header count
                if len(row) < target_cols:
                    row.extend([''] * (target_cols - len(row)))
                elif len(row) > target_cols:
                    row = row[:target_cols]
                normalized_rows.append(row)
            
            rows = normalized_rows
            
            # Filter based on want_fields if provided
            if want_fields:
                wanted_indices = []
                for field in want_fields:
                    for i, header in enumerate(headers):
                        if field.lower() in header.lower():
                            wanted_indices.append(i)
                            break
                
                if wanted_indices:
                    # Filter headers and rows to only wanted columns
                    filtered_headers = [headers[i] for i in wanted_indices]
                    filtered_rows = [[row[i] for i in wanted_indices] for row in rows]
                    headers = filtered_headers
                    rows = filtered_rows
                    confidence += 0.1  # Boost confidence when we found requested fields
            
            print_status(f"✅ Fallback extraction successful: {len(rows)} rows, {len(headers)} columns", Colors.GREEN)
            
        else:
            print_status("❌ All extraction strategies failed", Colors.RED)
            extraction_method = "failed"
            confidence = 0.0
    
    except Exception as e:
        print_status(f"❌ Fallback extraction error: {e}", Colors.RED)
        extraction_method = "error"
        confidence = 0.0
    
    return TableData(
        headers=headers,
        rows=rows,
        row_count=len(rows),
        column_count=len(headers),
        extraction_method=extraction_method,
        confidence=confidence
    )

async def llm_structure_table_data(llm, table_data: TableData, target_schema_name: str = "EventsSchema", target_schema=None) -> Dict[str, Any]:
    """
    Use LLM to structure raw table data according to a target schema.
    This completes the "Tabular → Text → JSON" pipeline.
    
    Args:
        llm: LLM instance to use for structuring
        table_data: Raw table data from fallback extraction
        target_schema_name: Name of the target schema (for prompt)
        target_schema: Pydantic model class for the target schema
        
    Returns:
        dict: Structured data matching the target schema
    """
    if not table_data.rows:
        return {"error": "No table data to structure", "events": [], "total_count": 0}
    
    # Create text representation of the table
    table_text = f"HEADERS: {', '.join(table_data.headers)}\n\nROWS:\n"
    for i, row in enumerate(table_data.rows, 1):
        table_text += f"Row {i}: {' | '.join(str(cell) for cell in row)}\n"
    
    # Use default EventsSchema if no target schema provided
    if target_schema is None:
        target_schema = EventsSchema
        target_schema_name = "EventsSchema"
    
    structure_prompt = f"""
You are a data structuring specialist. Convert the raw table data below into a structured JSON format following the {target_schema_name} schema.

RAW TABLE DATA:
{table_text}

EXTRACTION METHOD: {table_data.extraction_method}
CONFIDENCE: {table_data.confidence}

INSTRUCTIONS:
1. Analyze the table structure and identify what each column represents
2. Map the data to the appropriate schema fields
3. Handle missing or unclear data gracefully (use null/empty values)
4. Parse dates into YYYY-MM-DD format when possible
5. Extract times in HH:MM format when possible
6. Infer event titles, locations, descriptions from available columns
7. Count the total number of events
8. Determine the date range if dates are present

OUTPUT: Return ONLY valid JSON matching the {target_schema_name} schema. No additional text or comments.
"""

    try:
        print_status(f"🧠 Using LLM to structure table data into {target_schema_name}...", Colors.BLUE)
        
        # Get structured response from LLM
        messages = [
            SystemMessage(content=structure_prompt.strip()),
            UserMessage(content="Please structure this table data now.")
        ]
        
        # Request structured output if the LLM supports it
        if hasattr(llm, 'generate_structured'):
            # For LLMs that support structured output
            structured_response = await llm.generate_structured(
                messages=messages,
                output_model=target_schema
            )
            result = structured_response.model_dump()
        else:
            # Fallback to regular generation + JSON parsing
            response = await llm.generate(messages=messages)
            response_text = response.choices[0].message.content.strip()
            
            # Try to extract JSON from the response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
            else:
                # If no JSON found, try parsing the whole response
                result = json.loads(response_text)
        
        # Validate against schema if provided
        if target_schema:
            validated = target_schema(**result)
            result = validated.model_dump()
        
        result["extraction_source"] = f"llm_structured_from_{table_data.extraction_method}"
        print_status(f"✅ Successfully structured {result.get('total_count', 0)} items", Colors.GREEN)
        
        return result
        
    except json.JSONDecodeError as e:
        print_status(f"❌ JSON parsing error: {e}", Colors.RED)
        return {
            "error": f"Failed to parse LLM response as JSON: {e}",
            "events": [],
            "total_count": 0,
            "extraction_source": f"error_from_{table_data.extraction_method}"
        }
    except Exception as e:
        print_status(f"❌ LLM structuring error: {e}", Colors.RED)
        return {
            "error": f"Failed to structure data with LLM: {e}",
            "events": [],
            "total_count": 0,
            "extraction_source": f"error_from_{table_data.extraction_method}"
        }

# ----------------------------
# Custom Action Registration for Browser-Use
# ----------------------------
async def register_fallback_extraction_action(controller, llm=None):
    """Register the fallback table extraction as a custom action."""
    
    @controller.action("fallback_extract_table")
    async def fallback_extract_table_action(want_fields: List[str] = None, target_schema: str = "EventsSchema", structure_with_llm: bool = True) -> dict:
        """
        Generic fallback table extraction that works on any schedule/table.
        Completes the "Tabular → Text → JSON" pipeline.
        
        Tries multiple strategies:
        1. File → Download as CSV (for Google Sheets, etc.)
        2. Select All → Copy to get TSV from clipboard  
        3. HTML table parsing as last resort
        4. Use LLM to structure the data according to target schema
        
        Args:
            want_fields: Optional list of field names to filter for
            target_schema: Target schema name ("EventsSchema" by default)
            structure_with_llm: Whether to use LLM for structuring (default True)
            
        Returns:
            dict: Structured data matching target schema, or raw table data if structuring disabled
        """
        print_status("🔄 Starting fallback table extraction with LLM structuring...", Colors.BLUE)
        
        # Step 1: Extract raw table data
        table_data = await fallback_extract_table(controller, want_fields)
        
        if not table_data.rows:
            return {
                "error": "No table data could be extracted",
                "events": [],
                "total_count": 0,
                "extraction_method": table_data.extraction_method
            }
        
        # Step 2: Structure with LLM if requested and available
        if structure_with_llm and llm:
            print_status("🧠 Structuring table data with LLM...", Colors.BLUE)
            
            # Map target schema name to actual schema class
            schema_mapping = {
                "EventsSchema": EventsSchema,
                "events": EventsSchema,
                "schedule": EventsSchema,
                "calendar": EventsSchema
            }
            
            target_schema_class = schema_mapping.get(target_schema.lower(), EventsSchema)
            structured_result = await llm_structure_table_data(
                llm=llm,
                table_data=table_data,
                target_schema_name=target_schema,
                target_schema=target_schema_class
            )
            
            return structured_result
        
        else:
            # Return raw table data if LLM structuring not available/requested
            print_status("📋 Returning raw table data (no LLM structuring)", Colors.YELLOW)
            return {
                "headers": table_data.headers,
                "rows": table_data.rows,
                "row_count": table_data.row_count,
                "column_count": table_data.column_count,
                "extraction_method": table_data.extraction_method,
                "confidence": table_data.confidence
            }
    
    print_status("✅ Registered custom action: fallback_extract_table (with LLM structuring)", Colors.GREEN)

async def register_serper_search_action(controller):
    """Register the Serper API search as a custom action with browser fallback."""
    
    @controller.action("search_web")
    async def search_web_action(query: str, num_results: int = 10) -> str:
        """
        Search the web using Serper API with browser fallback.
        Much cheaper and more reliable than browser searches.
        
        Args:
            query: Search query string
            num_results: Number of results to return (default 10, max 100)
            
        Returns:
            str: Formatted search results with titles, URLs, and snippets
        """
        print_status(f"🔍 Searching web: {query}", Colors.BLUE)
        
        result = await search_with_serper_fallback(controller, query, num_results)
        return result.extracted_content
    
    print_status("✅ Registered custom action: search_web (Serper API with browser fallback)", Colors.GREEN)

# ----------------------------
# Planner / Critic prompts (GENERAL — not task-specific)
# ----------------------------
PLANNER_SYS = """You are a high-reliability web plan generator for a browser automation agent (Browser-Use v0.6+).

Output: a concise, numbered, end-to-end plan that a non-deterministic agent can follow.

General best practices:
- Prefer first-party, in-app viewers (e.g., Google Drive/Docs/Sheets/Calendar) over downloading files.
- Avoid third-party file converters unless explicitly requested.
- Keep actions inside the smallest number of trusted domains needed to finish the task.
- Bring the correct tab to the foreground before interacting; avoid acting on background tabs.
- Use clear recovery strategies for common failures (missing element, wrong page, 2FA, rate-limit).
- Never perform actions outside the user’s stated intent. If a step is ambiguous, proceed with the safest common-sense assumption and continue.

You MUST output valid JSON following the StructuredPlan schema. No additional text or commentary.

Create a structured plan for the task: "{task}"

**AVAILABLE CUSTOM ACTIONS**:

1. 'search_web' - Fast & cheap web search via Serper API with browser fallback:
   - Much cheaper than browser searches ($2 per 1000 vs $0.25 per search)
   - Faster and more reliable than navigating to Google
   - Automatically falls back to browser search if API fails
   - Returns formatted results with titles, URLs, snippets
   - Usage: search_web(query='your search terms', num_results=10)
   - Use this instead of navigating to Google for research tasks

2. 'fallback_extract_table' - Complete Tabular → Text → JSON pipeline:
   - Extract: File→Download CSV (Google Sheets) → Select All→Copy clipboard → HTML table parsing
   - Structure: Uses LLM to map raw data to target schema (EventsSchema for schedules/calendars)
   - Return: Clean structured JSON matching requested schema
   - Usage: fallback_extract_table(want_fields=['date', 'time', 'event'], target_schema='EventsSchema')
   - Works universally on any table/schedule across any site/app when normal table parsing struggles """

CRITIC_SYS = """You are a strict QA checker for web-automation plans and outcomes.

You MUST output valid JSON following the StructuredCritique schema. No additional text.

Evaluate for:
- Unnecessary downloads or third-party converters
- Wrong tab focus or domain drift  
- Ambiguous steps or missing completion criteria
- Security risks or data exposure
- Efficiency and reliability issues
- Missing error handling
- Incorrect format assumptions

For each issue: categorize type, assess severity (low/medium/high/critical), provide specific recommendations.
If no issues found: set overall_assessment to "excellent" and issues_found to empty list."""

# ----------------------------
# Enhanced LLM helpers with structured output support
# ----------------------------
async def chat_once(llm, user_prompt: str, system_prompt: str | None = None) -> str:
    """Basic LLM call returning raw text response."""
    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(UserMessage(content=user_prompt))
    resp = await llm.ainvoke(messages)
    return resp.completion

async def structured_chat(llm, user_prompt: str, system_prompt: str, response_model: type[BaseModel]) -> BaseModel:
    """LLM call that enforces structured JSON response and validates against schema."""
    full_system_prompt = f"""{system_prompt}

CRITICAL: You MUST respond with ONLY valid JSON that matches this exact schema:
{response_model.model_json_schema()}

No additional text, explanations, or formatting. Just the JSON object."""
    
    messages = [
        SystemMessage(content=full_system_prompt),
        UserMessage(content=user_prompt)
    ]
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = await llm.ainvoke(messages)
            response_text = resp.completion.strip()
            
            # Try to extract JSON from response if wrapped in code blocks
            if response_text.startswith('```'):
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)
            
            # Parse and validate the JSON response
            parsed_response = response_model.model_validate_json(response_text)
            return parsed_response
            
        except (ValidationError, json.JSONDecodeError) as e:
            if attempt == max_retries - 1:
                print_status(f"❌ Failed to get valid structured response after {max_retries} attempts", Colors.RED)
                print_status(f"Last response: {resp.completion[:200]}...", Colors.YELLOW)
                raise ValueError(f"Could not get valid {response_model.__name__} after {max_retries} attempts: {e}")
            
            print_status(f"⚠️  Invalid JSON response (attempt {attempt + 1}/{max_retries}), retrying...", Colors.YELLOW)
            # Add more specific instruction for retry
            messages.append(UserMessage(content=f"The previous response was invalid JSON. Please provide ONLY valid JSON matching the {response_model.__name__} schema."))
    
    raise ValueError("Unexpected error in structured_chat")

def process_agent_history_to_structured_result(history: AgentHistoryList, task: str) -> StructuredExecutionResult:
    """Convert agent execution history into structured result format."""
    events = []
    total_steps = len(history.history)
    successful_steps = 0
    final_data = None
    
    for i, step in enumerate(history.history):
        if hasattr(step, 'result') and step.result:
            for action_result in step.result:
                # Ensure success is always a boolean - fix for Pydantic validation
                action_success = getattr(action_result, 'success', True)
                action_error = getattr(action_result, 'error', None)
                success = bool(action_success) and not bool(action_error)
                if success:
                    successful_steps += 1
                
                # Extract any data that was found
                extracted_data = None
                if hasattr(action_result, 'extracted_content') and action_result.extracted_content:
                    try:
                        # Try to structure the extracted content
                        if isinstance(action_result.extracted_content, str):
                            # Simple text extraction
                            extracted_data = ExtractedData(
                                data_type="text",
                                content={"text": action_result.extracted_content},
                                confidence=0.8,
                                source_url=getattr(action_result, 'url', None)
                            )
                        elif isinstance(action_result.extracted_content, (dict, list)):
                            # Already structured data
                            extracted_data = ExtractedData(
                                data_type="structured",
                                content=action_result.extracted_content,
                                confidence=0.9,
                                source_url=getattr(action_result, 'url', None)
                            )
                        
                        # Keep the most recent extraction as final data
                        if extracted_data:
                            final_data = extracted_data
                            
                    except Exception as e:
                        print_status(f"Warning: Could not structure extracted content: {e}", Colors.YELLOW)
                
                event = ExecutionEvent(
                    step_number=i + 1,
                    action_taken=str(action_result.__class__.__name__ if hasattr(action_result, '__class__') else "unknown_action"),
                    result=str(action_result.extracted_content if hasattr(action_result, 'extracted_content') else "completed"),
                    success=success,
                    extracted_data=extracted_data,
                    error_message=getattr(action_result, 'error', None)
                )
                events.append(event)
    
    # Determine if task was completed successfully
    final_result = history.final_result()
    task_completed = bool(final_result) and successful_steps > 0
    
    success_rate = (successful_steps / max(total_steps, 1)) * 100
    
    return StructuredExecutionResult(
        task_completed=task_completed,
        summary=final_result or f"Executed {total_steps} steps with {successful_steps} successful actions",
        events=events,
        final_data=final_data,
        total_steps=total_steps,
        success_rate=success_rate
    )

# ----------------------------
# Progress Assessment Schema
# ----------------------------
class ProgressAssessment(BaseModel):
    """Assessment of current progress toward goal."""
    progress_percentage: int = Field(description="Estimated progress toward completion (0-100)")
    current_status: str = Field(description="Brief description of current state")
    obstacles_encountered: List[str] = Field(description="List of current obstacles or issues")
    next_milestone: str = Field(description="What should be achieved in the next chunk")
    needs_replanning: bool = Field(description="Whether the plan needs to be revised")
    should_continue: bool = Field(description="Whether to continue with current approach")
    fallback_needed: str = Field(description="Type of fallback if needed: none, table_extraction, simple_search, manual_intervention")

# ----------------------------
# Milestone-based execution helper
# ----------------------------
async def execute_milestone_chunk(agent: Agent, chunk_steps: int = 4) -> AgentHistoryList:
    """Execute a small chunk of steps and return history."""
    # Set max_steps for this chunk
    agent.max_steps = chunk_steps
    return await agent.run()

async def gather_milestone_state(controller, chunk_history: AgentHistoryList) -> str:
    """Gather current browser state for milestone critique."""
    state_info = []
    
    try:
        if controller and hasattr(controller, 'page'):
            # Current URL
            current_url = controller.page.url
            state_info.append(f"Current URL: {current_url}")
            
            # Page title
            try:
                title = await controller.page.title()
                state_info.append(f"Page Title: {title}")
            except:
                pass
                
            # Brief DOM excerpt (first 300 chars of visible text)
            try:
                visible_text = await controller.page.locator('body').inner_text()
                if visible_text:
                    excerpt = visible_text[:300] + "..." if len(visible_text) > 300 else visible_text
                    state_info.append(f"Page Content: {excerpt}")
            except:
                pass
                
            # Check for common error indicators
            try:
                error_indicators = await controller.page.locator('text="Error" >> visible=true').count()
                if error_indicators > 0:
                    state_info.append(f"Error elements detected: {error_indicators}")
            except:
                pass
                
    except Exception as e:
        state_info.append(f"State gathering error: {str(e)}")
    
    # Add execution summary
    if chunk_history and hasattr(chunk_history, 'history'):
        action_count = len(chunk_history.history)
        state_info.append(f"Actions in this milestone: {action_count}")
        
        # Last action result
        if chunk_history.history:
            last_step = chunk_history.history[-1]
            if hasattr(last_step, 'result') and last_step.result:
                last_action = str(last_step.result[-1].__class__.__name__ if last_step.result else "Unknown")
                state_info.append(f"Last action: {last_action}")
    
    return '\n'.join(state_info) if state_info else "No state information available"

def summarize_chunk_history(chunk_history: AgentHistoryList) -> str:
    """Create a brief summary of what happened in this milestone chunk."""
    if not chunk_history or not hasattr(chunk_history, 'history'):
        return "No execution history available"
    
    summary_parts = []
    success_count = 0
    error_count = 0
    
    for step in chunk_history.history:
        if hasattr(step, 'result') and step.result:
            for action in step.result:
                action_name = action.__class__.__name__ if hasattr(action, '__class__') else 'UnknownAction'
                
                # Check if action succeeded
                if hasattr(action, 'error') and action.error:
                    summary_parts.append(f"❌ {action_name}: {str(action.error)[:100]}")
                    error_count += 1
                else:
                    summary_parts.append(f"✅ {action_name}")
                    success_count += 1
                
                # Add extracted content if available
                if hasattr(action, 'extracted_content') and action.extracted_content:
                    content_preview = str(action.extracted_content)[:100]
                    summary_parts.append(f"   📄 Extracted: {content_preview}")
    
    # Add stats
    total_actions = success_count + error_count
    success_rate = (success_count / total_actions * 100) if total_actions > 0 else 0
    
    summary = f"Milestone Summary: {total_actions} actions ({success_rate:.0f}% success)\n"
    summary += '\n'.join(summary_parts[-10:])  # Last 10 actions
    
    return summary

async def assess_progress(planner_llm, original_query: str, current_plan: str, history: AgentHistoryList) -> ProgressAssessment:
    """Use planner/critic to assess current progress and decide next steps."""
    # Build progress context from history
    recent_actions = []
    if history and hasattr(history, 'history'):
        for step in history.history[-5:]:  # Last 5 steps
            if hasattr(step, 'result') and step.result:
                for action in step.result:
                    action_desc = f"Action: {action.__class__.__name__ if hasattr(action, '__class__') else 'unknown'}"
                    if hasattr(action, 'extracted_content'):
                        action_desc += f" | Result: {str(action.extracted_content)[:100]}"
                    if hasattr(action, 'error') and action.error:
                        action_desc += f" | Error: {action.error}"
                    recent_actions.append(action_desc)
    
    progress_prompt = f"""Original Task: {original_query}

Current Plan:
{current_plan}

Recent Actions Taken:
{chr(10).join(recent_actions) if recent_actions else "No actions taken yet"}

Assess the current progress toward completing the original task."""
    
    progress_system = """You are a progress assessor for web automation tasks. Analyze the current state and provide structured guidance.

Consider:
- Are we making meaningful progress toward the goal?
- Are we stuck or encountering repeated failures?
- Should we continue with current approach or replan?
- Do we need a different strategy (table extraction, simpler search, etc.)?

You MUST output valid JSON following the ProgressAssessment schema."""
    
    return await structured_chat(
        planner_llm,
        user_prompt=progress_prompt,
        system_prompt=progress_system,
        response_model=ProgressAssessment
    )

# ----------------------------
# Enhanced Core runner with frequent planner/critic involvement
# ----------------------------
async def run_query(query: str, keep_browser_open: bool = True) -> bool:
    print_status("Initializing milestone-based planner/critic system...", Colors.YELLOW)

    # Browser session
    browser_profile = BrowserProfile(
        user_data_dir=CHROME_PROFILE_DIR,
        keep_alive=keep_browser_open,
        headless=False
    )
    browser_session = BrowserSession(browser_profile=browser_profile)

    # LLMs
    planner_llm = ChatOpenAI(
        model=PLANNER_MODEL, 
        base_url='https://openrouter.ai/api/v1',
        api_key=os.getenv('OPENROUTER_API_KEY')
    )
    executor_llm = ChatGoogle(model=EXECUTOR_MODEL, api_key=os.getenv('GOOGLE_API_KEY'))

    print_status(f"Planner/Critic: {PLANNER_MODEL} (frequent re-assessment)", Colors.BLUE)
    print_status(f"Executor: {EXECUTOR_MODEL} (milestone chunks)", Colors.BLUE)

    # ---- Generate Initial Structured Plan
    print_status("Generating initial structured plan...", Colors.YELLOW)
    try:
        structured_plan = await structured_chat(
            planner_llm, 
            user_prompt=f"Task: {query}", 
            system_prompt=PLANNER_SYS.format(task=query),
            response_model=StructuredPlan
        )
        print_status(f"✅ Plan generated: {len(structured_plan.steps)} steps, {structured_plan.estimated_duration_minutes}min estimated", Colors.GREEN)
        
        # Convert structured plan back to text for the executor
        plan_text = f"Task: {structured_plan.task_summary}\n\n"
        plan_text += f"Success Criteria: {structured_plan.success_criteria}\n\n"
        plan_text += "Steps:\n"
        for step in structured_plan.steps:
            plan_text += f"{step.step_number}. {step.action}\n"
            plan_text += f"   Expected: {step.expected_outcome}\n"
            if step.fallback_strategy:
                plan_text += f"   Fallback: {step.fallback_strategy}\n"
            plan_text += "\n"
        
        current_plan = plan_text
        
    except Exception as e:
        print_status(f"⚠️  Structured planning failed, falling back to basic planning: {e}", Colors.YELLOW)
        current_plan = await chat_once(planner_llm, user_prompt=query, system_prompt=PLANNER_SYS.format(task=query))
        structured_plan = None

    # ---- Generate Initial Structured Critique
    print_status("Generating initial structured critique...", Colors.YELLOW)
    try:
        structured_critique = await structured_chat(
            planner_llm,
            user_prompt=f"Plan to evaluate:\n{current_plan}",
            system_prompt=CRITIC_SYS,
            response_model=StructuredCritique
        )
        
        if structured_critique.final_recommendation != "approve":
            # Apply critique adjustments to the plan
            current_plan = current_plan + "\n\n# Critic Adjustments\n"
            for issue in structured_critique.issues_found:
                if issue.severity in ["high", "critical"]:
                    current_plan += f"- {issue.issue_type}: {issue.recommendation}\n"
            
        critique_summary = f"Assessment: {structured_critique.overall_assessment}, {len(structured_critique.issues_found)} issues found"
        print_status(f"✅ {critique_summary}", Colors.GREEN if structured_critique.final_recommendation == "approve" else Colors.YELLOW)
        
    except Exception as e:
        print_status(f"⚠️  Structured critique failed, falling back to basic critique: {e}", Colors.YELLOW)
        critique = await chat_once(planner_llm, user_prompt=f"Plan:\n{current_plan}", system_prompt=CRITIC_SYS)
        if "OK" not in critique.strip().upper():
            current_plan = current_plan + "\n\n# Critic adjustments\n" + critique
        structured_critique = None

    # ---- Configure Native Structured Output Schema
    output_schema = None
    data_extraction_keywords = ['extract', 'scrape', 'get data', 'find information', 'table', 'list', 'price', 'product', 'compare', 'search results']
    
    if any(keyword in query.lower() for keyword in data_extraction_keywords):
        print_status("🔧 Configuring native structured data extraction schema...", Colors.BLUE)
        output_schema = ExtractedData
        print_status(f"   ✅ Using ExtractedData schema for structured output", Colors.GREEN)

    # ---- Milestone-based Execution with Frequent Planner/Critic Check-ins
    # Execution parameters
    CHUNK_SIZE = 4  # Execute 4 steps, then reassess
    MAX_MILESTONES = 8  # Maximum number of milestone chunks (32 total steps max)
    
    print_status("Starting milestone-based execution with frequent re-assessment...", Colors.YELLOW)
    print_status(f"🎯 Milestone Strategy: {CHUNK_SIZE} steps per milestone, up to {MAX_MILESTONES} milestones", Colors.BLUE)
    print_status("   ✅ Each milestone includes: Execute → Critique → Plan Adjustment → Continue", Colors.GREEN)
    print()
    
    all_histories = []
    milestone_count = 0
    task_completed = False
    replanning_count = 0
    
    while milestone_count < MAX_MILESTONES and not task_completed:
        milestone_count += 1
        print_status(f"\n{'='*60}", Colors.BLUE)
        print_status(f"🎯 MILESTONE {milestone_count}/{MAX_MILESTONES} - Executing {CHUNK_SIZE} steps...", Colors.BOLD + Colors.BLUE)
        print_status(f"{'='*60}\n", Colors.BLUE)
        
        # Create agent for this milestone chunk
        agent = Agent(
            task=current_plan,
            llm=executor_llm,
            browser_session=browser_session,
            output_model_schema=output_schema,
            max_steps=CHUNK_SIZE,
            extend_system_message="CRITICAL: Focus on immediate next steps. When extracting data, use structured output format. Prefer in-app viewers; avoid downloads; keep to the user's stated intent.\n\nCUSTOM ACTIONS AVAILABLE:\n\n1. 'search_web' - Fast & cheap web search via Serper API with browser fallback:\n   - Much cheaper than browser searches ($2 per 1000 vs $0.25 per search)\n   - Faster and more reliable than navigating to Google\n   - Automatically falls back to browser search if API fails\n   - Returns formatted results with titles, URLs, snippets\n   - Call with: search_web(query='your search terms', num_results=10)\n   - Use this instead of navigating to Google for research tasks\n\n2. 'fallback_extract_table' - Complete Tabular → Text → JSON pipeline:\n   - Extract: Try File→Download CSV (Google Sheets) → Select All→Copy clipboard → HTML table parsing\n   - Structure: Use LLM to map raw data to target schema (EventsSchema by default)\n   - Return: Structured JSON ready for use\n   - Call with: fallback_extract_table(want_fields=['date', 'time', 'event'], target_schema='EventsSchema')\n   - Works universally on any table/schedule across any site/app when normal extraction struggles"
        )
        
        # Register custom actions
        if hasattr(agent, 'controller') and agent.controller:
            await register_fallback_extraction_action(agent.controller, llm=executor_llm)
            await register_serper_search_action(agent.controller)
        
        try:
            # Execute milestone chunk
            chunk_history: AgentHistoryList = await agent.run()
            all_histories.append(chunk_history)
            
            # Assess progress with planner/critic
            print_status("🔍 Assessing progress with planner/critic...", Colors.YELLOW)
            progress = await assess_progress(planner_llm, query, current_plan, chunk_history)
            
            print_status(f"Progress: {progress.progress_percentage}% | Status: {progress.current_status[:50]}...", Colors.GREEN if progress.should_continue else Colors.YELLOW)
            
            # ---- NEW: Milestone Structured Critique Pass ----
            print_status(f"🔍 Running milestone {milestone_count}/{MAX_MILESTONES} structured critique...", Colors.YELLOW)
            try:
                # Gather current state for critic
                current_state = await gather_milestone_state(agent.controller if hasattr(agent, 'controller') else None, chunk_history)
                
                # Call structured critic to review execution
                milestone_critique = await structured_chat(
                    planner_llm,
                    user_prompt=f"MILESTONE {milestone_count} CRITIQUE:\n\nOriginal Plan:\n{current_plan}\n\nProgress: {progress.progress_percentage}%\n\nCurrent Status: {progress.current_status}\n\nObstacles: {', '.join(progress.obstacles_encountered)}\n\nCurrent State:\n{current_state}\n\nRecent Execution Summary:\n{summarize_chunk_history(chunk_history)}",
                    system_prompt=f"You are critiquing milestone {milestone_count}/{MAX_MILESTONES} execution. Analyze what's working, what's not, and provide specific recommendations for the next milestone. Focus on tactical adjustments rather than complete replanning.",
                    response_model=StructuredCritique
                )
                
                print_status(f"🔎 Milestone critique: {milestone_critique.overall_assessment} | {len(milestone_critique.issues_found)} issues | {milestone_critique.final_recommendation}", Colors.BLUE)
                
                # Apply high-priority critic recommendations to current plan
                if milestone_critique.issues_found:
                    high_priority_fixes = [issue for issue in milestone_critique.issues_found if issue.severity in ["high", "critical"]]
                    if high_priority_fixes:
                        print_status(f"🔧 Applying {len(high_priority_fixes)} critical/high priority fixes to plan", Colors.YELLOW)
                        current_plan += f"\n\n# Milestone {milestone_count} Critical Adjustments:\n"
                        for fix in high_priority_fixes:
                            current_plan += f"- {fix.issue_type}: {fix.recommendation}\n"
                        
            except Exception as e:
                print_status(f"⚠️  Milestone critique failed, continuing: {e}", Colors.YELLOW)
            
            # Check if task is completed
            if progress.progress_percentage >= 95 or not progress.should_continue:
                print_status(f"✅ Task completion detected! ({progress.progress_percentage}% progress)", Colors.GREEN)
                task_completed = True
                break
                
            # Handle replanning if needed
            if progress.needs_replanning and replanning_count < 2:  # Limit replanning attempts
                replanning_count += 1
                print_status(f"🔄 Replanning needed (attempt {replanning_count}/2): {progress.next_milestone}", Colors.YELLOW)
                
                # Generate new plan based on current progress
                replan_prompt = f"""Original task: {query}

Current progress: {progress.progress_percentage}%
Status: {progress.current_status}
Obstacles: {', '.join(progress.obstacles_encountered)}
Next milestone: {progress.next_milestone}

Generate a revised plan that addresses current obstacles and focuses on the next milestone."""
                
                try:
                    new_structured_plan = await structured_chat(
                        planner_llm,
                        user_prompt=replan_prompt,
                        system_prompt=PLANNER_SYS.format(task=query),
                        response_model=StructuredPlan
                    )
                    
                    # Update current plan
                    current_plan = f"Revised Task: {new_structured_plan.task_summary}\n\n"
                    current_plan += f"Success Criteria: {new_structured_plan.success_criteria}\n\n"
                    current_plan += "Revised Steps:\n"
                    for step in new_structured_plan.steps:
                        current_plan += f"{step.step_number}. {step.action}\n"
                        current_plan += f"   Expected: {step.expected_outcome}\n"
                        if step.fallback_strategy:
                            current_plan += f"   Fallback: {step.fallback_strategy}\n"
                        current_plan += "\n"
                    
                    print_status(f"✅ Plan revised with {len(new_structured_plan.steps)} updated steps", Colors.GREEN)
                    
                except Exception as e:
                    print_status(f"⚠️  Replanning failed, continuing with current plan: {e}", Colors.YELLOW)
                    
            # Handle fallback strategies
            if progress.fallback_needed != "none":
                print_status(f"🔄 Applying fallback strategy: {progress.fallback_needed}", Colors.YELLOW)
                fallback_instruction = ""
                
                if progress.fallback_needed == "table_extraction":
                    fallback_instruction = "\n\n# FALLBACK: Focus on table extraction - look for HTML tables, data grids, or structured content. Use built-in table parsing."
                elif progress.fallback_needed == "simple_search":
                    fallback_instruction = "\n\n# FALLBACK: Simplify approach - use basic search terms, focus on first few results, avoid complex interactions."
                elif progress.fallback_needed == "manual_intervention":
                    print_status("⚠️  Manual intervention may be needed - consider stopping here", Colors.YELLOW)
                    
                current_plan += fallback_instruction
                
        except Exception as e:
            print_status(f"❌ Error in milestone {milestone_count}: {str(e)}", Colors.RED)
            # Continue with next milestone if possible
            continue
    
    # Combine all histories for final processing
    if all_histories:
        # Use the most recent history as primary, but combine usage stats
        final_history = all_histories[-1]
        
        # Aggregate usage across all chunks if available
        total_usage = None
        for hist in all_histories:
            if hasattr(hist, 'usage') and hist.usage:
                if total_usage is None:
                    total_usage = hist.usage
                else:
                    # Sum up the usage stats
                    total_usage.total_prompt_tokens += hist.usage.total_prompt_tokens
                    total_usage.total_completion_tokens += hist.usage.total_completion_tokens  
                    total_usage.total_tokens += hist.usage.total_tokens
                    total_usage.total_cost += hist.usage.total_cost
        
        if total_usage:
            final_history.usage = total_usage
    else:
        # No execution occurred
        final_history = None
        
    try:
        if final_history:
            # Convert execution history to structured format
            print_status("Processing milestone execution results...", Colors.YELLOW)
            structured_result = process_agent_history_to_structured_result(final_history, query)

            # ---- Final structured critic pass on the outcome
            print_status("Running final structured critic validation...", Colors.YELLOW)
            try:
                final_critique = await structured_chat(
                    planner_llm,
                    user_prompt=f"Original Plan:\n{current_plan}\n\nExecution Summary:\n{structured_result.summary}\n\nSuccess Rate: {structured_result.success_rate:.1f}%\n\nTask Completed: {structured_result.task_completed}\n\nMilestones: {milestone_count}",
                    system_prompt=CRITIC_SYS,
                    response_model=StructuredCritique
                )
                critic_eval = f"Assessment: {final_critique.overall_assessment} | Issues: {len(final_critique.issues_found)} | Recommendation: {final_critique.final_recommendation} | Milestones: {milestone_count}"
                
            except Exception as e:
                print_status(f"⚠️  Structured final critique failed, using basic critique: {e}", Colors.YELLOW)
                critic_eval = await chat_once(
                    planner_llm,
                    user_prompt=f"Plan:\n{current_plan}\n\nOutcome:\n{structured_result.summary}",
                    system_prompt=CRITIC_SYS
                )
                final_critique = None

            # Use structured result as the final result
            final_result = structured_result.summary

            # Cost usage from browser-use
            cost_info = None
            if getattr(final_history, "usage", None):
                cost_info = {
                    "planner_model": PLANNER_MODEL,
                    "executor_model": EXECUTOR_MODEL,
                    "prompt_tokens": final_history.usage.total_prompt_tokens,
                    "completion_tokens": final_history.usage.total_completion_tokens,
                    "total_tokens": final_history.usage.total_tokens,
                    "estimated_cost": final_history.usage.total_cost,
                }
        else:
            # No execution occurred
            structured_result = StructuredExecutionResult(
                task_completed=False,
                summary="No execution occurred due to initialization issues",
                events=[],
                final_data=None,
                total_steps=0,
                success_rate=0.0
            )
            critic_eval = "No execution to evaluate"
            cost_info = None

        # Compose structured log
        result_text = f"## Structured Execution Result\n"
        result_text += f"**Task Completed:** {structured_result.task_completed}\n"
        result_text += f"**Success Rate:** {structured_result.success_rate:.1f}%\n"
        result_text += f"**Summary:** {structured_result.summary}\n\n"
        
        if structured_result.final_data:
            result_text += f"## Extracted Data\n"
            result_text += f"**Data Type:** {structured_result.final_data.data_type}\n"
            result_text += f"**Confidence:** {structured_result.final_data.confidence:.2f}\n"
            if structured_result.final_data.source_url:
                result_text += f"**Source:** {structured_result.final_data.source_url}\n"
            result_text += f"**Content:**\n```json\n{json.dumps(structured_result.final_data.content, indent=2)}\n```\n\n"
        
        result_text += f"## Execution Events\n"
        for event in structured_result.events[-5:]:  # Show last 5 events
            result_text += f"- Step {event.step_number}: {event.action_taken}\n"
            result_text += f"  Result: {event.result[:100]}{'...' if len(event.result) > 100 else ''}\n"
            result_text += f"  Success: {'✅' if event.success else '❌'}\n"
            if event.extracted_data:
                result_text += f"  Data Type: {event.extracted_data.data_type}\n"
            result_text += "\n"
        
        result_text += f"## Critic Evaluation\n{critic_eval}\n\n"
        result_text += "## Execution Details\n"
        result_text += f"- Steps taken: {structured_result.total_steps}\n"
        result_text += f"- Successful actions: {int(structured_result.success_rate / 100 * structured_result.total_steps)}\n"
        result_text += f"- Planner/Critic model: {PLANNER_MODEL}\n"
        result_text += f"- Executor model: {EXECUTOR_MODEL}\n"
        if cost_info:
            result_text += f"- Total tokens used: {cost_info['total_tokens']}\n"
            result_text += f"- Estimated cost: ${cost_info['estimated_cost']:.4f}\n"

        log_file = save_query_log(query, result_text, cost_info)

        print_status("✅ Structured query completed!", Colors.GREEN)
        print_status(f"📄 Log saved to: {log_file}", Colors.GREEN)
        if cost_info:
            print_status(f"💰 Estimated cost: ${cost_info['estimated_cost']:.4f}", Colors.YELLOW)

        # Console display with structured data
        print(f"\n{Colors.BOLD}📊 Structured Execution Result:{Colors.END}")
        print("-" * 50)
        print(f"Task Completed: {'✅ Yes' if structured_result.task_completed else '❌ No'}")
        print(f"Success Rate: {structured_result.success_rate:.1f}%")
        print(f"Steps: {structured_result.total_steps}")
        print(f"Summary: {structured_result.summary}")
        
        if structured_result.final_data:
            print(f"\n{Colors.BOLD}📋 Extracted Data ({structured_result.final_data.data_type}):{Colors.END}")
            print("-" * 30)
            content_str = json.dumps(structured_result.final_data.content, indent=2)
            if len(content_str) > 300:
                print(content_str[:300] + "...\n[Full data saved to log file]")
            else:
                print(content_str)
        print("-" * 50)

        print(f"\n{Colors.BOLD}🔍 Critic Assessment:{Colors.END}")
        print("-" * 30)
        if len(critic_eval) > 200:
            print(critic_eval[:200] + "...\n[Full evaluation saved to log file]")
        else:
            print(critic_eval)
        print("-" * 30)

        if keep_browser_open:
            print(f"\n{Colors.YELLOW}Browser is still open. You can interact with it.{Colors.END}")
            input(f"{Colors.BOLD}Press Enter to close the browser and continue...{Colors.END}")

        await browser_session.kill()
        return True

    except Exception as e:
        print_status(f"❌ Error: {str(e)}", Colors.RED)
        await browser_session.kill()
        return False

# ----------------------------
# CLI
# ----------------------------
async def main():
    print_header()

    # Require keys
    missing = []
    if not os.getenv('OPENROUTER_API_KEY'):
        missing.append('OPENROUTER_API_KEY (planner/critic)')
    if not os.getenv('GOOGLE_API_KEY'):
        missing.append('GOOGLE_API_KEY (executor)')
    if missing:
        print_status("❌ Missing required API keys:", Colors.RED)
        for k in missing:
            print_status(f"  - {k}", Colors.YELLOW)
        print_status("Add them to your .env and rerun.", Colors.YELLOW)
        return

    print(f"📁 Logs will be saved to: {LOGS_DIR.absolute()}")
    print(f"🌐 Using Chrome profile: {CHROME_PROFILE_DIR}")
    print(f"\n{Colors.GREEN}🚀 Structured Output Features Enabled:{Colors.END}")
    print(f"  • Plans: JSON schema with steps, success criteria & fallbacks")
    print(f"  • Critiques: Structured issue assessment with severity levels")
    print(f"  • Extraction: Automatic JSON formatting for tables & data")
    print(f"  • Events: Complete execution history with success tracking")
    print(f"  • Validation: Auto-retry on invalid JSON responses\n")

    while True:
        print(f"\n{Colors.BOLD}Enter your query (or 'quit' to exit):{Colors.END}")
        query = input(f"{Colors.GREEN}> {Colors.END}").strip()
        if query.lower() in ('quit', 'exit', 'q'):
            print_status("Goodbye! 👋", Colors.BLUE)
            break
        if not query:
            print_status("Please enter a valid query", Colors.YELLOW)
            continue

        print(f"\n{Colors.BOLD}Keep browser open after completion? (y/n, default: y):{Colors.END}")
        keep_open = input(f"{Colors.GREEN}> {Colors.END}").strip().lower() != 'n'
        print()

        await run_query(query, keep_browser_open=keep_open)

        # Daily summary
        today = datetime.now().strftime("%Y-%m-%d")
        summary_file = LOGS_DIR / today / "daily_summary.json"
        if summary_file.exists():
            with open(summary_file, 'r', encoding='utf-8') as f:
                summary = json.load(f)
            print(f"\n{Colors.BOLD}Today's Statistics:{Colors.END}")
            print(f"  • Queries run: {len(summary['queries'])}")
            print(f"  • Total cost: ${summary['total_cost']:.4f}")

        print(f"\n{'-'*60}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Interrupted by user{Colors.END}")
        sys.exit(0)
