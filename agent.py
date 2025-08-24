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
from browser_use.llm import ChatOpenAI, ChatAnthropic, ChatGoogle, SystemMessage, UserMessage  # NOTE: imports from browser_use.llm

# Import Serper search integration
from serper_search import search_with_serper_fallback

# Import Aug23 optimizations
from aug23_hooks import RobustnessManager, HumanGatekeeper, enhanced_agent_run

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

# Aug23 Playbook Model Strategy
PLANNER_MODEL  = "gpt-4o-mini"               # Cheaper reasoning model  
EXECUTOR_MODEL = "o3"                        # Strong executor model
STRONG_MODEL   = "claude-3-5-sonnet-20241022"  # Escalation model for failures

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
    print(f"{Colors.BLUE}{Colors.BOLD}Browser-Use Query Tool - Task Router Edition{Colors.END}")
    print(f"{Colors.GREEN}Lightweight Task Classification + Simplified Execution Flow{Colors.END}")
    print(f"{Colors.YELLOW}Planner: gpt-4o-mini | Executor: o3 | Escalation: claude-3-5-sonnet{Colors.END}")
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
    print_status("Attempting fallback table extraction...", Colors.YELLOW)
    
    extraction_method = "unknown"
    headers = []
    rows = []
    confidence = 0.5
    
    try:
        # Strategy 1: Try to download as CSV (works for Google Sheets, some web apps)
        print_status("  Strategy 1: Attempting CSV download...", Colors.BLUE)
        
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
                        print_status("  Found download option", Colors.GREEN)
                        
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
                                    print_status("  CSV download initiated", Colors.GREEN)
                                    
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
                print_status("  No download option found", Colors.YELLOW)
                
        except Exception as e:
            print_status(f"  CSV download failed: {e}", Colors.YELLOW)
        
        # Strategy 2: Select All + Copy (most reliable fallback)
        print_status("  Strategy 2: Attempting select all + copy...", Colors.BLUE)
        
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
                    print_status("  Clipboard content retrieved", Colors.GREEN)
                    
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
                            
                            print_status(f"  Parsed {len(rows)} rows with {len(headers)} columns", Colors.GREEN)
                            
                        else:
                            print_status("  Could not parse clipboard content as table", Colors.YELLOW)
                else:
                    print_status("  Clipboard content too short or empty", Colors.YELLOW)
                    
            except Exception as e:
                print_status(f"  Clipboard access failed: {e}", Colors.YELLOW)
                
        except Exception as e:
            print_status(f"  Select all + copy failed: {e}", Colors.YELLOW)
        
        # Strategy 3: HTML table parsing (last resort)
        if not rows:
            print_status("  Strategy 3: Attempting HTML table parsing...", Colors.BLUE)
            
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
                            
                            print_status(f"  Parsed HTML table: {len(rows)} rows, {len(headers)} columns", Colors.GREEN)
                else:
                    print_status("  No HTML tables found", Colors.YELLOW)
                    
            except Exception as e:
                print_status(f"  HTML table parsing failed: {e}", Colors.YELLOW)
        
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
            
            print_status(f"Fallback extraction successful: {len(rows)} rows, {len(headers)} columns", Colors.GREEN)
            
        else:
            print_status("All extraction strategies failed", Colors.RED)
            extraction_method = "failed"
            confidence = 0.0
    
    except Exception as e:
        print_status(f"Fallback extraction error: {e}", Colors.RED)
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
        print_status(f"Successfully structured {result.get('total_count', 0)} items", Colors.GREEN)
        
        return result
        
    except json.JSONDecodeError as e:
        print_status(f"JSON parsing error: {e}", Colors.RED)
        return {
            "error": f"Failed to parse LLM response as JSON: {e}",
            "events": [],
            "total_count": 0,
            "extraction_source": f"error_from_{table_data.extraction_method}"
        }
    except Exception as e:
        print_status(f"LLM structuring error: {e}", Colors.RED)
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
        print_status("Starting fallback table extraction with LLM structuring...", Colors.BLUE)
        
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
            print_status("Returning raw table data (no LLM structuring)", Colors.YELLOW)
            return {
                "headers": table_data.headers,
                "rows": table_data.rows,
                "row_count": table_data.row_count,
                "column_count": table_data.column_count,
                "extraction_method": table_data.extraction_method,
                "confidence": table_data.confidence
            }
    
    print_status("Registered custom action: fallback_extract_table (with LLM structuring)", Colors.GREEN)

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
        print_status(f"Searching web: {query}", Colors.BLUE)
        
        result = await search_with_serper_fallback(controller, query, num_results)
        return result.extracted_content
    
    print_status("Registered custom action: search_web (Serper API with browser fallback)", Colors.GREEN)

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
                print_status(f"Failed to get valid structured response after {max_retries} attempts", Colors.RED)
                print_status(f"Last response: {resp.completion[:200]}...", Colors.YELLOW)
                raise ValueError(f"Could not get valid {response_model.__name__} after {max_retries} attempts: {e}")
            
            print_status(f"Invalid JSON response (attempt {attempt + 1}/{max_retries}), retrying...", Colors.YELLOW)
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
# Task Classification Schema
# ----------------------------
class TaskType(BaseModel):
    """Classification of the user's task type."""
    category: str = Field(description="Task category: data_extraction, research, navigation, transaction")
    complexity: str = Field(description="Task complexity: simple, moderate, complex")
    requires_structured_output: bool = Field(description="Whether this task needs structured JSON output")
    requires_planning: bool = Field(description="Whether this task needs upfront planning")
    estimated_steps: int = Field(description="Estimated number of steps needed (1-20)")

# ----------------------------
# Task Router
# ----------------------------
class TaskRouter:
    """Lightweight task classification and routing."""
    
    @staticmethod
    async def classify_task(llm, query: str) -> TaskType:
        """Classify the user's task and determine execution strategy."""
        classification_prompt = f"""Classify this user query into a task type:

QUERY: {query}

Categories:
- data_extraction: Extracting tables, schedules, contact info, product details
- research: Web searches, information gathering, fact checking  
- navigation: Going to specific pages, logging in, basic interactions
- transaction: Purchases, form submissions, account changes

Complexity levels:
- simple: Single page, basic interaction (1-3 steps)
- moderate: Multiple pages, some logic (4-8 steps)
- complex: Multi-step workflows, conditional logic (9+ steps)

Structured output needed for data extraction tasks only.
Planning needed for moderate/complex tasks only."""
        
        classification_sys = """You are a task classifier. Analyze the user query and determine:
1. What category of task this is
2. How complex the task is
3. Whether it needs structured JSON output (data extraction only)
4. Whether it needs upfront planning (moderate/complex only)
5. Estimated number of steps

Output valid JSON matching TaskType schema."""
        
        try:
            return await structured_chat(
                llm,
                user_prompt=classification_prompt,
                system_prompt=classification_sys,
                response_model=TaskType
            )
        except Exception as e:
            print_status(f"Task classification failed, using defaults: {e}", Colors.YELLOW)
            return TaskType(
                category="navigation",
                complexity="moderate", 
                requires_structured_output=False,
                requires_planning=True,
                estimated_steps=5
            )
    
    @staticmethod
    def get_task_system_prompt(task_type: TaskType) -> str:
        """Get task-specific system prompt based on classification."""
        base_prompt = "You are a web automation agent. Follow the user's intent precisely."
        
        if task_type.category == "data_extraction":
            return f"{base_prompt} Focus on extracting structured data. Use table parsing and data extraction actions. Output structured JSON when complete."
        elif task_type.category == "research":
            return f"{base_prompt} Focus on information gathering. Use search actions efficiently. Synthesize findings clearly."
        elif task_type.category == "navigation":
            return f"{base_prompt} Focus on reaching the target page or state. Navigate efficiently with minimal steps."
        elif task_type.category == "transaction":
            return f"{base_prompt} Focus on completing the transaction safely. Verify each step before proceeding."
        else:
            return base_prompt

# ----------------------------
# Core runner with single upfront query normalization and failure-triggered critique
# ----------------------------
async def run_query(query: str, keep_browser_open: bool = True) -> bool:
    print_status("Initializing simplified execution flow...", Colors.YELLOW)
    
    # Initialize models
    planner_llm = ChatOpenAI(model=PLANNER_MODEL)
    executor_llm = ChatOpenAI(model=EXECUTOR_MODEL)
    
    try:
        # Step 1: Task Classification
        print_status("Step 1: Classifying task type", Colors.BLUE)
        task_type = await TaskRouter.classify_task(planner_llm, query)
        print_status(f"Task classified: {task_type.category} ({task_type.complexity}, {task_type.estimated_steps} steps)", Colors.GREEN)
        
        # Step 2: Generate Plan (only if complex task)
        plan = None
        if task_type.requires_planning:
            print_status("Step 2: Generating structured plan", Colors.BLUE)
            try:
                plan = await structured_chat(
                    planner_llm,
                    user_prompt=query,
                    system_prompt=PLANNER_SYS.format(task=query),
                    response_model=StructuredPlan
                )
                print_status(f"Plan generated with {len(plan.steps)} steps", Colors.GREEN)
            except Exception as e:
                print_status(f"Planning failed, proceeding without plan: {e}", Colors.YELLOW)
        
        # Step 3: Browser Setup
        print_status("Step 3: Setting up browser", Colors.BLUE)
        browser_profile = BrowserProfile(
            user_data_dir=CHROME_PROFILE_DIR,
            keep_alive=keep_browser_open,
            headless=False,
            wait_for_network_idle_page_load_time=3.0,
            minimum_wait_page_load_time=0.5,
            maximum_wait_page_load_time=8.0,
            wait_between_actions=0.7,
            default_timeout=10_000,
            default_navigation_timeout=45_000,
        )
        browser_session = BrowserSession(browser_profile=browser_profile)
        
        # Step 4: Configure Task-Specific Agent
        print_status("Step 4: Configuring agent for task type", Colors.BLUE)
        
        # Get task-specific system prompt
        task_system_prompt = TaskRouter.get_task_system_prompt(task_type)
        
        # Set output schema only for data extraction tasks
        output_schema = ExtractedData if task_type.requires_structured_output else None
        if output_schema:
            print_status("Structured output enabled for data extraction", Colors.BLUE)
        
        # Build task description
        if plan:
            task_description = f"Task: {plan.task_summary}\n\nSuccess Criteria: {plan.success_criteria}\n\nSteps:\n"
            for step in plan.steps:
                task_description += f"{step.step_number}. {step.action}\n"
        else:
            task_description = query
        
        # Create agent with task-specific configuration
        agent = Agent(
            task=task_description,
            llm=executor_llm,
            browser_session=browser_session,
            output_model_schema=output_schema,
            max_steps=min(task_type.estimated_steps + 3, 20),  # Add buffer but cap at 20
            max_actions_per_step=3,
            max_failures=3,
            retry_delay=8,
            use_vision=True,
            vision_detail_level="auto",
            save_conversation_path=str(LOGS_DIR / "conversations"),
            extend_system_message=task_system_prompt + " CUSTOM ACTIONS: 'search_web', 'fallback_extract_table' are available."
        )

        # Register custom actions
        if hasattr(agent, 'controller') and agent.controller:
            await register_fallback_extraction_action(agent.controller, llm=executor_llm)
            await register_serper_search_action(agent.controller)

        # Step 5: Execute with robustness hooks
        print_status("Step 5: Executing task", Colors.BLUE)
        robustness = RobustnessManager(strong_model_name=STRONG_MODEL)
        from aug23_hooks import CostManager
        cost_mgr = CostManager(cheap_model_name="gemini-2.5-flash")

        await robustness.on_step_start(agent, {"step_number": 0, "action_type": "initial_execution"})
        if cost_mgr.should_downshift(agent):
            cost_mgr.downshift_model(agent)

        history: AgentHistoryList = await agent.run()

        step_success = len(history) > 0 and all(
            not hasattr(event, 'error') or not event.error for event in history
        )
        await robustness.on_step_end(agent, {"success": step_success})

        # Step 6: Process Results
        print_status("Step 6: Processing results", Colors.BLUE)
        structured_result = process_agent_history_to_structured_result(history, query)

        # Step 7: Final Critique (if data extraction task)
        critic_eval = None
        if task_type.requires_structured_output or task_type.complexity != "simple":
            print_status("Step 7: Running critic evaluation", Colors.BLUE)
            try:
                final_critique = await structured_chat(
                    planner_llm,
                    user_prompt=f"Task: {query}\n\nExecution Summary: {structured_result.summary}\n\nSuccess Rate: {structured_result.success_rate:.1f}%\n\nCompleted: {structured_result.task_completed}",
                    system_prompt=CRITIC_SYS,
                    response_model=StructuredCritique
                )
                critic_eval = f"Assessment: {final_critique.overall_assessment} | Issues: {len(final_critique.issues_found)} | Recommendation: {final_critique.final_recommendation}"
            except Exception as e:
                print_status(f"Critic evaluation failed: {e}", Colors.YELLOW)
                critic_eval = "Critic evaluation not available"
        
        # Step 8: Prepare output
        cost_info = None
        if getattr(history, "usage", None):
            cost_info = {
                "planner_model": PLANNER_MODEL,
                "executor_model": EXECUTOR_MODEL,
                "prompt_tokens": history.usage.total_prompt_tokens,
                "completion_tokens": history.usage.total_completion_tokens,
                "total_tokens": history.usage.total_tokens,
                "estimated_cost": history.usage.total_cost,
            }

        # Create result text
        result_text = f"## Task Execution Result\n"
        result_text += f"**Task Type:** {task_type.category} ({task_type.complexity})\n"
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
        
        if plan:
            result_text += f"## Original Plan\n"
            result_text += f"**Task:** {plan.task_summary}\n"
            result_text += f"**Estimated Duration:** {plan.estimated_duration_minutes} minutes\n\n"
        
        if critic_eval:
            result_text += f"## Critic Evaluation\n{critic_eval}\n\n"
        
        result_text += "## Execution Details\n"
        result_text += f"- Task Type: {task_type.category}\n"
        result_text += f"- Complexity: {task_type.complexity}\n"
        result_text += f"- Steps taken: {structured_result.total_steps}\n"
        result_text += f"- Successful actions: {int(structured_result.success_rate / 100 * structured_result.total_steps)}\n"
        result_text += f"- Planner model: {PLANNER_MODEL}\n"
        result_text += f"- Executor model: {EXECUTOR_MODEL}\n"
        if cost_info:
            result_text += f"- Total tokens used: {cost_info['total_tokens']}\n"
            result_text += f"- Estimated cost: ${cost_info['estimated_cost']:.4f}\n"

        log_file = save_query_log(query, result_text, cost_info)

        print_status("Query completed!", Colors.GREEN)
        print_status(f"Log saved to: {log_file}", Colors.GREEN)
        if cost_info:
            print_status(f"Estimated cost: ${cost_info['estimated_cost']:.4f}", Colors.YELLOW)

        # Console display
        print(f"\n{Colors.BOLD}Task Execution Result:{Colors.END}")
        print("-" * 50)
        print(f"Task Type: {task_type.category} ({task_type.complexity})")
        print(f"Task Completed: {'Yes' if structured_result.task_completed else 'No'}")
        print(f"Success Rate: {structured_result.success_rate:.1f}%")
        print(f"Steps: {structured_result.total_steps}")
        print(f"Summary: {structured_result.summary}")
        
        if structured_result.final_data:
            print(f"\n{Colors.BOLD}Extracted Data ({structured_result.final_data.data_type}):{Colors.END}")
            print("-" * 30)
            content_str = json.dumps(structured_result.final_data.content, indent=2)
            if len(content_str) > 300:
                print(content_str[:300] + "...\n[Full data saved to log file]")
            else:
                print(content_str)
        print("-" * 50)

        if critic_eval and len(critic_eval) > 20:
            print(f"\n{Colors.BOLD}Critic Assessment:{Colors.END}")
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
        print_status(f"Error during execution: {str(e)}", Colors.RED)
        try:
            await browser_session.kill()
        except:
            pass
        return False

# ----------------------------
# CLI
# ----------------------------
async def main():
    print_header()

    # Require keys for aug23 model strategy
    missing = []
    if not os.getenv('OPENAI_API_KEY'):
        missing.append('OPENAI_API_KEY (planner: gpt-4o-mini, executor: o3)')
    if not os.getenv('ANTHROPIC_API_KEY'):
        missing.append('ANTHROPIC_API_KEY (escalation: claude-3-5-sonnet)')
    if missing:
        print_status("Missing required API keys for aug23 model strategy:", Colors.RED)
        for k in missing:
            print_status(f"  - {k}", Colors.YELLOW)
        print_status("Add them to your .env and rerun.", Colors.YELLOW)
        return

    print(f"Logs will be saved to: {LOGS_DIR.absolute()}")
    print(f"Using Chrome profile: {CHROME_PROFILE_DIR}")
    print(f"\n{Colors.GREEN}Task Router Features:{Colors.END}")
    print(f"  * Automatic task classification (data_extraction, research, navigation, transaction)")
    print(f"  * Task-specific system prompts and configurations")
    print(f"  * Structured output only for data extraction tasks")
    print(f"  * Planning only for moderate/complex tasks")
    print(f"  * Simplified execution flow with robustness hooks\n")

    while True:
        print(f"\n{Colors.BOLD}Enter your query (or 'quit' to exit):{Colors.END}")
        query = input(f"{Colors.GREEN}> {Colors.END}").strip()
        if query.lower() in ('quit', 'exit', 'q'):
            print_status("Goodbye!", Colors.BLUE)
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
