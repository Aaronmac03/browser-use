#!/usr/bin/env python3
"""
Workflow Runner

Simple CLI to run hybrid automation workflows:
- Lists available workflows
- Runs selected workflow with proper setup
- Shows performance metrics and privacy stats
- Validates hybrid orchestrator functionality
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

async def run_research_workflow():
	"""Run the hybrid research workflow."""
	from workflows.hybrid_research import main as research_main
	await research_main()

async def run_account_workflow():
	"""Run the account automation workflow."""  
	from workflows.account_automation import main as account_main
	await account_main()

async def run_data_workflow():
	"""Run the data extraction workflow."""
	from workflows.data_extraction import main as data_main
	await data_main()

async def run_quick_test():
	"""Run a quick workflow test for validation."""
	print("QUICK WORKFLOW TEST")
	print("=" * 30)
	print("Testing hybrid orchestrator with simple task")
	print()
	
	from hybrid_orchestrator import HybridOrchestrator, HybridConfig
	from enhanced_local_llm import LocalLLMConfig
	from cloud_planner import CloudPlannerConfig  
	from runner import make_browser, build_tools
	
	# Minimal config for quick test
	config = HybridConfig(
		local_config=LocalLLMConfig(
			max_actions_per_step=5,
			step_timeout=30
		),
		cloud_config=CloudPlannerConfig(
			max_planning_calls=2
		),
		local_first_threshold=0.9
	)
	
	orchestrator = HybridOrchestrator(config)
	browser = make_browser()
	tools = build_tools()
	
	# Simple test task
	test_task = "Visit google.com and search for 'browser automation', then return to the homepage"
	
	try:
		result = await orchestrator.execute_task(test_task, browser, tools)
		
		print(f"Quick test: {'PASSED' if result['success'] else 'FAILED'}")
		print(f"Duration: {result['total_time']:.1f}s")
		print(f"Local processing: {result['local_processing_ratio']:.0%}")
		print(f"Cloud calls: {result['cloud_usage']['planning_calls_used']}")
		
		if result['success']:
			print("Hybrid orchestrator is working correctly!")
		else:
			print("Issues detected - check logs")
		
		return result['success']
		
	except Exception as e:
		print(f"Test failed: {e}")
		return False
		
	finally:
		await browser.kill()

def print_workflows():
	"""Print available workflows."""
	print("AVAILABLE WORKFLOWS")
	print("=" * 30)
	print("1. research   - Hybrid research and competitive analysis")
	print("2. accounts   - Account automation across platforms") 
	print("3. data       - Privacy-first data extraction")
	print("4. test       - Quick validation test")
	print()
	print("Usage: python run_workflow.py <workflow_name>")
	print("Example: python run_workflow.py research")

async def main():
	"""Main workflow runner."""
	parser = argparse.ArgumentParser(description="Run hybrid browser-use workflows")
	parser.add_argument("workflow", nargs="?", default="", 
		help="Workflow to run: research, accounts, data, test, or list")
	
	args = parser.parse_args()
	
	if not args.workflow or args.workflow == "list":
		print_workflows()
		return
	
	workflow_map = {
		"research": run_research_workflow,
		"accounts": run_account_workflow, 
		"data": run_data_workflow,
		"test": run_quick_test
	}
	
	if args.workflow not in workflow_map:
		print(f"Unknown workflow: {args.workflow}")
		print_workflows()
		sys.exit(1)
	
	print("HYBRID BROWSER-USE WORKFLOWS")
	print("=" * 40)
	print("Privacy-first automation with cloud planning + local execution")
	print()
	
	try:
		await workflow_map[args.workflow]()
		print("\nWorkflow execution completed!")
		
	except KeyboardInterrupt:
		print("\nWorkflow interrupted by user")
		
	except Exception as e:
		print(f"\nWorkflow failed: {e}")
		sys.exit(1)

if __name__ == "__main__":
	asyncio.run(main())