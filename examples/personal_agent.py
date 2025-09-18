import asyncio
import os
import sys
from typing import Any

# Add the project root to the path so we can import browser_use
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from browser_use import Agent, BrowserSession
from browser_use.llm.google.chat import ChatGoogle
from langchain_community.tools import Tool

# --- Prerequisites ---
# 1. Ensure you have activated the virtual environment:
#    source .venv/bin/activate
#
# 2. Install the required libraries:
#    pip install python-dotenv langchain-community google-search-results psutil bubus openai cdp-use reportlab posthog pyotp google-genai
#
# 3. Create a .env file in the root of this project and add your API keys:
#    SERPER_API_KEY="your_serper_api_key"
#    GOOGLE_API_KEY="your_google_api_key"
# ---------------------

# Load environment variables from .env file
load_dotenv()

# --- Check for Credentials ---
use_vertex = "GOOGLE_APPLICATION_CREDENTIALS" in os.environ
if use_vertex:
    if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
        raise ValueError("GOOGLE_CLOUD_PROJECT not found in environment variables. Please add it to your .env file.")
    if not os.environ.get("VERTEXAI_LOCATION"):
        raise ValueError("VERTEXAI_LOCATION not found in environment variables. Please add it to your .env file.")
else:
    if not os.environ.get("GOOGLE_API_KEY"):
        raise ValueError("GOOGLE_API_KEY not found in environment variables. Please add it to your .env file.")

if not os.environ.get("SERPER_API_KEY"):
    raise ValueError("SERPER_API_KEY not found in environment variables. Please add it to your .env file.")


# --- 1. Define a Custom Serper Search Tool ---
# We create a custom tool for Serper search using LangChain's Tool class.
# This allows the agent to perform Google searches.

def serper_search(query: str, **kwargs: Any) -> str:
    """
    Performs a Google search using the Serper API.
    
    Args:
        query: The search query.
    
    Returns:
        A string with the search results.
    """
    try:
        from serpapi import GoogleSearch
        
        params = {
            "q": query,
            "api_key": os.environ["SERPER_API_KEY"],
        }
        
        search = GoogleSearch(params)
        results = search.get_dict()
        
        # Process and format the results
        if "organic_results" in results:
            return str(results["organic_results"])
        if "answer_box" in results:
            return str(results["answer_box"])
        if "sports_results" in results:
            return str(results["sports_results"])
        if "knowledge_graph" in results:
            return str(results["knowledge_graph"])
        
        return "No good search result found"
    
    except ImportError:
        return "google-search-results library is not installed. Please run 'pip install google-search-results'."
    except Exception as e:
        return f"An error occurred during search: {e}"

serper_tool = Tool(
    name="google_search",
    description="A tool for performing Google searches and getting up-to-date information.",
    func=serper_search,
)


async def main():
    # --- 2. Instantiate the Language Model ---
    # We'll use ChatGoogle with the Gemini 2.5 Pro model, configured for either
    # an API key or Vertex AI based on your environment variables.
    use_vertex = "GOOGLE_APPLICATION_CREDENTIALS" in os.environ
    if use_vertex:
        llm = ChatGoogle(
            model='gemini-2.5-pro',
            vertexai=True,
            project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
            location=os.environ.get("VERTEXAI_LOCATION")
        )
    else:
        llm = ChatGoogle(model='gemini-2.5-pro', api_key=os.environ.get("GOOGLE_API_KEY"))

    # --- 3. Configure the Browser Session ---
    # This will use your existing Chrome profile, so the agent can access
    # your logged-in sessions and cookies.
    browser_session = BrowserSession(
        user_data_dir="/Users/aaronmcnulty/Library/Application Support/Google/Chrome/Default",
        channel="chrome",
        headless=False  # Run in a visible window to observe the agent
    )

    # --- 4. Create the Agent ---
    # The task is now passed in as a command-line argument.
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("task", help="The task for the agent to perform.")
    args = parser.parse_args()
    task = args.task

    # We combine the LLM, browser, and our custom search tool.
    agent = Agent(
        task=task,
        llm=llm,
        browser=browser_session,
        additional_tools=[serper_tool]
    )

    # --- 5. Define and Run the Task ---
    print(f"Running task: {task}")
    await agent.run()
    print("Task complete.")


if __name__ == '__main__':
    asyncio.run(main())