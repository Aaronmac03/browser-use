"""
Browser Agent: Hybrid Local/Cloud Browser Automation

This is the main entry point for the browser automation system that supports
both local (Ollama) and cloud-based language models for intelligent web interaction.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from config.settings import Settings
from utils.logger import setup_logging


def main():
    """Main entry point for the browser agent application."""
    # Load environment variables
    load_dotenv()
    
    # Initialize settings
    settings = Settings()
    
    # Setup logging
    setup_logging(settings.log_level, settings.log_file)
    logger = logging.getLogger(__name__)
    
    logger.info("Starting Browser Agent...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Default Model: {settings.default_model}")
    
    try:
        # Run the async main function
        asyncio.run(async_main(settings))
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        raise


async def async_main(settings: Settings):
    """Async main function for the browser agent."""
    logger = logging.getLogger(__name__)
    
    # Import components
    from config.models import ModelConfigManager
    from config.profiles import BrowserProfileManager, ProfileType, SecurityLevel
    from models.local_handler import OllamaModelHandler
    from models.cloud_handler import CloudModelManager, BudgetManager, ResponseCache
    from models.model_router import ModelRouter, TaskRequirements, RoutingStrategy
    from utils.serper import SerperAPI, SearchFilters
    from utils.security import SecurityManager
    
    try:
        # Initialize security manager
        logger.info("Initializing security manager...")
        security_manager = SecurityManager()
        
        # Initialize model configuration manager
        logger.info("Initializing model configuration...")
        model_config_manager = ModelConfigManager()
        
        # Initialize browser profile manager
        logger.info("Initializing browser profiles...")
        profile_manager = BrowserProfileManager()
        
        # Create default profiles if they don't exist
        try:
            if not profile_manager.get_profile("default"):
                profile_manager.create_profile(
                    name="default",
                    profile_type=ProfileType.DEFAULT,
                    security_level=SecurityLevel.MEDIUM,
                    description="Default browser profile for general use"
                )
            
            if not profile_manager.get_profile("secure"):
                profile_manager.create_profile(
                    name="secure",
                    profile_type=ProfileType.BANKING,
                    security_level=SecurityLevel.HIGH,
                    description="High-security profile for sensitive operations"
                )
        except Exception as e:
            logger.warning(f"Failed to create default profiles: {e}")
        
        # Initialize local model handler (Ollama)
        local_handler = None
        if settings.ollama_base_url:
            logger.info("Initializing local model handler...")
            local_handler = OllamaModelHandler(
                base_url=settings.ollama_base_url,
                timeout=settings.task_timeout
            )
            
            # Check if Ollama is available
            async with local_handler:
                if await local_handler.is_available():
                    logger.info("Ollama server is available")
                    
                    # List available models
                    models = await local_handler.list_models()
                    logger.info(f"Found {len(models)} local models")
                    for model in models[:3]:  # Show first 3
                        logger.info(f"  - {model.name} ({model.size / (1024**3):.1f}GB)")
                else:
                    logger.warning("Ollama server is not available")
                    local_handler = None
        
        # Initialize cloud model manager
        cloud_manager = None
        api_keys = {}
        
        if settings.openai_api_key:
            api_keys['openai'] = settings.openai_api_key
        if settings.anthropic_api_key:
            api_keys['anthropic'] = settings.anthropic_api_key
        
        if api_keys:
            logger.info("Initializing cloud model manager...")
            budget_manager = BudgetManager(daily_limit=50.0, monthly_limit=500.0)
            cache = ResponseCache(max_age_hours=24)
            
            cloud_manager = CloudModelManager(
                openai_api_key=api_keys.get('openai'),
                anthropic_api_key=api_keys.get('anthropic'),
                budget_manager=budget_manager,
                cache=cache
            )
            logger.info(f"Initialized cloud handlers for: {list(api_keys.keys())}")
        
        # Initialize model router
        logger.info("Initializing model router...")
        model_router = ModelRouter(
            model_config_manager=model_config_manager,
            local_handler=local_handler,
            cloud_manager=cloud_manager,
            default_strategy=RoutingStrategy.BALANCED
        )
        
        # Initialize search API
        search_api = None
        if settings.serper_api_key:
            logger.info("Initializing search API...")
            search_api = SerperAPI(api_key=settings.serper_api_key)
        
        logger.info("Browser Agent initialized successfully")
        
        # Demonstrate basic functionality
        await demonstrate_functionality(
            model_router, search_api, profile_manager, security_manager, logger
        )
        
        # Demonstrate workflow functionality
        await demonstrate_workflows(
            model_router, profile_manager, security_manager, logger
        )
        
        # Cleanup
        if cloud_manager:
            await cloud_manager.close()
        if local_handler:
            await local_handler.close()
        if search_api:
            await search_api.close()
        
        security_manager.close()
        
    except Exception as e:
        logger.error(f"Failed to initialize browser agent: {e}")
        raise


async def demonstrate_functionality(
    model_router: "ModelRouter",
    search_api: Optional["SerperAPI"],
    profile_manager: "BrowserProfileManager",
    security_manager: "SecurityManager",
    logger
):
    """Demonstrate the core functionality of the browser agent."""
    logger.info("=== Browser Agent Functionality Demo ===")
    
    # 1. Model Selection Demo
    logger.info("1. Testing model selection...")
    try:
        from models.model_router import TaskRequirements
        
        # Test planning task
        planning_task = TaskRequirements(
            is_planning_task=True,
            requires_vision=False
        )
        
        selected_model = await model_router.select_model(planning_task)
        logger.info(f"Selected model for planning task: {selected_model.name} ({selected_model.provider.value})")
        
        # Test execution task with vision
        execution_task = TaskRequirements(
            requires_vision=True,
            requires_code=True
        )
        
        try:
            selected_model = await model_router.select_model(execution_task)
            logger.info(f"Selected model for execution task: {selected_model.name}")
        except Exception as e:
            logger.info(f"No suitable model found for execution task: {e}")
        
    except Exception as e:
        logger.warning(f"Model selection demo failed: {e}")
    
    # 2. Search API Demo
    if search_api:
        logger.info("2. Testing search functionality...")
        try:
            async with search_api:
                # Perform a simple web search
                from utils.serper import SearchFilters
                
                filters = SearchFilters(num_results=3)
                response = await search_api.web_search("browser automation python", filters)
                
                logger.info(f"Search returned {len(response.results)} results")
                for i, result in enumerate(response.results[:2]):
                    logger.info(f"  {i+1}. {result.title[:50]}...")
                
                # Extract key information
                key_info = search_api.extract_key_information(response, max_results=2)
                if key_info["summary"]:
                    logger.info(f"Summary: {key_info['summary'][:100]}...")
        
        except Exception as e:
            logger.warning(f"Search demo failed: {e}")
    else:
        logger.info("2. Search API not configured (no Serper API key)")
    
    # 3. Browser Profiles Demo
    logger.info("3. Testing browser profiles...")
    try:
        profiles = profile_manager.list_profiles()
        logger.info(f"Available profiles: {[p.name for p in profiles]}")
        
        # Get configuration for default profile
        default_profile = profile_manager.get_profile("default")
        if default_profile:
            config = profile_manager.get_browser_config("default")
            logger.info(f"Default profile config: headless={config.get('headless')}, args count={len(config.get('args', []))}")
    
    except Exception as e:
        logger.warning(f"Browser profiles demo failed: {e}")
    
    # 4. Security Demo
    logger.info("4. Testing security features...")
    try:
        # Test URL validation
        test_urls = [
            "https://google.com",
            "https://suspicious-site.tk",
            "https://github.com/microsoft/playwright"
        ]
        
        for url in test_urls:
            validation = security_manager.validate_and_log_url_access(
                url, user_id="demo_user", session_id="demo_session"
            )
            logger.info(f"URL {url}: {validation['recommendation']} (risk: {validation['risk_score']:.2f})")
    
    except Exception as e:
        logger.warning(f"Security demo failed: {e}")
    
    # 5. Show statistics
    logger.info("5. System statistics...")
    try:
        routing_stats = model_router.get_routing_stats()
        if routing_stats.get("total_routing_decisions", 0) > 0:
            logger.info(f"Model routing decisions: {routing_stats['total_routing_decisions']}")
        
        if search_api:
            search_stats = search_api.get_api_stats()
            logger.info(f"Search API requests: {search_stats['total_requests']}")
    
    except Exception as e:
        logger.warning(f"Statistics demo failed: {e}")
    
    logger.info("=== Demo completed ===")
    logger.info("Browser Agent is ready to accept tasks")


async def demonstrate_workflows(
    model_router: "ModelRouter",
    profile_manager: "BrowserProfileManager", 
    security_manager: "SecurityManager",
    logger
):
    """Demonstrate the workflow functionality of the browser agent."""
    logger.info("=== Browser Agent Workflow Demo ===")
    
    try:
        from datetime import datetime, timedelta, date
        from workflows.workflow_base import WorkflowConfig, WorkflowPriority
        from tasks.gmail import GmailWorkflow, EmailSearchCriteria
        from tasks.calendar import CalendarWorkflow, CalendarEvent
        from tasks.forms import FormHandler, create_contact_form
        from workflows.email_calendar import EmailCalendarWorkflow
        
        # 1. Gmail Workflow Demo
        logger.info("1. Testing Gmail workflow...")
        try:
            gmail_config = WorkflowConfig(
                workflow_id="demo_gmail_001",
                name="Gmail Demo Workflow",
                description="Demonstrate Gmail automation capabilities",
                priority=WorkflowPriority.NORMAL,
                browser_profile="default",
                timeout=300.0
            )
            
            gmail_workflow = GmailWorkflow(
                gmail_config, model_router, profile_manager, security_manager
            )
            
            # Test workflow validation
            prerequisites_valid = await gmail_workflow.validate_prerequisites()
            logger.info(f"Gmail workflow prerequisites valid: {prerequisites_valid}")
            
            # Test email search criteria
            search_criteria = EmailSearchCriteria(
                query="important",
                is_unread=True,
                max_results=5
            )
            logger.info(f"Created email search criteria: {search_criteria.query}")
            
        except Exception as e:
            logger.warning(f"Gmail workflow demo failed: {e}")
        
        # 2. Calendar Workflow Demo
        logger.info("2. Testing Calendar workflow...")
        try:
            calendar_config = WorkflowConfig(
                workflow_id="demo_calendar_001",
                name="Calendar Demo Workflow", 
                description="Demonstrate Calendar automation capabilities",
                priority=WorkflowPriority.NORMAL,
                browser_profile="default",
                timeout=300.0
            )
            
            calendar_workflow = CalendarWorkflow(
                calendar_config, model_router, profile_manager, security_manager
            )
            
            # Test workflow validation
            prerequisites_valid = await calendar_workflow.validate_prerequisites()
            logger.info(f"Calendar workflow prerequisites valid: {prerequisites_valid}")
            
            # Test event creation
            demo_event = CalendarEvent(
                title="Demo Meeting",
                start_time=datetime.now() + timedelta(hours=1),
                end_time=datetime.now() + timedelta(hours=2),
                description="Demonstration calendar event",
                attendees=["demo@example.com"]
            )
            logger.info(f"Created demo calendar event: {demo_event.title}")
            
        except Exception as e:
            logger.warning(f"Calendar workflow demo failed: {e}")
        
        # 3. Form Handler Demo
        logger.info("3. Testing Form handler...")
        try:
            form_config = WorkflowConfig(
                workflow_id="demo_form_001",
                name="Form Demo Workflow",
                description="Demonstrate form automation capabilities", 
                priority=WorkflowPriority.NORMAL,
                browser_profile="default",
                timeout=180.0
            )
            
            # Create a contact form definition
            contact_form = create_contact_form()
            
            form_handler = FormHandler(
                form_config, model_router, profile_manager, security_manager, contact_form
            )
            
            # Test workflow validation
            prerequisites_valid = await form_handler.validate_prerequisites()
            logger.info(f"Form handler prerequisites valid: {prerequisites_valid}")
            
            # Test form data validation
            test_form_data = {
                "first_name": "John",
                "last_name": "Doe", 
                "email": "john.doe@example.com",
                "phone": "+1-555-123-4567",
                "subject": "Demo Contact",
                "message": "This is a demonstration message for the contact form."
            }
            
            validation_errors = form_handler.validator.validate_form_data(contact_form, test_form_data)
            logger.info(f"Form validation errors: {len(validation_errors)}")
            
        except Exception as e:
            logger.warning(f"Form handler demo failed: {e}")
        
        # 4. Combined Email-Calendar Workflow Demo
        logger.info("4. Testing combined Email-Calendar workflow...")
        try:
            combined_config = WorkflowConfig(
                workflow_id="demo_combined_001",
                name="Email-Calendar Demo Workflow",
                description="Demonstrate combined email and calendar automation",
                priority=WorkflowPriority.HIGH,
                browser_profile="default",
                timeout=600.0,
                continue_on_error=True
            )
            
            email_calendar_workflow = EmailCalendarWorkflow(
                combined_config, model_router, profile_manager, security_manager
            )
            
            # Test workflow validation
            prerequisites_valid = await email_calendar_workflow.validate_prerequisites()
            logger.info(f"Combined workflow prerequisites valid: {prerequisites_valid}")
            
            logger.info("Combined workflow supports:")
            logger.info("  - Processing meeting invitations from email")
            logger.info("  - Scheduling meetings from email requests")
            logger.info("  - Syncing calendar events to email reminders")
            
        except Exception as e:
            logger.warning(f"Combined workflow demo failed: {e}")
        
        # 5. Workflow Progress and Management Demo
        logger.info("5. Testing workflow management features...")
        try:
            # Demonstrate workflow progress tracking
            if 'gmail_workflow' in locals():
                progress = gmail_workflow.get_progress()
                logger.info(f"Gmail workflow progress: {progress['progress_percentage']:.1f}%")
                logger.info(f"Workflow status: {progress['status']}")
            
            # Demonstrate workflow configuration options
            logger.info("Available workflow configuration options:")
            logger.info("  - Priority levels: LOW, NORMAL, HIGH, CRITICAL")
            logger.info("  - Execution modes: Sequential, Parallel")
            logger.info("  - Error handling: Continue on error, Stop on error")
            logger.info("  - Security levels: Browser profile based")
            logger.info("  - Timeout management: Per-step and overall timeouts")
            logger.info("  - Retry mechanisms: Configurable retry counts with exponential backoff")
            
        except Exception as e:
            logger.warning(f"Workflow management demo failed: {e}")
        
        logger.info("=== Workflow Demo completed ===")
        logger.info("Workflow system features:")
        logger.info("  ✓ Base workflow abstraction with lifecycle management")
        logger.info("  ✓ Gmail workflow for email automation")
        logger.info("  ✓ Calendar workflow for event management")
        logger.info("  ✓ Generic form handler for web forms")
        logger.info("  ✓ Combined workflows for complex scenarios")
        logger.info("  ✓ Error handling and recovery mechanisms")
        logger.info("  ✓ Security validation and audit logging")
        logger.info("  ✓ Progress tracking and workflow management")
        
    except Exception as e:
        logger.error(f"Workflow demonstration failed: {e}")


if __name__ == "__main__":
    main()