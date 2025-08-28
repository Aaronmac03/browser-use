"""
Tasks package for browser-agent.

This package contains task-specific workflow implementations for common
web automation scenarios like email, calendar, and form handling.
"""

from .gmail import (
    GmailWorkflow,
    EmailMessage,
    EmailSearchCriteria,
    GmailDOMHelper
)

from .calendar import (
    CalendarWorkflow,
    CalendarEvent,
    CalendarSearchCriteria,
    DateTimeParser,
    EventStatus,
    EventVisibility,
    RecurrenceType
)

from .forms import (
    FormHandler,
    FormDefinition,
    FormField,
    FormSection,
    FormSubmissionResult,
    FormValidator,
    FieldType,
    ValidationRule,
    create_contact_form,
    create_registration_form
)

__all__ = [
    # Gmail workflow
    "GmailWorkflow",
    "EmailMessage", 
    "EmailSearchCriteria",
    "GmailDOMHelper",
    
    # Calendar workflow
    "CalendarWorkflow",
    "CalendarEvent",
    "CalendarSearchCriteria", 
    "DateTimeParser",
    "EventStatus",
    "EventVisibility",
    "RecurrenceType",
    
    # Form handling
    "FormHandler",
    "FormDefinition",
    "FormField",
    "FormSection",
    "FormSubmissionResult",
    "FormValidator",
    "FieldType",
    "ValidationRule",
    "create_contact_form",
    "create_registration_form"
]