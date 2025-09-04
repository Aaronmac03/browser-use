#!/usr/bin/env python3
"""
Hybrid Research Workflow Example

This example demonstrates the hybrid architecture in action:
- Cloud planning for research strategy (task decomposition)
- Local execution for all web interactions (privacy preserved)
- Serper API integration for enhanced search capabilities

Use Case: Research emerging AI tools and create a comparative analysis
Perfect for: Market research, competitive analysis, technology scouting
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from hybrid_orchestrator import HybridOrchestrator, HybridConfig
from enhanced_local_llm import LocalLLMConfig  
from cloud_planner import CloudPlannerConfig
from runner import make_browser, build_tools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def hybrid_research_example():
	"""
	Example: Research AI coding assistants and compare their features.
	
	This showcases:
	- Complex multi-step research task
	- Privacy-first web browsing (content stays local)  
	- Cloud strategic planning + local execution
	- Serper API for enhanced search results
	"""
	
	print("\n🔬 HYBRID RESEARCH WORKFLOW")
	print("=" * 50)
	print("Privacy-First AI Research with Hybrid Architecture")
	print("Cloud Plans ➤ Local Executes ➤ Privacy Preserved")
	print()
	
	# Configure hybrid system for research optimization
	config = HybridConfig(
		local_config=LocalLLMConfig(
			max_actions_per_step=10,  # More actions for research tasks
			step_timeout=90,          # Longer timeout for complex tasks
			use_thinking=True         # Enable reasoning for research
		),
		cloud_config=CloudPlannerConfig(
			max_planning_calls=3,  # Strategic planning only
			enable_serper=True     # Enhanced search
		),
		local_first_threshold=0.85  # 85%+ local processing target
	)
	
	orchestrator = HybridOrchestrator(config)
	browser = make_browser()
	tools = build_tools()
	
	# Define research task
	research_task = """
	Research and compare AI coding assistants in 2024. I need:
	
	1. Find information about the top 5 AI coding assistants:
	   - GitHub Copilot
	   - Cursor
	   - Replit AI
	   - Tabnine
	   - Codeium
	
	2. For each assistant, gather:
	   - Pricing model (free vs paid tiers)
	   - Key features and capabilities
	   - Supported languages and IDEs
	   - User reviews or ratings if available
	   - Recent updates or developments
	
	3. Create a comparative analysis highlighting:
	   - Best value for money
	   - Most advanced features
	   - Best for beginners vs professionals
	   - Privacy and data handling approach
	
	Focus on recent information from 2024. Use multiple sources to verify claims.
	"""
	
	print(f"📋 Task: {research_task.strip()[:100]}...")
	print(f"🎯 Target: {config.local_first_threshold:.0%}+ local processing")
	print()
	
	try:
		# Execute hybrid research
		result = await orchestrator.execute_task(
			research_task,
			browser,
			tools,
			include_thinking=True,
			max_actions_per_step=15,
			step_delay=0.5
		)
		
		print("\n📊 RESEARCH RESULTS")
		print("=" * 30)
		print(f"✅ Success: {result['success']}")
		print(f"⏱️  Duration: {result['total_time']:.1f}s")
		print(f"📋 Steps Completed: {len(result['results'])}")
		
		print(f"\n🔒 PRIVACY METRICS")
		print("=" * 30) 
		print(f"☁️  Cloud API Calls: {result['cloud_usage']['planning_calls_used']}/{result['cloud_usage']['max_planning_calls']}")
		print(f"🖥️  Local Processing: {result['local_processing_ratio']:.1%}")
		print(f"🎯 Target Achieved: {'✅' if result['phase_3b_target_met'] else '❌'}")
		print(f"🛡️  Privacy Status: Web content never left your machine")
		
		print(f"\n⚡ PERFORMANCE METRICS") 
		print("=" * 30)
		print(f"🎯 Local Success Rate: {result['local_performance']['success_rate']:.1%}")
		print(f"📈 Avg Step Time: {result['local_performance']['avg_step_time']:.1f}s")
		print(f"🔄 Recovery Attempts: {result['local_performance']['recovery_attempts']}")
		
		# Show insights
		insights = await orchestrator.get_performance_insights()
		print(f"\n🔍 SYSTEM INSIGHTS")
		print("=" * 30)
		print(f"🤖 Local Model: {insights['local_llm_model']}")
		print(f"🛡️  Privacy: {insights['privacy_status']}")
		
		# Print step-by-step results
		if result['results']:
			print(f"\n📝 STEP BREAKDOWN")
			print("=" * 30)
			for i, step_result in enumerate(result['results'], 1):
				status = "✅" if step_result['success'] else "❌"
				duration = step_result.get('duration', 0)
				retries = step_result.get('retries', 0)
				print(f"{status} Step {i}: {duration:.1f}s (retries: {retries})")
		
		return result
		
	except Exception as e:
		logger.error(f"Research workflow failed: {e}")
		return None
		
	finally:
		await browser.kill()
		print(f"\n🏁 Research workflow completed!")

async def quick_comparison_example():
	"""
	Quick example: Compare two specific tools side by side.
	Demonstrates faster hybrid execution for focused tasks.
	"""
	
	print("\n⚡ QUICK COMPARISON WORKFLOW")  
	print("=" * 40)
	print("Fast hybrid execution for focused research")
	print()
	
	# Optimized config for speed
	config = HybridConfig(
		local_config=LocalLLMConfig(
			max_actions_per_step=5,
			step_timeout=45,
			use_thinking=False  # Faster execution
		),
		cloud_config=CloudPlannerConfig(
			max_planning_calls=2,
			enable_serper=True
		),
		step_retry_limit=1,  # Faster execution
		local_first_threshold=0.9
	)
	
	orchestrator = HybridOrchestrator(config)
	browser = make_browser()
	tools = build_tools()
	
	comparison_task = """
	Compare Cursor AI vs GitHub Copilot:
	1. Visit both official websites
	2. Compare pricing (focus on individual developer plans)
	3. List 3 key differences in features
	4. Provide a recommendation for solo developers
	
	Keep it concise and factual.
	"""
	
	try:
		result = await orchestrator.execute_task(
			comparison_task,
			browser, 
			tools,
			max_actions_per_step=10
		)
		
		print(f"⚡ Quick comparison completed in {result['total_time']:.1f}s")
		print(f"🔒 {result['local_processing_ratio']:.0%} local processing maintained")
		
		return result
		
	except Exception as e:
		logger.error(f"Quick comparison failed: {e}")
		return None
		
	finally:
		await browser.kill()

async def main():
	"""Run both research workflow examples."""
	print("🚀 HYBRID RESEARCH EXAMPLES")
	print("Demonstrating privacy-first AI automation")
	print()
	
	# Run comprehensive research example
	await hybrid_research_example()
	
	# Wait between examples
	await asyncio.sleep(2)
	
	# Run quick comparison example  
	await quick_comparison_example()
	
	print("\n🎉 All hybrid research examples completed!")
	print("Your data stayed private - web content never left your machine")

if __name__ == "__main__":
	asyncio.run(main())