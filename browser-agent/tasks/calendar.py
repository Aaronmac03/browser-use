"""
Google Calendar workflow implementation for calendar automation tasks.

This module provides specialized workflows for Google Calendar interactions including
viewing, creating, and modifying events, with date/time parsing utilities.
"""

import re
import asyncio
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from datetime import datetime, timedelta, date, time
from enum import Enum

from workflows.workflow_base import (
    BaseWorkflow, WorkflowStep, WorkflowConfig, 
    TaskComplexity, SecurityError
)
from models.model_router import ModelRouter
from config.profiles import BrowserProfileManager
from utils.security import SecurityManager


class EventStatus(str, Enum):
    """Calendar event status."""
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"


class EventVisibility(str, Enum):
    """Calendar event visibility."""
    DEFAULT = "default"
    PUBLIC = "public"
    PRIVATE = "private"
    CONFIDENTIAL = "confidential"


class RecurrenceType(str, Enum):
    """Event recurrence types."""
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    CUSTOM = "custom"


@dataclass
class CalendarEvent:
    """Represents a calendar event."""
    title: str
    start_time: datetime
    end_time: datetime
    description: Optional[str] = None
    location: Optional[str] = None
    attendees: List[str] = None
    event_id: Optional[str] = None
    calendar_id: Optional[str] = None
    status: EventStatus = EventStatus.CONFIRMED
    visibility: EventVisibility = EventVisibility.DEFAULT
    recurrence: RecurrenceType = RecurrenceType.NONE
    recurrence_rule: Optional[str] = None
    reminders: List[int] = None  # Minutes before event
    all_day: bool = False
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None
    creator: Optional[str] = None
    organizer: Optional[str] = None

    def __post_init__(self):
        if self.attendees is None:
            self.attendees = []
        if self.reminders is None:
            self.reminders = [10]  # Default 10 minutes reminder


@dataclass
class CalendarSearchCriteria:
    """Search criteria for calendar events."""
    query: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    calendar_ids: Optional[List[str]] = None
    attendee: Optional[str] = None
    location: Optional[str] = None
    status: Optional[EventStatus] = None
    max_results: int = 50


class DateTimeParser:
    """Utility class for parsing date and time strings."""
    
    # Common date formats
    DATE_FORMATS = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%Y-%m-%d %H:%M",
        "%m/%d/%Y %H:%M",
        "%B %d, %Y at %I:%M %p",
        "%b %d, %Y at %I:%M %p"
    ]
    
    # Time formats
    TIME_FORMATS = [
        "%H:%M",
        "%I:%M %p",
        "%H:%M:%S",
        "%I:%M:%S %p"
    ]
    
    # Relative date patterns
    RELATIVE_PATTERNS = {
        r'today': lambda: date.today(),
        r'tomorrow': lambda: date.today() + timedelta(days=1),
        r'yesterday': lambda: date.today() - timedelta(days=1),
        r'next week': lambda: date.today() + timedelta(weeks=1),
        r'next month': lambda: date.today() + timedelta(days=30),
        r'in (\d+) days?': lambda m: date.today() + timedelta(days=int(m.group(1))),
        r'in (\d+) weeks?': lambda m: date.today() + timedelta(weeks=int(m.group(1))),
        r'(\d+) days? ago': lambda m: date.today() - timedelta(days=int(m.group(1))),
    }
    
    @classmethod
    def parse_date(cls, date_str: str) -> Optional[date]:
        """Parse a date string into a date object."""
        if not date_str:
            return None
        
        date_str = date_str.strip().lower()
        
        # Try relative patterns first
        for pattern, func in cls.RELATIVE_PATTERNS.items():
            match = re.search(pattern, date_str)
            if match:
                try:
                    return func() if callable(func) else func(match)
                except:
                    continue
        
        # Try standard formats
        for fmt in cls.DATE_FORMATS:
            try:
                parsed = datetime.strptime(date_str, fmt)
                return parsed.date()
            except ValueError:
                continue
        
        return None
    
    @classmethod
    def parse_time(cls, time_str: str) -> Optional[time]:
        """Parse a time string into a time object."""
        if not time_str:
            return None
        
        time_str = time_str.strip()
        
        for fmt in cls.TIME_FORMATS:
            try:
                parsed = datetime.strptime(time_str, fmt)
                return parsed.time()
            except ValueError:
                continue
        
        return None
    
    @classmethod
    def parse_datetime(cls, datetime_str: str) -> Optional[datetime]:
        """Parse a datetime string into a datetime object."""
        if not datetime_str:
            return None
        
        # Try to parse as full datetime first
        for fmt in cls.DATE_FORMATS:
            try:
                return datetime.strptime(datetime_str, fmt)
            except ValueError:
                continue
        
        # Try to split date and time parts
        parts = datetime_str.split(' at ')
        if len(parts) == 2:
            date_part, time_part = parts
        else:
            # Try other separators
            for sep in [' ', 'T']:
                if sep in datetime_str:
                    parts = datetime_str.split(sep, 1)
                    if len(parts) == 2:
                        date_part, time_part = parts
                        break
            else:
                return None
        
        parsed_date = cls.parse_date(date_part)
        parsed_time = cls.parse_time(time_part)
        
        if parsed_date and parsed_time:
            return datetime.combine(parsed_date, parsed_time)
        
        return None
    
    @classmethod
    def parse_duration(cls, duration_str: str) -> Optional[timedelta]:
        """Parse a duration string into a timedelta object."""
        if not duration_str:
            return None
        
        duration_str = duration_str.lower().strip()
        
        # Pattern for duration parsing
        patterns = {
            r'(\d+)\s*hours?': lambda m: timedelta(hours=int(m.group(1))),
            r'(\d+)\s*minutes?': lambda m: timedelta(minutes=int(m.group(1))),
            r'(\d+)\s*days?': lambda m: timedelta(days=int(m.group(1))),
            r'(\d+)h\s*(\d+)m': lambda m: timedelta(hours=int(m.group(1)), minutes=int(m.group(2))),
            r'(\d+):(\d+)': lambda m: timedelta(hours=int(m.group(1)), minutes=int(m.group(2))),
        }
        
        for pattern, func in patterns.items():
            match = re.search(pattern, duration_str)
            if match:
                try:
                    return func(match)
                except:
                    continue
        
        return None


class CalendarDOMHelper:
    """Helper class for Google Calendar DOM interactions."""
    
    # Google Calendar selectors
    SELECTORS = {
        # Navigation
        "create_button": "div[data-target='create']",
        "today_button": "button[aria-label='Today']",
        "view_selector": "div[role='tablist']",
        "month_view": "button[aria-label='Month']",
        "week_view": "button[aria-label='Week']",
        "day_view": "button[aria-label='Day']",
        "agenda_view": "button[aria-label='Agenda']",
        
        # Calendar grid
        "calendar_grid": "div[role='grid']",
        "event_element": "div[data-eventid]",
        "time_slot": "div[role='gridcell']",
        "date_cell": "td[role='gridcell']",
        
        # Event creation/editing
        "event_title": "input[aria-label='Title']",
        "event_location": "input[aria-label='Location']",
        "event_description": "textarea[aria-label='Description']",
        "start_date": "input[aria-label='Start date']",
        "start_time": "input[aria-label='Start time']",
        "end_date": "input[aria-label='End date']",
        "end_time": "input[aria-label='End time']",
        "all_day_toggle": "input[aria-label='All day']",
        "save_button": "button[aria-label='Save']",
        "delete_button": "button[aria-label='Delete']",
        
        # Attendees
        "add_guests": "input[aria-label='Add guests']",
        "guest_list": "div[role='listbox']",
        
        # Reminders
        "add_notification": "button[aria-label='Add notification']",
        "notification_time": "select[aria-label='Notification time']",
        
        # Search
        "search_box": "input[aria-label='Search']",
        "search_button": "button[aria-label='Search']",
    }
    
    @staticmethod
    def format_event_creation_task(event: CalendarEvent) -> str:
        """Generate task prompt for creating a calendar event."""
        task_parts = [
            "Create a new calendar event in Google Calendar with the following details:",
            f"Title: {event.title}",
            f"Start: {event.start_time.strftime('%Y-%m-%d %H:%M')}",
            f"End: {event.end_time.strftime('%Y-%m-%d %H:%M')}"
        ]
        
        if event.description:
            task_parts.append(f"Description: {event.description}")
        
        if event.location:
            task_parts.append(f"Location: {event.location}")
        
        if event.attendees:
            task_parts.append(f"Attendees: {', '.join(event.attendees)}")
        
        if event.all_day:
            task_parts.append("All day: Yes")
        
        if event.reminders:
            reminder_text = ", ".join([f"{r} minutes" for r in event.reminders])
            task_parts.append(f"Reminders: {reminder_text}")
        
        task_parts.extend([
            "",
            "Steps:",
            "1. Click the create/+ button",
            "2. Fill in the event title",
            "3. Set the start date and time",
            "4. Set the end date and time",
            "5. Add description if provided",
            "6. Add location if provided",
            "7. Add attendees if provided",
            "8. Set reminders if specified",
            "9. Save the event"
        ])
        
        return "\n".join(task_parts)


class CalendarWorkflow(BaseWorkflow):
    """Workflow for Google Calendar automation tasks."""
    
    def __init__(
        self,
        config: WorkflowConfig,
        model_router: ModelRouter,
        profile_manager: BrowserProfileManager,
        security_manager: SecurityManager,
        calendar_url: str = "https://calendar.google.com"
    ):
        """
        Initialize Calendar workflow.
        
        Args:
            config: Workflow configuration
            model_router: Model router for intelligent model selection
            profile_manager: Browser profile manager
            security_manager: Security manager
            calendar_url: Google Calendar URL to use
        """
        super().__init__(config, model_router, profile_manager, security_manager)
        self.calendar_url = calendar_url
        self.dom_helper = CalendarDOMHelper()
        self.date_parser = DateTimeParser()
        
        # Calendar-specific state
        self.current_view = "month"
        self.current_date = date.today()
        self.authenticated = False
        
    async def validate_prerequisites(self) -> bool:
        """Validate Calendar workflow prerequisites."""
        # Validate Calendar URL
        validation = self.security_manager.validate_and_log_url_access(
            self.calendar_url,
            user_id=f"workflow_{self.config.workflow_id}",
            session_id="prerequisites_check"
        )
        
        if validation["recommendation"] == "BLOCK":
            self.logger.error(f"Calendar URL blocked by security policy: {self.calendar_url}")
            return False
        
        # Check if we have appropriate browser profile
        profile = self.profile_manager.get_profile(self.config.browser_profile)
        if not profile:
            self.logger.error(f"Browser profile not found: {self.config.browser_profile}")
            return False
        
        return True

    async def define_steps(self) -> List[WorkflowStep]:
        """Define default Calendar workflow steps."""
        return [
            WorkflowStep(
                name="navigate_to_calendar",
                description="Navigate to Google Calendar",
                task=f"Navigate to {self.calendar_url} and wait for the calendar interface to load",
                complexity=TaskComplexity.SIMPLE,
                timeout=30.0
            ),
            WorkflowStep(
                name="verify_authentication",
                description="Verify Calendar authentication",
                task="Check if user is logged into Google Calendar. Look for calendar interface elements like the create button and calendar grid.",
                complexity=TaskComplexity.SIMPLE,
                timeout=15.0
            )
        ]

    async def create_event(self, event: CalendarEvent) -> bool:
        """
        Create a new calendar event.
        
        Args:
            event: Calendar event to create
            
        Returns:
            True if event was created successfully
        """
        self.logger.info(f"Creating calendar event: {event.title}")
        
        # Validate event data
        if not event.title:
            raise ValueError("Event title is required")
        
        if event.start_time >= event.end_time:
            raise ValueError("Event start time must be before end time")
        
        # Validate attendee email addresses
        for attendee in event.attendees:
            if not self._validate_email_address(attendee):
                raise ValueError(f"Invalid attendee email address: {attendee}")
        
        # Create event creation task
        create_task = self.dom_helper.format_event_creation_task(event)
        
        step = WorkflowStep(
            name="create_calendar_event",
            description="Create calendar event",
            task=create_task,
            complexity=TaskComplexity.MODERATE,
            timeout=90.0
        )
        
        try:
            await self._execute_single_step(step)
            self.logger.info("Calendar event created successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create calendar event: {e}")
            return False

    async def view_events(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        view_type: str = "month"
    ) -> List[CalendarEvent]:
        """
        View calendar events in a date range.
        
        Args:
            start_date: Start date for viewing events
            end_date: End date for viewing events
            view_type: Calendar view type (month, week, day, agenda)
            
        Returns:
            List of calendar events
        """
        self.logger.info(f"Viewing calendar events in {view_type} view")
        
        if not start_date:
            start_date = date.today()
        
        if not end_date:
            if view_type == "day":
                end_date = start_date
            elif view_type == "week":
                end_date = start_date + timedelta(days=7)
            else:  # month or agenda
                end_date = start_date + timedelta(days=30)
        
        steps = []
        
        # Switch to appropriate view
        if view_type != self.current_view:
            steps.append(WorkflowStep(
                name="switch_calendar_view",
                description=f"Switch to {view_type} view",
                task=f"Switch Google Calendar to {view_type} view by clicking the appropriate view button",
                complexity=TaskComplexity.SIMPLE,
                timeout=15.0
            ))
        
        # Navigate to date range
        if start_date != self.current_date:
            steps.append(WorkflowStep(
                name="navigate_to_date",
                description="Navigate to target date",
                task=f"Navigate to {start_date.strftime('%B %Y')} in Google Calendar",
                complexity=TaskComplexity.SIMPLE,
                timeout=20.0
            ))
        
        # Extract events
        steps.append(WorkflowStep(
            name="extract_calendar_events",
            description="Extract calendar events",
            task=f"Extract all calendar events visible in the current view from {start_date} to {end_date}, including title, time, location, and attendees",
            complexity=TaskComplexity.MODERATE,
            requires_vision=True,
            timeout=30.0
        ))
        
        # Execute steps
        results = []
        for step in steps:
            try:
                result = await self._execute_single_step(step)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Failed to execute step {step.name}: {e}")
                if not self.config.continue_on_error:
                    raise
        
        # Parse results into CalendarEvent objects
        events = self._parse_event_results(results)
        
        self.current_view = view_type
        self.current_date = start_date
        return events

    async def search_events(self, criteria: CalendarSearchCriteria) -> List[CalendarEvent]:
        """
        Search for calendar events based on criteria.
        
        Args:
            criteria: Search criteria
            
        Returns:
            List of matching calendar events
        """
        self.logger.info("Searching calendar events")
        
        # Build search query
        search_terms = []
        if criteria.query:
            search_terms.append(criteria.query)
        if criteria.attendee:
            search_terms.append(f"attendee:{criteria.attendee}")
        if criteria.location:
            search_terms.append(f"location:{criteria.location}")
        
        search_query = " ".join(search_terms)
        
        step = WorkflowStep(
            name="search_calendar_events",
            description="Search calendar events",
            task=f"Search Google Calendar for events matching: {search_query}. Extract the search results including title, date, time, location, and attendees.",
            complexity=TaskComplexity.MODERATE,
            requires_vision=True,
            timeout=30.0
        )
        
        try:
            result = await self._execute_single_step(step)
            events = self._parse_event_results([result])
            return events
            
        except Exception as e:
            self.logger.error(f"Calendar event search failed: {e}")
            return []

    async def update_event(
        self,
        event_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update an existing calendar event.
        
        Args:
            event_id: ID of the event to update
            updates: Dictionary of fields to update
            
        Returns:
            True if event was updated successfully
        """
        self.logger.info(f"Updating calendar event {event_id}")
        
        # Build update description
        update_parts = []
        for field, value in updates.items():
            if field == "title":
                update_parts.append(f"Change title to: {value}")
            elif field == "start_time":
                update_parts.append(f"Change start time to: {value}")
            elif field == "end_time":
                update_parts.append(f"Change end time to: {value}")
            elif field == "location":
                update_parts.append(f"Change location to: {value}")
            elif field == "description":
                update_parts.append(f"Change description to: {value}")
            elif field == "attendees":
                update_parts.append(f"Update attendees to: {', '.join(value)}")
        
        update_description = "; ".join(update_parts)
        
        step = WorkflowStep(
            name="update_calendar_event",
            description="Update calendar event",
            task=f"Find and open the calendar event, then make the following changes: {update_description}. Save the changes.",
            complexity=TaskComplexity.MODERATE,
            timeout=60.0
        )
        
        try:
            await self._execute_single_step(step)
            self.logger.info("Calendar event updated successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update calendar event: {e}")
            return False

    async def delete_event(self, event_id: str) -> bool:
        """
        Delete a calendar event.
        
        Args:
            event_id: ID of the event to delete
            
        Returns:
            True if event was deleted successfully
        """
        self.logger.info(f"Deleting calendar event {event_id}")
        
        step = WorkflowStep(
            name="delete_calendar_event",
            description="Delete calendar event",
            task=f"Find and open the calendar event, then delete it. Confirm the deletion when prompted.",
            complexity=TaskComplexity.MODERATE,
            timeout=30.0
        )
        
        try:
            await self._execute_single_step(step)
            self.logger.info("Calendar event deleted successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete calendar event: {e}")
            return False

    async def check_availability(
        self,
        attendees: List[str],
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, bool]:
        """
        Check availability of attendees for a time slot.
        
        Args:
            attendees: List of attendee email addresses
            start_time: Start time to check
            end_time: End time to check
            
        Returns:
            Dictionary mapping attendee emails to availability status
        """
        self.logger.info(f"Checking availability for {len(attendees)} attendees")
        
        attendee_list = ", ".join(attendees)
        time_range = f"{start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')}"
        
        step = WorkflowStep(
            name="check_attendee_availability",
            description="Check attendee availability",
            task=f"Check the availability of the following attendees for {time_range}: {attendee_list}. Use Google Calendar's scheduling assistant or free/busy view.",
            complexity=TaskComplexity.MODERATE,
            requires_vision=True,
            timeout=45.0
        )
        
        try:
            result = await self._execute_single_step(step)
            # Parse availability results
            availability = self._parse_availability_results(result, attendees)
            return availability
            
        except Exception as e:
            self.logger.error(f"Failed to check availability: {e}")
            return {attendee: False for attendee in attendees}

    def _validate_email_address(self, email: str) -> bool:
        """Validate email address format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    def _parse_event_results(self, results: List[Any]) -> List[CalendarEvent]:
        """Parse workflow results into CalendarEvent objects."""
        # This would need to be implemented based on the actual results structure
        # For now, return placeholder data
        events = []
        
        for i, result in enumerate(results):
            # Parse the result and create CalendarEvent objects
            # This is a placeholder implementation
            start_time = datetime.now() + timedelta(hours=i)
            end_time = start_time + timedelta(hours=1)
            
            event = CalendarEvent(
                title=f"Event {i+1}",
                start_time=start_time,
                end_time=end_time,
                description=f"Event description {i+1}",
                location=f"Location {i+1}",
                attendees=[f"attendee{i+1}@example.com"],
                event_id=f"event_{i+1}"
            )
            events.append(event)
        
        return events

    def _parse_availability_results(
        self, 
        result: Any, 
        attendees: List[str]
    ) -> Dict[str, bool]:
        """Parse availability check results."""
        # This would need to be implemented based on the actual results structure
        # For now, return placeholder data
        return {attendee: i % 2 == 0 for i, attendee in enumerate(attendees)}


# Convenience functions for common Calendar workflows

async def create_calendar_event_workflow(
    event: CalendarEvent,
    workflow_id: Optional[str] = None
) -> CalendarWorkflow:
    """Create a workflow for creating a calendar event."""
    config = WorkflowConfig(
        workflow_id=workflow_id or f"calendar_create_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        name="Create Calendar Event",
        description=f"Create event: {event.title}",
        browser_profile="default",
        timeout=300.0
    )
    
    # This would need to be initialized with actual dependencies
    # For now, return a placeholder
    return None  # CalendarWorkflow(config, model_router, profile_manager, security_manager)


async def create_calendar_view_workflow(
    start_date: date,
    end_date: date,
    workflow_id: Optional[str] = None
) -> CalendarWorkflow:
    """Create a workflow for viewing calendar events."""
    config = WorkflowConfig(
        workflow_id=workflow_id or f"calendar_view_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        name="View Calendar Events",
        description=f"View events from {start_date} to {end_date}",
        browser_profile="default",
        timeout=180.0
    )
    
    # This would need to be initialized with actual dependencies
    # For now, return a placeholder
    return None  # CalendarWorkflow(config, model_router, profile_manager, security_manager)