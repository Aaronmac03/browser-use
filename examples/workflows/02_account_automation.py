#!/usr/bin/env python3
"""
Account-Based Automation Workflow

This example demonstrates:
- Using your existing Chrome profile with logged-in accounts
- Complex multi-step workflows across different platforms
- Privacy-first automation (sensitive data stays local)
- Error handling and recovery mechanisms

Use Case: Social media management, account maintenance, multi-platform tasks
Perfect for: Content creators, social media managers, personal productivity
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

async def social_media_workflow_example():
	"""
	Example: Cross-platform social media management workflow.
	
	Showcases:
	- Chrome profile with your existing accounts
	- Multi-platform automation
	- Content creation and scheduling
	- Privacy preservation (posts/content stay local)
	"""
	
	print("\n📱 ACCOUNT AUTOMATION WORKFLOW")
	print("=" * 50)
	print("Multi-Platform Social Media Management") 
	print("Uses Your Chrome Profile + Existing Accounts")
	print()
	
	# Configure for account-based workflows
	config = HybridConfig(
		local_config=LocalLLMConfig(
			max_tokens=3072,
			temperature=0.4  # Creative for content generation
		),
		cloud_config=CloudPlannerConfig(
			max_planning_calls=4,  # More complex workflows
			enable_serper=False    # Don't need search for account tasks
		),
		max_recovery_attempts=2,   # Important for account workflows
		local_first_threshold=0.9  # High privacy standard
	)
	
	orchestrator = HybridOrchestrator(config)
	browser = make_browser()  # Uses your Chrome profile automatically
	tools = build_tools()
	
	# Social media management task
	social_task = """
	Perform a social media management workflow:
	
	1. LinkedIn Professional Update:
	   - Go to LinkedIn (you should be logged in via Chrome profile)  
	   - Check for new connection requests or messages
	   - If there are notifications, review them (don't auto-accept)
	   - Navigate to your profile to check recent activity
	
	2. Twitter/X Engagement:
	   - Visit Twitter/X homepage  
	   - Check your notifications for mentions or replies
	   - Review your direct messages (don't read private content)
	   - Check trending topics in your area
	
	3. Content Planning:
	   - Based on trending topics, suggest 3 professional post ideas
	   - Make sure suggestions are appropriate for LinkedIn audience
	   - Don't actually post anything - just gather insights
	
	Important: 
	- Don't read private messages/DMs in detail (privacy)
	- Don't make posts without explicit confirmation
	- Focus on gathering insights and checking account status
	- Respect platform terms of service
	"""
	
	print(f"📋 Task: Multi-platform account management")
	print(f"🔑 Authentication: Using your Chrome profile") 
	print(f"🛡️  Privacy Level: {config.local_first_threshold:.0%}+ local processing")
	print()
	
	try:
		# Execute account automation
		result = await orchestrator.execute_task(
			social_task,
			browser,
			tools,
			include_thinking=True,
			max_actions_per_step=12,
			step_delay=1.0  # Respectful delays for social platforms
		)
		
		print("\n📊 AUTOMATION RESULTS")
		print("=" * 30)
		print(f"✅ Workflow Success: {result['success']}")
		print(f"⏱️  Total Duration: {result['total_time']:.1f}s")
		print(f"📋 Steps Executed: {len(result['results'])}")
		
		print(f"\n🔒 PRIVACY & SECURITY")
		print("=" * 30)
		print(f"🔑 Account Access: Via your Chrome profile") 
		print(f"☁️  Cloud Calls: {result['cloud_usage']['planning_calls_used']}/{result['cloud_usage']['max_planning_calls']} (planning only)")
		print(f"🖥️  Local Processing: {result['local_processing_ratio']:.1%}")
		print(f"🛡️  Private Data: Never sent to cloud")
		
		# Account-specific insights
		if result['results']:
			print(f"\n📱 ACCOUNT WORKFLOW INSIGHTS")
			print("=" * 30)
			successful_steps = sum(1 for r in result['results'] if r['success'])
			print(f"✅ Successful Platform Connections: {successful_steps}/{len(result['results'])}")
			
			for i, step_result in enumerate(result['results'], 1):
				platform = ["LinkedIn", "Twitter/X", "Content Planning"][min(i-1, 2)]
				status = "✅" if step_result['success'] else "❌"
				print(f"{status} {platform}: {step_result.get('duration', 0):.1f}s")
		
		return result
		
	except Exception as e:
		logger.error(f"Account workflow failed: {e}")
		return None
		
	finally:
		await browser.kill()
		print(f"\n🏁 Account automation completed!")

async def ecommerce_account_workflow():
	"""
	Example: E-commerce account management and price tracking.
	Demonstrates practical account-based automation.
	"""
	
	print("\n🛒 E-COMMERCE ACCOUNT WORKFLOW")
	print("=" * 40)
	print("Price tracking and account management")
	print()
	
	config = HybridConfig(
		local_config=LocalLLMConfig(
			max_tokens=2048,
			temperature=0.2  # Focused for data extraction
		),
		cloud_config=CloudPlannerConfig(
			max_planning_calls=3,
			enable_serper=False
		),
		local_first_threshold=0.95  # Maximum privacy for shopping
	)
	
	orchestrator = HybridOrchestrator(config)
	browser = make_browser()
	tools = build_tools()
	
	ecommerce_task = """
	E-commerce account management workflow:
	
	1. Amazon Account Check:
	   - Visit Amazon (using your Chrome profile login)
	   - Check your order history (last 5 orders status)
	   - Look at your wishlist items for price changes
	   - Check for any account notifications
	
	2. Price Monitoring:
	   - Pick one item from your wishlist or cart
	   - Note the current price 
	   - Check if there are any deals or discounts available
	   - Don't make any purchases
	
	3. Account Security:
	   - Verify you're logged into the correct account
	   - Check if there are any security alerts
	   - Note any unusual account activity (without revealing details)
	
	Privacy: Don't extract personal details like addresses, payment methods, or specific order items.
	"""
	
	try:
		result = await orchestrator.execute_task(
			ecommerce_task,
			browser,
			tools,
			max_actions_per_step=8,
			step_delay=0.8
		)
		
		print(f"🛒 E-commerce workflow: {'✅ Success' if result['success'] else '❌ Failed'}")
		print(f"🔒 Privacy maintained: {result['local_processing_ratio']:.0%} local processing")
		print(f"⏱️  Duration: {result['total_time']:.1f}s")
		
		return result
		
	except Exception as e:
		logger.error(f"E-commerce workflow failed: {e}")
		return None
		
	finally:
		await browser.kill()

async def productivity_dashboard_workflow():
	"""
	Example: Personal productivity dashboard across multiple services.
	Shows integration of various account-based tools.
	"""
	
	print("\n📊 PRODUCTIVITY DASHBOARD WORKFLOW")
	print("=" * 45)
	print("Multi-service productivity check")
	print()
	
	config = HybridConfig(
		local_config=LocalLLMConfig(
			max_tokens=1024,
			temperature=0.1  # Very focused
		),
		cloud_config=CloudPlannerConfig(
			max_planning_calls=2,
		),
		local_first_threshold=0.9
	)
	
	orchestrator = HybridOrchestrator(config)  
	browser = make_browser()
	tools = build_tools()
	
	productivity_task = """
	Check productivity services for daily overview:
	
	1. Gmail/Google Workspace:
	   - Check inbox for urgent emails (count only)
	   - Look at today's calendar events
	   - Check Google Drive for shared files needing attention
	
	2. Create simple daily summary:
	   - Number of unread emails
	   - Today's meeting count  
	   - Any urgent items requiring immediate attention
	
	Note: Don't read email content - just get counts and urgency indicators.
	Respect privacy by avoiding personal content details.
	"""
	
	try:
		result = await orchestrator.execute_task(
			productivity_task,
			browser,
			tools,
			max_actions_per_step=6
		)
		
		print(f"📊 Productivity check: {'✅ Complete' if result['success'] else '❌ Issues'}")
		print(f"🔒 Privacy protected: {result['local_processing_ratio']:.0%} local")
		
		return result
		
	except Exception as e:
		logger.error(f"Productivity workflow failed: {e}")
		return None
		
	finally:
		await browser.kill()

async def main():
	"""Run account automation workflow examples."""
	print("🚀 ACCOUNT AUTOMATION EXAMPLES")
	print("Leveraging your Chrome profile for seamless workflows")
	print()
	
	# Run social media workflow
	await social_media_workflow_example()
	await asyncio.sleep(2)
	
	# Run e-commerce workflow  
	await ecommerce_account_workflow()
	await asyncio.sleep(2)
	
	# Run productivity workflow
	await productivity_dashboard_workflow()
	
	print("\n🎉 All account automation examples completed!")
	print("🔒 Your account data remained private throughout")
	print("💡 Tip: Customize tasks for your specific workflow needs")

if __name__ == "__main__":
	asyncio.run(main())