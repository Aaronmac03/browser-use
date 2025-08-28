# Browser Agent Workflow System

This document provides a comprehensive overview of the workflow system implemented for the Browser Agent project.

## 🏗️ Architecture Overview

The workflow system is built with a modular, extensible architecture that supports complex browser automation tasks:

```
workflows/
├── workflow_base.py      # Base workflow abstraction and lifecycle management
└── email_calendar.py    # Combined email-calendar workflow example

tasks/
├── gmail.py             # Gmail-specific workflow implementation
├── calendar.py          # Google Calendar workflow implementation
└── forms.py             # Generic form handling workflow
```

## 🔧 Core Components

### 1. BaseWorkflow (`workflows/workflow_base.py`)

The foundation of all workflows, providing:

- **Lifecycle Management**: Initialize → Validate → Execute → Cleanup
- **Error Handling**: Configurable retry mechanisms with exponential backoff
- **Progress Tracking**: Real-time progress monitoring and status updates
- **Security Integration**: URL validation and audit logging
- **Model Routing**: Intelligent selection of AI models based on task complexity

**Key Features:**
- Abstract base class for consistent workflow interface
- Configurable timeout and retry policies
- Dependency management between workflow steps
- Comprehensive logging and monitoring
- Security validation at each step

### 2. Gmail Workflow (`tasks/gmail.py`)

Specialized workflow for Gmail automation:

**Capabilities:**
- **Email Search**: Advanced search with filters (date, sender, unread status)
- **Email Composition**: Create and send emails with attachments
- **Email Management**: Reply, forward, delete, archive emails
- **Label Management**: Apply and manage Gmail labels
- **Bulk Operations**: Process multiple emails efficiently

**DOM Helpers:**
- Gmail-specific selectors and interaction patterns
- Intelligent waiting for dynamic content loading
- Error detection and recovery for Gmail interface changes

### 3. Calendar Workflow (`tasks/calendar.py`)

Google Calendar automation workflow:

**Capabilities:**
- **Event Creation**: Create events with attendees, reminders, recurrence
- **Event Management**: View, update, delete calendar events
- **Availability Checking**: Check attendee availability for scheduling
- **Event Search**: Find events by criteria (date, attendee, location)
- **Calendar Views**: Switch between month, week, day, agenda views

**Date/Time Utilities:**
- Natural language date parsing ("tomorrow", "next week")
- Multiple date format support
- Duration parsing and calculation
- Timezone handling

### 4. Form Handler (`tasks/forms.py`)

Generic form automation system:

**Capabilities:**
- **Multi-Field Support**: Text, email, select, checkbox, radio, file upload
- **Validation Engine**: Built-in validation rules with custom validators
- **Form Sections**: Handle complex multi-section forms
- **Error Recovery**: Detect and handle form validation errors
- **Dynamic Forms**: Support for conditional form sections

**Validation Rules:**
- Required field validation
- Format validation (email, phone, URL)
- Length constraints
- Pattern matching (regex)
- Custom validation functions

### 5. Combined Workflows (`workflows/email_calendar.py`)

Example of workflow composition:

**Use Cases:**
- **Meeting Processing**: Extract meeting invites from email → Create calendar events
- **Meeting Scheduling**: Parse email requests → Check availability → Schedule meetings
- **Calendar Sync**: Send email reminders for upcoming events
- **Automated Responses**: Reply to emails based on calendar availability

## 🚀 Usage Examples

### Basic Gmail Workflow

```python
from tasks.gmail import GmailWorkflow, EmailSearchCriteria
from workflows.workflow_base import WorkflowConfig

# Configure workflow
config = WorkflowConfig(
    workflow_id="email_automation_001",
    name="Email Processing",
    description="Process important emails",
    browser_profile="default",
    timeout=300.0
)

# Create workflow
gmail_workflow = GmailWorkflow(config, model_router, profile_manager, security_manager)

# Search for emails
search_criteria = EmailSearchCriteria(
    query="urgent OR important",
    is_unread=True,
    date_after=datetime.now() - timedelta(days=3)
)

emails = await gmail_workflow.search_emails(search_criteria)

# Process each email
for email in emails:
    if "meeting" in email.subject.lower():
        await gmail_workflow.reply_to_email(
            email.message_id,
            "I'll check my calendar and get back to you."
        )
```

### Calendar Event Creation

```python
from tasks.calendar import CalendarWorkflow, CalendarEvent

# Create calendar event
event = CalendarEvent(
    title="Project Review Meeting",
    start_time=datetime(2024, 1, 15, 14, 0),  # 2 PM
    end_time=datetime(2024, 1, 15, 15, 30),   # 3:30 PM
    description="Quarterly project review and planning",
    location="Conference Room A",
    attendees=["alice@company.com", "bob@company.com"],
    reminders=[15, 5]  # 15 and 5 minutes before
)

calendar_workflow = CalendarWorkflow(config, model_router, profile_manager, security_manager)
success = await calendar_workflow.create_event(event)
```

### Form Automation

```python
from tasks.forms import FormHandler, create_contact_form

# Create form definition
contact_form = create_contact_form()
contact_form.url = "https://example.com/contact"

# Form data
form_data = {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@example.com",
    "subject": "Product Inquiry",
    "message": "I'm interested in your automation solutions."
}

# Fill and submit form
form_handler = FormHandler(config, model_router, profile_manager, security_manager, contact_form)
result = await form_handler.fill_form(form_data)

if result.success:
    print("Form submitted successfully!")
else:
    print(f"Form submission failed: {result.errors}")
```

### Combined Email-Calendar Workflow

```python
from workflows.email_calendar import EmailCalendarWorkflow

# Process meeting invitations from email
email_calendar_workflow = EmailCalendarWorkflow(config, model_router, profile_manager, security_manager)

# Automatically process meeting invitations
result = await email_calendar_workflow.process_meeting_invitations(
    days_back=7,
    auto_accept=True
)

print(f"Processed {result.emails_processed} emails")
print(f"Created {result.events_created} calendar events")
```

## ⚙️ Configuration Options

### Workflow Configuration

```python
WorkflowConfig(
    workflow_id="unique_workflow_id",
    name="Human-readable name",
    description="Detailed description",
    priority=WorkflowPriority.NORMAL,  # LOW, NORMAL, HIGH, CRITICAL
    browser_profile="default",         # Browser profile to use
    timeout=300.0,                     # Overall timeout in seconds
    continue_on_error=True,            # Continue if individual steps fail
    max_retries=3,                     # Maximum retry attempts
    retry_delay=1.0,                   # Initial retry delay
    execution_mode=ExecutionMode.SEQUENTIAL  # SEQUENTIAL or PARALLEL
)
```

### Security Profiles

- **Default Profile**: Standard security for general web browsing
- **Secure Profile**: High security for sensitive operations (banking, etc.)
- **Custom Profiles**: Tailored security settings for specific use cases

### Error Handling Strategies

1. **Continue on Error**: Process remaining steps even if some fail
2. **Stop on Error**: Halt execution on first error
3. **Retry with Backoff**: Retry failed steps with exponential backoff
4. **Model Fallback**: Switch to different AI models on failure

## 🔒 Security Features

### URL Validation
- Domain whitelist/blacklist checking
- Suspicious pattern detection
- Risk scoring for unknown domains
- Homograph attack detection

### Credential Management
- Encrypted storage of sensitive data
- Master password protection
- Environment variable integration
- Audit trail for credential access

### Audit Logging
- Comprehensive logging of all workflow actions
- Security event tracking
- Risk assessment and scoring
- Searchable audit logs

## 📊 Monitoring and Analytics

### Progress Tracking
- Real-time progress updates
- Step-by-step execution status
- Time tracking and performance metrics
- Error rate monitoring

### Performance Metrics
- Model response times
- Token usage and costs
- Success/failure rates
- Resource utilization

### System Health
- Budget tracking for API usage
- Cache performance monitoring
- Security violation alerts
- Profile usage analytics

## 🧪 Testing and Validation

### Running Examples

```bash
# Run workflow examples
python3 example_workflows.py

# Run main application with workflow demo
python3 main.py
```

### Test Coverage

The workflow system includes comprehensive testing for:
- Individual workflow components
- Integration between workflows
- Error handling and recovery
- Security validation
- Performance under load

## 🔮 Future Enhancements

### Planned Features
- **Visual Workflow Builder**: Drag-and-drop workflow creation
- **Workflow Templates**: Pre-built workflows for common tasks
- **Advanced Scheduling**: Cron-like scheduling for recurring workflows
- **Workflow Marketplace**: Share and discover community workflows
- **Real-time Collaboration**: Multi-user workflow editing
- **Advanced Analytics**: Machine learning insights on workflow performance

### Integration Opportunities
- **CRM Systems**: Salesforce, HubSpot integration
- **Project Management**: Jira, Asana, Trello workflows
- **Communication**: Slack, Teams, Discord automation
- **Cloud Services**: AWS, Azure, GCP service integration
- **Database Operations**: Automated data entry and extraction

## 📝 Best Practices

### Workflow Design
1. **Single Responsibility**: Each workflow should have a clear, focused purpose
2. **Error Resilience**: Design workflows to handle and recover from failures
3. **Security First**: Always validate inputs and URLs before processing
4. **Performance Optimization**: Use appropriate timeouts and retry strategies
5. **Monitoring**: Include comprehensive logging and progress tracking

### Development Guidelines
1. **Consistent Interface**: Follow the BaseWorkflow pattern for all workflows
2. **Comprehensive Testing**: Test both success and failure scenarios
3. **Documentation**: Document all workflow capabilities and limitations
4. **Security Review**: Regular security audits of workflow implementations
5. **Performance Testing**: Validate workflows under realistic load conditions

## 🤝 Contributing

To add new workflows:

1. **Extend BaseWorkflow**: Create a new class inheriting from BaseWorkflow
2. **Implement Required Methods**: Define validate_prerequisites() and define_steps()
3. **Add DOM Helpers**: Create specialized helpers for target websites
4. **Include Tests**: Add comprehensive test coverage
5. **Update Documentation**: Document new workflow capabilities

The workflow system provides a robust foundation for browser automation that can be extended to support virtually any web-based task while maintaining security, reliability, and performance.