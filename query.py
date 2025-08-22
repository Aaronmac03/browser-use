"""
query.py - Interactive Browser-Use Query Tool
Run with: python query.py

Cost tracking uses browser-use's built-in token usage and cost calculation,
which provides accurate real-time pricing for all supported models.
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
import json

from dotenv import load_dotenv
load_dotenv()

from browser_use import Agent, ChatGoogle, BrowserProfile, BrowserSession
from browser_use.agent.views import AgentHistoryList

# Configuration
CHROME_PROFILE_DIR = 'C:/Users/drmcn/.config/browseruse/profiles/default'
LOGS_DIR = Path('browser_queries')
LOGS_DIR.mkdir(exist_ok=True)

# Colors for terminal output (optional, but nice)
class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header():
    """Print a nice header for the tool"""
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}🤖 Browser-Use Query Tool{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}\n")

def print_status(message, color=Colors.BLUE):
    """Print status messages with color"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{timestamp}] {message}{Colors.END}")

def save_query_log(query, result, cost_info=None):
    """Save query and results to timestamped log file"""
    timestamp = datetime.now()
    date_str = timestamp.strftime("%Y-%m-%d")
    time_str = timestamp.strftime("%H-%M-%S")
    
    # Create daily log directory
    daily_dir = LOGS_DIR / date_str
    daily_dir.mkdir(exist_ok=True)
    
    # Save detailed log for this query
    log_file = daily_dir / f"{time_str}_query.md"
    
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(f"# Browser Query Log\n")
        f.write(f"**Date:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## Query\n```\n{query}\n```\n\n")
        f.write(f"## Result\n{result}\n\n")
        
        if cost_info:
            f.write(f"## Cost Information\n")
            f.write(f"- Model: {cost_info.get('model', 'N/A')}\n")
            f.write(f"- Total Tokens: {cost_info.get('total_tokens', 'N/A')}\n")
            f.write(f"- Estimated Cost: ${cost_info.get('estimated_cost', 0):.4f}\n")
    
    # Also append to daily summary
    summary_file = daily_dir / "daily_summary.json"
    summary_entry = {
        "time": time_str,
        "query": query[:100] + "..." if len(query) > 100 else query,
        "log_file": str(log_file.name),
        "cost": cost_info.get('estimated_cost', 0) if cost_info else 0
    }
    
    if summary_file.exists():
        with open(summary_file, 'r') as f:
            summary = json.load(f)
    else:
        summary = {"queries": [], "total_cost": 0}
    
    summary["queries"].append(summary_entry)
    summary["total_cost"] += summary_entry["cost"]
    
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    return log_file



async def run_query(query: str, keep_browser_open: bool = True):
    """Execute a browser query and return results"""
    
    print_status("Initializing browser...", Colors.YELLOW)
    
    # Create browser session with your Chrome profile
    browser_profile = BrowserProfile(
        user_data_dir=CHROME_PROFILE_DIR,
        keep_alive=keep_browser_open,
        headless=False  # Show browser window
    )
    browser_session = BrowserSession(browser_profile=browser_profile)
    
    # Initialize model (DEFAULT: Gemini 2.5 Flash)
    model_name = "gemini-2.5-flash"
    llm = ChatGoogle(
        model=model_name,
        api_key=os.getenv('GOOGLE_API_KEY')
    )
    
    # Create agent
    agent = Agent(
        task=query,
        llm=llm,
        browser_session=browser_session,
        max_steps=15  # Limit steps to control costs
    )
    
    print_status("Executing query...", Colors.YELLOW)
    print_status(f"Model: {model_name} | Max steps: 15")
    print()
    
    try:
        # Run the agent
        history: AgentHistoryList = await agent.run()
        
        # Extract results
        final_result = history.final_result()
        if not final_result:
            # Try to get the last extracted content
            for item in reversed(history.history):
                if hasattr(item, 'result') and item.result:
                    for action in item.result:
                        if hasattr(action, 'extracted_content') and action.extracted_content:
                            final_result = action.extracted_content
                            break
                if final_result:
                    break
        
        # Extract cost information from browser-use's built-in usage tracking
        # This provides accurate real-time pricing and token counts
        cost_info = None
        if history.usage:
            cost_info = {
                "model": model_name,
                "prompt_tokens": history.usage.total_prompt_tokens,
                "completion_tokens": history.usage.total_completion_tokens,
                "total_tokens": history.usage.total_tokens,
                "estimated_cost": history.usage.total_cost
            }
        
        # Format result
        result_text = f"## Summary\n{final_result if final_result else 'No specific result extracted'}\n\n"
        result_text += f"## Details\n"
        result_text += f"- Steps taken: {len(history.history)}\n"
        result_text += f"- Model used: {model_name}\n"
        
        if cost_info:
            result_text += f"- Tokens used: {cost_info['total_tokens']}\n"
            result_text += f"- Estimated cost: ${cost_info['estimated_cost']:.4f}\n"
        
        # Save log
        log_file = save_query_log(query, result_text, cost_info)
        
        print_status(f"✅ Query completed!", Colors.GREEN)
        print_status(f"📄 Log saved to: {log_file}", Colors.GREEN)
        
        if cost_info:
            print_status(f"💰 Estimated cost: ${cost_info['estimated_cost']:.4f}", Colors.YELLOW)
        
        # Display result
        print(f"\n{Colors.BOLD}Result:{Colors.END}")
        print("-" * 40)
        if final_result:
            # Truncate if too long for terminal
            if len(final_result) > 500:
                print(final_result[:500] + "...\n[Full result saved to log file]")
            else:
                print(final_result)
        else:
            print("No specific result extracted. Check the log file for details.")
        print("-" * 40)
        
        if keep_browser_open:
            print(f"\n{Colors.YELLOW}Browser is still open. You can interact with it.{Colors.END}")
            input(f"{Colors.BOLD}Press Enter to close the browser and continue...{Colors.END}")
            await browser_session.kill()
        
        return True
        
    except Exception as e:
        print_status(f"❌ Error: {str(e)}", Colors.RED)
        await browser_session.kill()
        return False

async def main():
    """Main interactive loop"""
    print_header()
    
    # Check for API key (environment variable name unchanged) (environment variable name unchanged)
    if not os.getenv('GOOGLE_API_KEY'):
        print_status("❌ Error: GOOGLE_API_KEY not found in environment variables", Colors.RED)
        print_status("Please add it to your .env file", Colors.YELLOW)
        return
    
    print(f"📁 Logs will be saved to: {LOGS_DIR.absolute()}")
    print(f"🌐 Using Chrome profile: {CHROME_PROFILE_DIR}")
    print()
    
    while True:
        print(f"\n{Colors.BOLD}Enter your query (or 'quit' to exit):{Colors.END}")
        query = input(f"{Colors.GREEN}> {Colors.END}").strip()
        
        if query.lower() in ['quit', 'exit', 'q']:
            print_status("Goodbye! 👋", Colors.BLUE)
            break
        
        if not query:
            print_status("Please enter a valid query", Colors.YELLOW)
            continue
        
        # Ask about browser preference
        print(f"\n{Colors.BOLD}Keep browser open after completion? (y/n, default: y):{Colors.END}")
        keep_open = input(f"{Colors.GREEN}> {Colors.END}").strip().lower() != 'n'
        
        print()
        await run_query(query, keep_browser_open=keep_open)
        
        # Show daily summary
        today = datetime.now().strftime("%Y-%m-%d")
        summary_file = LOGS_DIR / today / "daily_summary.json"
        if summary_file.exists():
            with open(summary_file, 'r') as f:
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
