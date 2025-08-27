# hybridtest.py
#!/usr/bin/env python3
import asyncio
import logging
import sys

# Configure logging to handle Unicode properly on Windows
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
	stream=sys.stdout,
	force=True
)

# Set encoding for stdout to handle Unicode
if hasattr(sys.stdout, 'reconfigure'):
	sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from hybrid_agent import HybridAgent

# Your fixed, end-to-end test query
DEFAULT_TASK = (
    "check price and availability of a room at the Omni Hotel in Louisville "
    "for 9/1/25-9/2/25"
)

async def run():
    agent = HybridAgent()

    # Fast sanity check so failures are obvious up front
    if not await agent.vision_analyzer.check_ollama_availability():
        print("Ollama is not running. Start it with:  ollama serve")
        print("And ensure the model is installed:   ollama pull moondream")
        return

    # (Optional) resolve the exact moondream tag for clarity
    try:
        model_tag = await agent.vision_analyzer.resolve_moondream_tag()
        print(f"Using vision model: {model_tag}")
    except Exception:
        pass

    # Run the single fixed task end-to-end
    result = await agent.execute_task(DEFAULT_TASK)

    print("\n" + "="*60)
    print("EXECUTION SUMMARY")
    print(f"Task: {result.get('task')}")
    print(f"Completed: {result.get('completed')}")
    print(f"Steps Executed: {result.get('steps_executed')}")
    print(f"Escalation Level: {result.get('escalation_level')}")
    if result.get('final_screenshot'):
        print(f"Final Screenshot: {result['final_screenshot']}")
    if result.get('summary'):
        print(f"Summary: {result['summary']}")
    print("="*60)

    # Tidy up
    try:
        if agent.browser_session:
            await agent.browser_session.kill()
    except Exception:
        pass

if __name__ == "__main__":
    asyncio.run(run())
