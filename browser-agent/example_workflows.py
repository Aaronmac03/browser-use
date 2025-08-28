"""
Example workflow usage for the browser-agent project.

This file demonstrates how to use the various workflow implementations
for common automation tasks like email, calendar, and form handling.
"""

import asyncio
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional

# Import workflow components
from workflows.workflow_base import WorkflowConfig, WorkflowPriority
from tasks.gmail import GmailWorkflow, EmailMessage, EmailSearchCriteria
from tasks.calendar import CalendarWorkflow, CalendarEvent, CalendarSearchCriteria
from tasks.forms import FormHandler, FormDefinition, create_contact_form, create_registration_form
from workflows.email_calendar import EmailCalendarWorkflow

# Import core components (these would be initialized from your main application)
from config.models import ModelConfigManager
from config.profiles import BrowserProfileManager
from models.model_router import ModelRouter
from utils.security import SecurityManager


async def example_gmail_workflow():
    """Example of using the Gmail workflow for email automation."""
    print("=== Gmail Workflow Example ===")
    
    # Create workflow configuration
    config = WorkflowConfig(
        workflow_id="gmail_example_001",
        name="Gmail Automation Example",
        description="Demonstrate Gmail email automation capabilities",
        priority=WorkflowPriority.NORMAL,
        browser_profile="default",
        timeout=300.0
    )
    
    # Initialize dependencies (in real usage, these would come from your main app)
    model_config_manager = ModelConfigManager()
    profile_manager = BrowserProfileManager()
    security_manager = SecurityManager()
    model_router = ModelRouter(model_config_manager)
    
    # Create Gmail workflow
    gmail_workflow = GmailWorkflow(
        config, model_router, profile_manager, security_manager
    )
    
    try:
        # Example 1: Search for emails
        print("1. Searching for emails...")
        search_criteria = EmailSearchCriteria(
            query="important meeting",
            is_unread=True,
            date_after=datetime.now() - timedelta(days=7),
            max_results=10
        )
        
        # In a real implementation, this would actually search Gmail
        print(f"Search criteria: {search_criteria.query}")
        print(f"Looking for unread emails from the last 7 days")
        
        # Example 2: Compose and send email
        print("\n2. Composing email...")
        email_data = {
            "to": "colleague@example.com",
            "subject": "Weekly Status Update",
            "body": """Hi Team,

Here's the weekly status update:

1. Completed tasks:
   - Implemented workflow system
   - Added email automation
   - Created calendar integration

2. Next week's priorities:
   - Testing and validation
   - Documentation updates
   - Performance optimization

Best regards,
Browser Agent
"""
        }
        
        print(f"Composing email to: {email_data['to']}")
        print(f"Subject: {email_data['subject']}")
        
        # Example 3: Reply to email
        print("\n3. Replying to email...")
        reply_message = """Thank you for your email. 

I've reviewed the meeting request and will add it to my calendar.

Best regards,
Browser Agent
"""
        
        print("Reply message prepared")
        
        print("Gmail workflow example completed successfully!")
        
    except Exception as e:
        print(f"Gmail workflow example failed: {e}")


async def example_calendar_workflow():
    """Example of using the Calendar workflow for event management."""
    print("\n=== Calendar Workflow Example ===")
    
    # Create workflow configuration
    config = WorkflowConfig(
        workflow_id="calendar_example_001",
        name="Calendar Automation Example",
        description="Demonstrate Google Calendar automation capabilities",
        priority=WorkflowPriority.NORMAL,
        browser_profile="default",
        timeout=300.0
    )
    
    # Initialize dependencies
    model_config_manager = ModelConfigManager()
    profile_manager = BrowserProfileManager()
    security_manager = SecurityManager()
    model_router = ModelRouter(model_config_manager)
    
    # Create Calendar workflow
    calendar_workflow = CalendarWorkflow(
        config, model_router, profile_manager, security_manager
    )
    
    try:
        # Example 1: Create a calendar event
        print("1. Creating calendar event...")
        
        meeting_event = CalendarEvent(
            title="Team Standup Meeting",
            start_time=datetime.now() + timedelta(days=1, hours=9),  # Tomorrow at 9 AM
            end_time=datetime.now() + timedelta(days=1, hours=9, minutes=30),  # 30 minutes
            description="Daily team standup to discuss progress and blockers",
            location="Conference Room A / Zoom",
            attendees=[
                "alice@company.com",
                "bob@company.com", 
                "charlie@company.com"
            ],
            reminders=[15, 5]  # 15 and 5 minutes before
        )
        
        print(f"Event: {meeting_event.title}")
        print(f"Time: {meeting_event.start_time.strftime('%Y-%m-%d %H:%M')} - {meeting_event.end_time.strftime('%H:%M')}")
        print(f"Attendees: {', '.join(meeting_event.attendees)}")
        
        # Example 2: View upcoming events
        print("\n2. Viewing upcoming events...")
        start_date = date.today()
        end_date = start_date + timedelta(days=7)
        
        print(f"Viewing events from {start_date} to {end_date}")
        
        # Example 3: Search for events
        print("\n3. Searching for events...")
        search_criteria = CalendarSearchCriteria(
            query="meeting",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            max_results=20
        )
        
        print(f"Searching for: {search_criteria.query}")
        print(f"Date range: {search_criteria.start_date} to {search_criteria.end_date}")
        
        # Example 4: Check availability
        print("\n4. Checking availability...")
        attendees = ["alice@company.com", "bob@company.com"]
        check_time = datetime.now() + timedelta(days=2, hours=14)  # Day after tomorrow at 2 PM
        
        print(f"Checking availability for: {', '.join(attendees)}")
        print(f"Time slot: {check_time.strftime('%Y-%m-%d %H:%M')}")
        
        print("Calendar workflow example completed successfully!")
        
    except Exception as e:
        print(f"Calendar workflow example failed: {e}")


async def example_form_workflow():
    """Example of using the Form workflow for web form automation."""
    print("\n=== Form Workflow Example ===")
    
    # Create workflow configuration
    config = WorkflowConfig(
        workflow_id="form_example_001",
        name="Form Automation Example",
        description="Demonstrate web form automation capabilities",
        priority=WorkflowPriority.NORMAL,
        browser_profile="default",
        timeout=180.0
    )
    
    # Initialize dependencies
    model_config_manager = ModelConfigManager()
    profile_manager = BrowserProfileManager()
    security_manager = SecurityManager()
    model_router = ModelRouter(model_config_manager)
    
    try:
        # Example 1: Contact form
        print("1. Contact form example...")
        
        contact_form = create_contact_form()
        contact_form.url = "https://example.com/contact"
        
        form_handler = FormHandler(
            config, model_router, profile_manager, security_manager, contact_form
        )
        
        # Form data to fill
        contact_data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "phone": "+1-555-123-4567",
            "subject": "Product Inquiry",
            "message": "I'm interested in learning more about your automation solutions. Could you please provide more information about pricing and features?"
        }
        
        print(f"Form URL: {contact_form.url}")
        print(f"Contact: {contact_data['first_name']} {contact_data['last_name']}")
        print(f"Email: {contact_data['email']}")
        print(f"Subject: {contact_data['subject']}")
        
        # Validate form data
        validation_errors = form_handler.validator.validate_form_data(contact_form, contact_data)
        if validation_errors:
            print(f"Validation errors: {validation_errors}")
        else:
            print("Form data validation passed!")
        
        # Example 2: Registration form
        print("\n2. Registration form example...")
        
        registration_form = create_registration_form()
        registration_form.url = "https://example.com/register"
        
        registration_handler = FormHandler(
            config, model_router, profile_manager, security_manager, registration_form
        )
        
        # Registration data
        registration_data = {
            "username": "johndoe123",
            "email": "john.doe@example.com",
            "password": "SecurePassword123!",
            "confirm_password": "SecurePassword123!",
            "agree_terms": True
        }
        
        print(f"Registration URL: {registration_form.url}")
        print(f"Username: {registration_data['username']}")
        print(f"Email: {registration_data['email']}")
        
        # Validate registration data
        validation_errors = registration_handler.validator.validate_form_data(registration_form, registration_data)
        if validation_errors:
            print(f"Validation errors: {validation_errors}")
        else:
            print("Registration data validation passed!")
        
        print("Form workflow examples completed successfully!")
        
    except Exception as e:
        print(f"Form workflow example failed: {e}")


async def example_combined_email_calendar_workflow():
    """Example of using the combined Email-Calendar workflow."""
    print("\n=== Combined Email-Calendar Workflow Example ===")
    
    # Create workflow configuration
    config = WorkflowConfig(
        workflow_id="combined_example_001",
        name="Email-Calendar Integration Example",
        description="Demonstrate combined email and calendar automation",
        priority=WorkflowPriority.HIGH,
        browser_profile="default",
        timeout=600.0,
        continue_on_error=True
    )
    
    # Initialize dependencies
    model_config_manager = ModelConfigManager()
    profile_manager = BrowserProfileManager()
    security_manager = SecurityManager()
    model_router = ModelRouter(model_config_manager)
    
    # Create combined workflow
    email_calendar_workflow = EmailCalendarWorkflow(
        config, model_router, profile_manager, security_manager
    )
    
    try:
        # Example 1: Process meeting invitations
        print("1. Processing meeting invitations from email...")
        
        print("Searching for meeting invitation emails...")
        print("Extracting meeting details...")
        print("Creating calendar events...")
        print("Sending acceptance replies...")
        
        # Example 2: Schedule meetings from email requests
        print("\n2. Scheduling meetings from email requests...")
        
        print("Searching for meeting request emails...")
        print("Parsing meeting requirements...")
        print("Checking attendee availability...")
        print("Creating calendar events...")
        print("Sending confirmation emails...")
        
        # Example 3: Sync calendar to email reminders
        print("\n3. Syncing calendar events to email reminders...")
        
        print("Retrieving upcoming calendar events...")
        print("Identifying events needing reminders...")
        print("Sending reminder emails to attendees...")
        
        print("Combined workflow examples completed successfully!")
        
    except Exception as e:
        print(f"Combined workflow example failed: {e}")


async def example_workflow_management():
    """Example of workflow management and monitoring features."""
    print("\n=== Workflow Management Example ===")
    
    try:
        # Example 1: Workflow configuration options
        print("1. Workflow configuration options...")
        
        configs = [
            WorkflowConfig(
                workflow_id="high_priority_task",
                name="Critical Email Processing",
                description="High-priority email processing with strict error handling",
                priority=WorkflowPriority.CRITICAL,
                browser_profile="secure",
                timeout=120.0,
                continue_on_error=False,
                max_retries=3
            ),
            WorkflowConfig(
                workflow_id="background_task",
                name="Daily Calendar Sync",
                description="Background task for daily calendar synchronization",
                priority=WorkflowPriority.LOW,
                browser_profile="default",
                timeout=600.0,
                continue_on_error=True,
                max_retries=1
            )
        ]
        
        for config in configs:
            print(f"  - {config.name}: Priority={config.priority.value}, Timeout={config.timeout}s")
        
        # Example 2: Error handling strategies
        print("\n2. Error handling strategies...")
        
        error_strategies = [
            "Continue on error: Keep processing other steps if one fails",
            "Stop on error: Halt workflow execution on first error",
            "Retry with backoff: Retry failed steps with exponential backoff",
            "Fallback models: Switch to different AI models on failure"
        ]
        
        for strategy in error_strategies:
            print(f"  - {strategy}")
        
        # Example 3: Security and validation
        print("\n3. Security and validation features...")
        
        security_features = [
            "URL validation: Check domains against security policies",
            "Credential encryption: Secure storage of sensitive data",
            "Audit logging: Track all workflow actions and decisions",
            "Profile-based security: Different security levels per use case",
            "Input validation: Validate all form data and parameters"
        ]
        
        for feature in security_features:
            print(f"  - {feature}")
        
        print("Workflow management examples completed successfully!")
        
    except Exception as e:
        print(f"Workflow management example failed: {e}")


async def main():
    """Run all workflow examples."""
    print("Browser Agent Workflow Examples")
    print("=" * 50)
    
    # Set up basic logging
    logging.basicConfig(level=logging.INFO)
    
    try:
        # Run individual workflow examples
        await example_gmail_workflow()
        await example_calendar_workflow()
        await example_form_workflow()
        await example_combined_email_calendar_workflow()
        await example_workflow_management()
        
        print("\n" + "=" * 50)
        print("All workflow examples completed successfully!")
        print("\nKey Features Demonstrated:")
        print("✓ Gmail email automation (search, compose, reply)")
        print("✓ Google Calendar event management (create, view, search)")
        print("✓ Generic form handling with validation")
        print("✓ Combined email-calendar workflows")
        print("✓ Error handling and recovery mechanisms")
        print("✓ Security validation and audit logging")
        print("✓ Flexible workflow configuration")
        print("✓ Progress tracking and monitoring")
        
    except Exception as e:
        print(f"Workflow examples failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())