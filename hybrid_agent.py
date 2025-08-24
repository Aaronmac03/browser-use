"""
Production-Ready Hybrid Vision Agent - Interactive Browser-Use Query Tool with Hybrid Vision

This integrates the hybrid local vision + cloud reasoning system with the main agent.py framework.

Key Features:
- Local MiniCPM-V vision processing for fast, cheap actions
- Intelligent escalation to cloud for complex scenarios
- Maintains all existing agent.py features (TaskRouter, cost tracking, structured output)
- Preserves the familiar CLI interface and workflow

Run with: python hybrid_agent.py
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
from browser_use.llm import ChatOpenAI, ChatAnthropic, ChatGoogle, SystemMessage, UserMessage

# Import Serper search integration
from serper_search import search_with_serper_fallback

# Import Aug23 optimizations
from aug23_hooks import RobustnessManager, HumanGatekeeper, enhanced_agent_run

# Import hybrid components
from hybrid.handoff_manager import HandoffManager
from hybrid.vision_state_builder import VisionStateBuilder
from hybrid.local_action_heuristics import LocalActionHeuristics
from hybrid.cloud_planner_client import CloudPlannerClient
from hybrid.schemas import VisionState, Action, ActionTarget

# ----------------------------
# Configuration - Extended for Hybrid
# ----------------------------
CHROME_PROFILE_DIR = 'C:/Users/drmcn/.config/browseruse/profiles/default'
LOGS_DIR = Path('browser_queries')
LOGS_DIR.mkdir(exist_ok=True)

# Aug23 Playbook Model Strategy (retained from original agent.py)
PLANNER_MODEL  = "gpt-4o-mini"               # Cheaper reasoning model  
EXECUTOR_MODEL = "o3"                        # Strong executor model
STRONG_MODEL   = "claude-3-5-sonnet-20241022"  # Escalation model for failures

# Hybrid Configuration - NEW
USE_HYBRID_VISION = True                     # Toggle between hybrid and standard
OLLAMA_URL = "http://localhost:11434"        # Local Ollama server
MINICPM_MODEL = "minicpm-v:2.6"             # Local vision model
VISION_CONFIDENCE_THRESHOLD = 0.7           # Confidence threshold for local vision
LOCAL_ACTION_CONFIDENCE = 0.8               # Confidence threshold for local actions
SIMILARITY_THRESHOLD = 0.8                  # Text similarity threshold

# ----------------------------
# Structured Output Schemas (retained from agent.py)
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

class ExtractedData(BaseModel):
    """Generic structured data extraction result."""
    data_type: str = Field(description="Type of data extracted (table, list, text, product, etc.)")
    content: Any = Field(description="The actual extracted data in structured format (can be dict, list, string, etc.)")
    confidence: float = Field(description="Confidence score 0-1 for extraction quality")
    source_url: Optional[str] = Field(description="URL where data was extracted from", default=None)
    timestamp: str = Field(description="When the data was extracted", default_factory=lambda: datetime.now().isoformat())

# Common schema for events/appointments
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

# Task Classification Schema
class TaskType(BaseModel):
    """Classification of the user's task type."""
    category: str = Field(description="Task category: data_extraction, research, navigation, transaction")
    complexity: str = Field(description="Task complexity: simple, moderate, complex")
    requires_structured_output: bool = Field(description="Whether this task needs structured JSON output")
    requires_planning: bool = Field(description="Whether this task needs upfront planning")
    estimated_steps: int = Field(description="Estimated number of steps needed (1-20)")

# Fallback Table Extraction Schema
class TableData(BaseModel):
    """Structured representation of extracted table data."""
    headers: List[str] = Field(description="Column headers from the table")
    rows: List[List[str]] = Field(description="Data rows as lists of strings")
    row_count: int = Field(description="Number of data rows")
    column_count: int = Field(description="Number of columns")
    extraction_method: str = Field(description="How the data was extracted (csv_download, clipboard_copy, html_parse)")
    confidence: float = Field(description="Confidence in extraction quality (0-1)")

# ----------------------------
# Terminal colors and utilities
# ----------------------------
class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    PURPLE = '\033[95m'  # NEW - for hybrid indicators

def print_header():
    print(f"\n{Colors.BOLD}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}Browser-Use Hybrid Agent - Vision + Cloud Reasoning{Colors.END}")
    print(f"{Colors.PURPLE}Local Vision: MiniCPM-V 2.6 | Cloud Planner: Gemini 2.0 Flash{Colors.END}")
    print(f"{Colors.GREEN}Planner: {PLANNER_MODEL} | Executor: {EXECUTOR_MODEL} | Escalation: {STRONG_MODEL}{Colors.END}")
    print(f"{Colors.BOLD}{'='*80}{Colors.END}\n")

def print_status(message, color=Colors.BLUE):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{ts}] {message}{Colors.END}")

def print_hybrid_status(message, used_local=False):
    """Special status printer for hybrid operations"""
    prefix = f"{Colors.PURPLE}[LOCAL]{Colors.END}" if used_local else f"{Colors.BLUE}[CLOUD]{Colors.END}"
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{prefix} [{ts}] {message}")

# ----------------------------
# Logging helpers (retained from agent.py)
# ----------------------------
def save_query_log(query, result, cost_info=None, hybrid_stats=None):
    """Enhanced logging with hybrid statistics"""
    timestamp = datetime.now()
    date_str = timestamp.strftime("%Y-%m-%d")
    time_str = timestamp.strftime("%H-%M-%S")

    daily_dir = LOGS_DIR / date_str
    daily_dir.mkdir(exist_ok=True)

    log_file = daily_dir / f"{time_str}_hybrid_query.md"
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(f"# Hybrid Browser Query Log\n")
        f.write(f"**Date:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## Query\n```\n{query}\n```\n\n")
        f.write(f"## Result\n{result}\n\n")
        
        if hybrid_stats:
            f.write("## Hybrid Vision Statistics\n")
            f.write(f"- Local actions: {hybrid_stats.get('local_actions', 0)}\n")
            f.write(f"- Cloud actions: {hybrid_stats.get('cloud_actions', 0)}\n")
            f.write(f"- Total actions: {hybrid_stats.get('total_actions', 0)}\n")
            f.write(f"- Local success rate: {hybrid_stats.get('local_success_rate', 0):.1f}%\n")
            f.write(f"- Ollama availability: {hybrid_stats.get('ollama_available', 'Unknown')}\n\n")
        
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
        "hybrid_enabled": USE_HYBRID_VISION,
        "local_actions": hybrid_stats.get('local_actions', 0) if hybrid_stats else 0,
        "cloud_actions": hybrid_stats.get('cloud_actions', 0) if hybrid_stats else 0,
    }

    if summary_file.exists():
        with open(summary_file, 'r', encoding='utf-8') as f:
            summary = json.load(f)
    else:
        summary = {"queries": [], "total_cost": 0, "total_local_actions": 0, "total_cloud_actions": 0}

    summary["queries"].append(summary_entry)
    summary["total_cost"] += summary_entry["cost"]
    summary["total_local_actions"] += summary_entry["local_actions"]
    summary["total_cloud_actions"] += summary_entry["cloud_actions"]

    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    return log_file

# ----------------------------
# Hybrid Vision Utilities
# ----------------------------
async def check_ollama_availability() -> bool:
    """Check if Ollama is running and MiniCPM-V is available"""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [model.get("name", "") for model in models]
                return any(MINICPM_MODEL in name for name in model_names)
    except Exception:
        pass
    return False

# ----------------------------
# LLM Communication Functions (retained from agent.py)
# ----------------------------
async def simple_chat(llm, user_prompt: str, system_prompt: str = None) -> str:
    """Basic LLM chat without structured output."""
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
                raise ValueError(f"Failed to get valid JSON after {max_retries} attempts: {e}")
            
            messages.append(SystemMessage(content=f"Your previous response was invalid JSON. Error: {e}. Please provide ONLY valid JSON matching the schema."))

# ----------------------------
# System Prompts (retained from agent.py)
# ----------------------------
PLANNER_SYS = """You are a high-reliability web plan generator for a browser automation agent (Browser-Use v0.6+).

Output: a concise, numbered, end-to-end plan that a non-deterministic agent can follow.

General best practices:
- Prefer first-party, in-app viewers (e.g., Google Drive/Docs/Sheets/Calendar) over downloading files.
- Avoid third-party file converters unless explicitly requested.
- Keep actions inside the smallest number of trusted domains needed to finish the task.
- Bring the correct tab to the foreground before interacting; avoid acting on background tabs.
- Use clear recovery strategies for common failures (missing element, wrong page, 2FA, rate-limit).
- Never perform actions outside the user's stated intent. If a step is ambiguous, proceed with the safest common-sense assumption and continue.

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
# Process Agent History (retained from agent.py)
# ----------------------------
def process_agent_history_to_structured_result(history: AgentHistoryList, task: str) -> StructuredExecutionResult:
    """Convert agent history to structured execution result."""
    events = []
    final_data = None
    task_completed = False
    
    for i, event in enumerate(history):
        success = not (hasattr(event, 'error') and event.error)
        
        # Try to extract any data from the event
        extracted = None
        if hasattr(event, 'result') and event.result:
            try:
                # Check if result looks like structured data
                result_text = str(event.result)
                if any(marker in result_text.lower() for marker in ['json', '{', 'data_type', 'extracted']):
                    # This might be structured data - let's see if we can extract it
                    if hasattr(event.result, 'data_type'):
                        extracted = ExtractedData(
                            data_type=getattr(event.result, 'data_type', 'unknown'),
                            content=getattr(event.result, 'content', result_text),
                            confidence=getattr(event.result, 'confidence', 0.5)
                        )
                        final_data = extracted  # Keep the last structured data as final
            except Exception:
                pass  # Not structured data
        
        # Determine action taken
        action_taken = "unknown"
        if hasattr(event, 'action_type'):
            action_taken = event.action_type
        elif hasattr(event, 'type'):
            action_taken = event.type
        
        events.append(ExecutionEvent(
            step_number=i + 1,
            action_taken=action_taken,
            result=str(event.result) if hasattr(event, 'result') else "No result",
            success=success,
            extracted_data=extracted,
            error_message=str(event.error) if hasattr(event, 'error') and event.error else None
        ))
    
    # Determine if task was completed (look for completion indicators)
    if events:
        last_event = events[-1]
        task_completed = (
            last_event.success and 
            any(word in last_event.result.lower() for word in ['completed', 'finished', 'done', 'success'])
        )
    
    # Calculate success rate
    total_steps = len(events)
    successful_steps = sum(1 for event in events if event.success)
    success_rate = (successful_steps / max(total_steps, 1)) * 100
    
    # Generate summary
    final_result = None
    if hasattr(history, 'final_result') and history.final_result:
        final_result = str(history.final_result)
    
    return StructuredExecutionResult(
        task_completed=task_completed,
        summary=final_result or f"Executed {total_steps} steps with {successful_steps} successful actions",
        events=events,
        final_data=final_data,
        total_steps=total_steps,
        success_rate=success_rate
    )

# ----------------------------
# Task Router (retained from agent.py)
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
# Custom Actions (adapted from agent.py for hybrid system)
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
                                    await controller.page.wait_for_timeout(3000)
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
                            rows = [row for row in parsed_rows[1:] if any(cell.strip() for cell in row)]
                            
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
                                    if any(cell for cell in row_data):
                                        rows.append(row_data)
                            
                            extraction_method = "html_parse"
                            confidence = 0.6
                            
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
                    confidence += 0.1
            
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
    """
    if not table_data.rows:
        return {"error": "No table data to structure", "events": [], "total_count": 0}
    
    # Create text representation of the table
    table_text = f"HEADERS: {', '.join(table_data.headers)}\n\nROWS:\n"
    for i, row in enumerate(table_data.rows[:20]):  # Limit to first 20 rows for token efficiency
        table_text += f"{i+1}: {', '.join(row)}\n"
    
    if len(table_data.rows) > 20:
        table_text += f"... and {len(table_data.rows) - 20} more rows\n"
    
    structuring_prompt = f"""Convert this table data into structured JSON following the {target_schema_name} format.

Raw Table Data:
{table_text}

Instructions:
- Extract all relevant information into the target schema
- Parse dates into YYYY-MM-DD format when possible
- Clean and normalize text fields
- Include confidence scores and metadata
- If some fields are missing, use null or empty values
- Return valid JSON only"""

    try:
        if target_schema:
            structured_result = await structured_chat(
                llm,
                user_prompt=structuring_prompt,
                system_prompt=f"You are a data structuring specialist. Convert table data to {target_schema_name} JSON format.",
                response_model=target_schema
            )
            
            return {
                "events": structured_result.events if hasattr(structured_result, 'events') else [],
                "total_count": structured_result.total_count if hasattr(structured_result, 'total_count') else len(table_data.rows),
                "date_range": getattr(structured_result, 'date_range', None),
                "extraction_source": f"llm_structured_{table_data.extraction_method}",
                "confidence": min(table_data.confidence + 0.2, 1.0)
            }
        else:
            # Fallback without schema validation
            response = await simple_chat(
                llm,
                user_prompt=structuring_prompt,
                system_prompt="Convert the table data to structured JSON format."
            )
            
            try:
                structured_data = json.loads(response)
                return structured_data
            except json.JSONDecodeError:
                return {
                    "error": "Failed to parse LLM response as JSON",
                    "raw_response": response[:500],
                    "fallback_data": {
                        "headers": table_data.headers,
                        "rows": table_data.rows,
                        "extraction_method": table_data.extraction_method
                    }
                }
                
    except Exception as e:
        return {
            "error": f"LLM structuring failed: {str(e)}",
            "fallback_data": {
                "headers": table_data.headers,
                "rows": table_data.rows,
                "extraction_method": table_data.extraction_method,
                "confidence": table_data.confidence
            }
        }

async def register_fallback_extraction_action(controller, llm=None):
    """Register the fallback table extraction as a custom action."""
    
    @controller.action("fallback_extract_table")
    async def fallback_extract_table_action(want_fields: List[str] = None, target_schema: str = "EventsSchema", structure_with_llm: bool = True) -> dict:
        """
        Generic fallback table extraction that works on any schedule/table.
        Completes the "Tabular → Text → JSON" pipeline.
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
    
    print_status("Registered custom action: fallback_extract_table (hybrid mode)", Colors.GREEN)

async def register_serper_search_action(controller):
    """Register the Serper API search as a custom action with browser fallback."""
    
    @controller.action("search_web")
    async def search_web_action(query: str, num_results: int = 10) -> str:
        """Search the web using Serper API with browser fallback."""
        try:
            results = search_with_serper_fallback(query, num_results)
            print_status(f"Web search completed: {query}", Colors.GREEN)
            return results
        except Exception as e:
            print_status(f"Search failed: {e}", Colors.RED)
            return f"Search failed: {str(e)}"
    
    print_status("Registered custom action: search_web (hybrid mode)", Colors.GREEN)

# ----------------------------
# Hybrid Agent Implementation
# ----------------------------
class HybridAgentWrapper:
    """
    Wrapper that integrates hybrid vision components with the browser-use Agent.
    This replaces the standard agent's vision processing with the hybrid system.
    """
    
    def __init__(
        self,
        task: str,
        llm,
        browser_session: BrowserSession,
        output_model_schema=None,
        max_steps: int = 20,
        **agent_kwargs
    ):
        self.task = task
        self.llm = llm
        self.browser_session = browser_session
        self.output_model_schema = output_model_schema
        self.max_steps = max_steps
        self.agent_kwargs = agent_kwargs
        
        # Initialize hybrid components
        self.handoff_manager = None
        self.hybrid_stats = {
            "local_actions": 0,
            "cloud_actions": 0,
            "total_actions": 0,
            "local_successes": 0,
            "ollama_available": False
        }
        
        # Original agent for fallback
        self.agent = None
    
    async def initialize_hybrid_components(self) -> bool:
        """Initialize hybrid vision components. Returns True if successful."""
        try:
            # Check Ollama availability
            ollama_available = await check_ollama_availability()
            self.hybrid_stats["ollama_available"] = ollama_available
            
            if not ollama_available or not USE_HYBRID_VISION:
                print_hybrid_status("Hybrid vision disabled or Ollama not available, falling back to standard mode")
                return False
            
            # Initialize hybrid components
            vision_builder = VisionStateBuilder(
                ollama_base_url=OLLAMA_URL,
                model_name=MINICPM_MODEL,
                confidence_threshold=VISION_CONFIDENCE_THRESHOLD
            )
            
            local_heuristics = LocalActionHeuristics(
                confidence_threshold=LOCAL_ACTION_CONFIDENCE,
                similarity_threshold=SIMILARITY_THRESHOLD
            )
            
            google_api_key = os.getenv("GOOGLE_API_KEY")
            if not google_api_key:
                print_hybrid_status("GOOGLE_API_KEY not found, cloud escalation disabled")
                return False
            
            cloud_client = CloudPlannerClient(
                api_key=google_api_key,
                model_name="gemini-2.0-flash-exp"
            )
            
            self.handoff_manager = HandoffManager(
                vision_builder=vision_builder,
                local_heuristics=local_heuristics,
                cloud_client=cloud_client
            )
            
            # Initialize vision builder context
            await vision_builder.__aenter__()
            
            print_hybrid_status("Hybrid components initialized successfully")
            return True
            
        except Exception as e:
            print_hybrid_status(f"Failed to initialize hybrid components: {e}")
            return False
    
    async def run(self) -> AgentHistoryList:
        """Run the agent with hybrid vision processing."""
        
        # Try to initialize hybrid components
        hybrid_initialized = await self.initialize_hybrid_components()
        
        if not hybrid_initialized:
            # Fall back to standard agent
            print_hybrid_status("Falling back to standard browser-use agent")
            self.agent = Agent(
                task=self.task,
                llm=self.llm,
                browser_session=self.browser_session,
                output_model_schema=self.output_model_schema,
                max_steps=self.max_steps,
                **self.agent_kwargs
            )
            return await self.agent.run()
        
        # Run with hybrid system
        print_hybrid_status("Starting hybrid execution")
        return await self._run_hybrid()
    
    async def _run_hybrid(self) -> AgentHistoryList:
        """Execute using the hybrid vision system."""
        
        history = AgentHistoryList([])
        step_count = 0
        current_intent = self.task
        
        # Start browser session if not already started
        if not hasattr(self.browser_session, 'context') or not self.browser_session.context:
            await self.browser_session.start()
        
        try:
            while step_count < self.max_steps:
                step_count += 1
                print_hybrid_status(f"Step {step_count}/{self.max_steps}: {current_intent[:60]}...")
                
                # Get current page info
                page_info = await self._get_current_page_info()
                if not page_info:
                    print_hybrid_status("Could not get page information, stopping")
                    break
                
                # Take screenshot
                screenshot_data = await self._take_screenshot()
                if not screenshot_data:
                    print_hybrid_status("Could not take screenshot, stopping")
                    break
                
                # Process intent with hybrid manager
                try:
                    action, reasoning, used_cloud = await self.handoff_manager.process_intent(
                        current_intent,
                        screenshot_data,
                        page_info["url"],
                        page_info["title"],
                        page_info["viewport"],
                        page_info["scroll_y"]
                    )
                    
                    # Update statistics
                    self.hybrid_stats["total_actions"] += 1
                    if used_cloud:
                        self.hybrid_stats["cloud_actions"] += 1
                    else:
                        self.hybrid_stats["local_actions"] += 1
                    
                    print_hybrid_status(f"Action: {action.op} | Reasoning: {reasoning[:80]}...", used_local=not used_cloud)
                    
                    # Execute the action
                    result = await self._execute_hybrid_action(action)
                    
                    # Record result with handoff manager
                    self.handoff_manager.record_action_result(action, result["status"], result["message"])
                    
                    # Update success statistics
                    if result["status"] == "ok" and not used_cloud:
                        self.hybrid_stats["local_successes"] += 1
                    
                    # Create history entry
                    history_entry = self._create_history_entry(step_count, action, result, reasoning)
                    history.append(history_entry)
                    
                    # Check completion
                    if self._is_task_complete(result, step_count):
                        print_hybrid_status("Task appears complete")
                        break
                    
                    # Update intent for next iteration (simplified for demo)
                    if result["status"] != "ok":
                        current_intent = f"Retry or recover from failed action: {action.op}"
                    
                except Exception as e:
                    print_hybrid_status(f"Error in hybrid processing: {e}")
                    # Create error entry
                    error_entry = self._create_error_entry(step_count, str(e))
                    history.append(error_entry)
                    break
        
        finally:
            # Clean up hybrid components
            if self.handoff_manager and hasattr(self.handoff_manager.vision_builder, '__aexit__'):
                try:
                    await self.handoff_manager.vision_builder.__aexit__(None, None, None)
                except:
                    pass
        
        # Set final result
        if history:
            final_summary = f"Hybrid execution completed: {len(history)} steps taken"
            if self.output_model_schema:
                # Try to extract structured data if required
                final_summary += " with structured data extraction"
            history.final_result = final_summary
        
        return history
    
    async def _get_current_page_info(self) -> Dict[str, Any]:
        """Get current page information."""
        try:
            if not self.browser_session.context or not self.browser_session.context.pages:
                return None
            
            page = self.browser_session.context.pages[0]
            
            return {
                "url": page.url,
                "title": await page.title(),
                "viewport": page.viewport_size,
                "scroll_y": await page.evaluate("window.pageYOffset") if page.url != "about:blank" else 0
            }
        except Exception as e:
            print_hybrid_status(f"Error getting page info: {e}")
            return None
    
    async def _take_screenshot(self) -> bytes:
        """Take screenshot of current page."""
        try:
            if not self.browser_session.context or not self.browser_session.context.pages:
                return None
            
            page = self.browser_session.context.pages[0]
            screenshot_data = await page.screenshot(type="png", full_page=False)
            return screenshot_data
        except Exception as e:
            print_hybrid_status(f"Error taking screenshot: {e}")
            return None
    
    async def _execute_hybrid_action(self, action: Action) -> Dict[str, str]:
        """Execute a hybrid action and return result."""
        try:
            if not self.browser_session.context or not self.browser_session.context.pages:
                return {"status": "fail", "message": "No active page"}
            
            page = self.browser_session.context.pages[0]
            
            if action.op == "navigate":
                await page.goto(action.value)
                return {"status": "ok", "message": f"Navigated to {action.value}"}
            
            elif action.op == "click":
                if action.target and action.target.selector_hint:
                    selector = self._convert_hybrid_selector_hint(action.target.selector_hint)
                    await page.click(selector, timeout=5000)
                    return {"status": "ok", "message": f"Clicked {selector}"}
                else:
                    return {"status": "fail", "message": "No target specified for click"}
            
            elif action.op == "type":
                if action.target and action.target.selector_hint and action.value:
                    selector = self._convert_hybrid_selector_hint(action.target.selector_hint)
                    await page.fill(selector, action.value)
                    return {"status": "ok", "message": f"Typed '{action.value}' into {selector}"}
                else:
                    return {"status": "fail", "message": "Missing target or value for type action"}
            
            elif action.op == "scroll":
                if action.value == "down":
                    await page.keyboard.press("Page_Down")
                elif action.value == "up":
                    await page.keyboard.press("Page_Up")
                else:
                    scroll_amount = int(action.value) if action.value and action.value.isdigit() else 500
                    await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
                return {"status": "ok", "message": f"Scrolled {action.value or 'down'}"}
            
            elif action.op == "wait":
                wait_ms = int(action.value) if action.value and action.value.isdigit() else 1000
                await asyncio.sleep(wait_ms / 1000)
                return {"status": "ok", "message": f"Waited {wait_ms}ms"}
            
            else:
                return {"status": "fail", "message": f"Unsupported action: {action.op}"}
        
        except Exception as e:
            print_hybrid_status(f"Error executing {action.op}: {e}")
            return {"status": "fail", "message": f"Execution error: {str(e)}"}
    
    def _convert_hybrid_selector_hint(self, selector_hint: str) -> str:
        """Convert hybrid selector hint to Playwright selector."""
        
        # Handle contains syntax
        if ":contains(" in selector_hint:
            parts = selector_hint.split(":contains(")
            element_type = parts[0]
            text_part = parts[1].rstrip(")")
            text = text_part.strip("'\"")
            return f"{element_type}:has-text('{text}')"
        
        # Handle aria-label
        elif "[aria-label=" in selector_hint:
            return selector_hint
        
        # Handle positional hints
        elif " near " in selector_hint:
            return selector_hint.split(" near ")[0]
        
        else:
            return selector_hint
    
    def _create_history_entry(self, step_number: int, action: Action, result: Dict[str, str], reasoning: str):
        """Create a history entry for the action."""
        class HistoryEntry:
            def __init__(self, step, action, result, reasoning):
                self.step_number = step
                self.action_type = action.op
                self.result = result["message"]
                self.error = None if result["status"] == "ok" else result["message"]
                self.reasoning = reasoning
        
        return HistoryEntry(step_number, action, result, reasoning)
    
    def _create_error_entry(self, step_number: int, error_message: str):
        """Create an error history entry."""
        class ErrorEntry:
            def __init__(self, step, error):
                self.step_number = step
                self.action_type = "error"
                self.result = "Failed"
                self.error = error
        
        return ErrorEntry(step_number, error_message)
    
    def _is_task_complete(self, result: Dict[str, str], step_count: int) -> bool:
        """Determine if the task is complete."""
        
        # Check for completion keywords
        completion_words = ["complete", "done", "finished", "success", "successfully"]
        message_lower = result["message"].lower()
        
        if any(word in message_lower for word in completion_words):
            return True
        
        # For simple tasks, consider complete after a few successful actions
        if result["status"] == "ok" and step_count >= 3:
            return True
        
        return False

# ----------------------------
# Enhanced run_query function with Hybrid Integration
# ----------------------------
async def run_query(query: str, keep_browser_open: bool = True) -> bool:
    print_status("Initializing hybrid execution flow...", Colors.YELLOW)
    
    # Check hybrid prerequisites
    if USE_HYBRID_VISION:
        ollama_available = await check_ollama_availability()
        if ollama_available:
            print_hybrid_status("Hybrid vision mode enabled - local MiniCPM-V + cloud Gemini")
        else:
            print_hybrid_status("Ollama not available, falling back to standard mode", used_local=False)
    else:
        print_hybrid_status("Hybrid vision disabled in config", used_local=False)
    
    # Initialize models
    planner_llm = ChatOpenAI(model=PLANNER_MODEL)
    executor_llm = ChatOpenAI(model=EXECUTOR_MODEL)
    
    # Track hybrid statistics
    hybrid_stats = {
        "local_actions": 0,
        "cloud_actions": 0,
        "total_actions": 0,
        "local_success_rate": 0.0,
        "ollama_available": await check_ollama_availability() if USE_HYBRID_VISION else False
    }
    
    try:
        # Step 1: Task Classification (unchanged)
        print_status("Step 1: Classifying task type", Colors.BLUE)
        task_type = await TaskRouter.classify_task(planner_llm, query)
        print_status(f"Task classified: {task_type.category} ({task_type.complexity}, {task_type.estimated_steps} steps)", Colors.GREEN)
        
        # Step 2: Generate Plan (unchanged)
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
        
        # Step 3: Browser Setup (unchanged)
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
        
        # Step 4: Configure Task-Specific Agent (modified for hybrid)
        print_status("Step 4: Configuring hybrid agent for task type", Colors.BLUE)
        
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
        
        # Create hybrid agent wrapper instead of standard agent
        print_hybrid_status("Creating hybrid agent wrapper")
        hybrid_agent = HybridAgentWrapper(
            task=task_description,
            llm=executor_llm,
            browser_session=browser_session,
            output_model_schema=output_schema,
            max_steps=min(task_type.estimated_steps + 3, 20),
            max_actions_per_step=3,
            max_failures=3,
            retry_delay=8,
            use_vision=True,
            vision_detail_level="auto",
            save_conversation_path=str(LOGS_DIR / "conversations"),
            extend_system_message=task_system_prompt + " CUSTOM ACTIONS: 'search_web', 'fallback_extract_table' are available."
        )
        
        # Step 5: Execute with hybrid system
        print_status("Step 5: Executing task with hybrid vision", Colors.BLUE)
        robustness = RobustnessManager(strong_model_name=STRONG_MODEL)
        from aug23_hooks import CostManager
        cost_mgr = CostManager(cheap_model_name="gemini-2.5-flash")

        # Execute
        history: AgentHistoryList = await hybrid_agent.run()
        
        # Update hybrid statistics
        hybrid_stats.update(hybrid_agent.hybrid_stats)
        if hybrid_stats["local_actions"] > 0:
            hybrid_stats["local_success_rate"] = (hybrid_stats["local_successes"] / hybrid_stats["local_actions"]) * 100

        # Step 6: Process Results (unchanged)
        print_status("Step 6: Processing results", Colors.BLUE)
        structured_result = process_agent_history_to_structured_result(history, query)

        # Step 7: Final Critique (unchanged)
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
        
        # Step 8: Prepare output with hybrid statistics
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

        # Create result text with hybrid information
        result_text = f"## Hybrid Task Execution Result\n"
        result_text += f"**Task Type:** {task_type.category} ({task_type.complexity})\n"
        result_text += f"**Task Completed:** {structured_result.task_completed}\n"
        result_text += f"**Success Rate:** {structured_result.success_rate:.1f}%\n"
        result_text += f"**Summary:** {structured_result.summary}\n\n"
        
        # Add hybrid vision statistics
        result_text += f"## Hybrid Vision Statistics\n"
        result_text += f"**Hybrid Mode:** {'Enabled' if USE_HYBRID_VISION else 'Disabled'}\n"
        result_text += f"**Ollama Available:** {'Yes' if hybrid_stats['ollama_available'] else 'No'}\n"
        result_text += f"**Local Actions:** {hybrid_stats['local_actions']}\n"
        result_text += f"**Cloud Actions:** {hybrid_stats['cloud_actions']}\n"
        result_text += f"**Total Actions:** {hybrid_stats['total_actions']}\n"
        result_text += f"**Local Success Rate:** {hybrid_stats.get('local_success_rate', 0):.1f}%\n\n"
        
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
        result_text += f"- Vision mode: {'Hybrid (Local + Cloud)' if hybrid_stats['ollama_available'] else 'Standard'}\n"
        if cost_info:
            result_text += f"- Total tokens used: {cost_info['total_tokens']}\n"
            result_text += f"- Estimated cost: ${cost_info['estimated_cost']:.4f}\n"

        log_file = save_query_log(query, result_text, cost_info, hybrid_stats)

        print_status("Query completed!", Colors.GREEN)
        print_status(f"Log saved to: {log_file}", Colors.GREEN)
        if cost_info:
            print_status(f"Estimated cost: ${cost_info['estimated_cost']:.4f}", Colors.YELLOW)

        # Console display with hybrid information
        print(f"\n{Colors.BOLD}Hybrid Task Execution Result:{Colors.END}")
        print("-" * 60)
        print(f"Task Type: {task_type.category} ({task_type.complexity})")
        print(f"Task Completed: {'Yes' if structured_result.task_completed else 'No'}")
        print(f"Success Rate: {structured_result.success_rate:.1f}%")
        print(f"Steps: {structured_result.total_steps}")
        print(f"Summary: {structured_result.summary}")
        
        # Hybrid statistics display
        print(f"\n{Colors.PURPLE}Hybrid Vision Statistics:{Colors.END}")
        print("-" * 30)
        print(f"Mode: {'Hybrid (Local + Cloud)' if hybrid_stats['ollama_available'] else 'Standard Browser-Use'}")
        print(f"Local Actions: {hybrid_stats['local_actions']}")
        print(f"Cloud Actions: {hybrid_stats['cloud_actions']}")
        if hybrid_stats['local_actions'] > 0:
            local_percentage = (hybrid_stats['local_actions'] / hybrid_stats['total_actions']) * 100
            print(f"Local Processing: {local_percentage:.1f}%")
            print(f"Cost Savings: ~{local_percentage * 0.8:.1f}% (estimated)")
        
        if structured_result.final_data:
            print(f"\n{Colors.BOLD}Extracted Data ({structured_result.final_data.data_type}):{Colors.END}")
            print("-" * 30)
            content_str = json.dumps(structured_result.final_data.content, indent=2)
            if len(content_str) > 300:
                print(content_str[:300] + "...\n[Full data saved to log file]")
            else:
                print(content_str)
        print("-" * 60)

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
# CLI with Hybrid Information
# ----------------------------
async def main():
    print_header()

    # Check required API keys
    missing = []
    if not os.getenv('OPENAI_API_KEY'):
        missing.append('OPENAI_API_KEY (planner: gpt-4o-mini, executor: o3)')
    if not os.getenv('ANTHROPIC_API_KEY'):
        missing.append('ANTHROPIC_API_KEY (escalation: claude-3-5-sonnet)')
    
    # Check hybrid-specific requirements
    hybrid_warnings = []
    if USE_HYBRID_VISION:
        if not os.getenv('GOOGLE_API_KEY'):
            hybrid_warnings.append('GOOGLE_API_KEY (required for cloud escalation in hybrid mode)')
        
        ollama_available = await check_ollama_availability()
        if not ollama_available:
            hybrid_warnings.append(f'Ollama with {MINICPM_MODEL} (local vision processing)')
    
    if missing:
        print_status("Missing required API keys:", Colors.RED)
        for k in missing:
            print_status(f"  - {k}", Colors.YELLOW)
        print_status("Add them to your .env and rerun.", Colors.YELLOW)
        return
    
    if hybrid_warnings:
        print_status("Hybrid mode warnings:", Colors.YELLOW)
        for w in hybrid_warnings:
            print_status(f"  - {w}", Colors.YELLOW)
        print_status("Hybrid mode will fall back to standard processing.", Colors.YELLOW)
        print()

    print(f"Logs will be saved to: {LOGS_DIR.absolute()}")
    print(f"Using Chrome profile: {CHROME_PROFILE_DIR}")
    
    # Display hybrid configuration
    print(f"\n{Colors.PURPLE}Hybrid Configuration:{Colors.END}")
    print(f"  * Hybrid Vision: {'Enabled' if USE_HYBRID_VISION else 'Disabled'}")
    if USE_HYBRID_VISION:
        print(f"  * Local Vision: MiniCPM-V 2.6 via Ollama ({OLLAMA_URL})")
        print(f"  * Cloud Planner: Gemini 2.0 Flash")
        print(f"  * Confidence Thresholds: Vision={VISION_CONFIDENCE_THRESHOLD}, Action={LOCAL_ACTION_CONFIDENCE}")
    
    print(f"\n{Colors.GREEN}Task Router Features:{Colors.END}")
    print(f"  * Automatic task classification (data_extraction, research, navigation, transaction)")
    print(f"  * Task-specific system prompts and configurations")
    print(f"  * Structured output only for data extraction tasks")
    print(f"  * Planning only for moderate/complex tasks")
    print(f"  * Hybrid local vision + cloud reasoning for actions\n")

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

        # Daily summary with hybrid statistics
        today = datetime.now().strftime("%Y-%m-%d")
        summary_file = LOGS_DIR / today / "daily_summary.json"
        if summary_file.exists():
            with open(summary_file, 'r', encoding='utf-8') as f:
                summary = json.load(f)
            print(f"\n{Colors.BOLD}Today's Statistics:{Colors.END}")
            print(f"  • Queries run: {len(summary['queries'])}")
            print(f"  • Total cost: ${summary['total_cost']:.4f}")
            if "total_local_actions" in summary and "total_cloud_actions" in summary:
                total_actions = summary["total_local_actions"] + summary["total_cloud_actions"]
                if total_actions > 0:
                    local_pct = (summary["total_local_actions"] / total_actions) * 100
                    print(f"  • Local actions: {summary['total_local_actions']} ({local_pct:.1f}%)")
                    print(f"  • Cloud actions: {summary['total_cloud_actions']}")

        print(f"\n{'-'*70}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Interrupted by user{Colors.END}")
        sys.exit(0)