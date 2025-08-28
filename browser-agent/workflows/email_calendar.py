"""
Combined email and calendar workflow example.

This module demonstrates how to combine Gmail and Calendar workflows
to create more complex automation scenarios.
"""

import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta, date

from workflows.workflow_base import (
    BaseWorkflow, WorkflowStep, WorkflowConfig, 
    TaskComplexity, WorkflowResult
)
from tasks.gmail import GmailWorkflow, EmailMessage, EmailSearchCriteria
from tasks.calendar import CalendarWorkflow, CalendarEvent, DateTimeParser
from models.model_router import ModelRouter
from config.profiles import BrowserProfileManager
from utils.security import SecurityManager


@dataclass
class MeetingRequest:
    """Represents a meeting request extracted from email."""
    subject: str
    organizer: str
    attendees: List[str]
    proposed_times: List[datetime]
    duration: timedelta
    location: Optional[str] = None
    description: Optional[str] = None
    email_id: Optional[str] = None


@dataclass
class EmailCalendarWorkflowResult:
    """Result of combined email and calendar workflow."""
    emails_processed: int
    events_created: int
    events_updated: int
    meetings_scheduled: int
    errors: List[str]
    workflow_results: Dict[str, WorkflowResult]


class EmailCalendarWorkflow(BaseWorkflow):
    """Combined workflow for email and calendar automation."""
    
    def __init__(
        self,
        config: WorkflowConfig,
        model_router: ModelRouter,
        profile_manager: BrowserProfileManager,
        security_manager: SecurityManager
    ):
        """
        Initialize combined email and calendar workflow.
        
        Args:
            config: Workflow configuration
            model_router: Model router for intelligent model selection
            profile_manager: Browser profile manager
            security_manager: Security manager
        """
        super().__init__(config, model_router, profile_manager, security_manager)
        
        # Initialize sub-workflows
        self.gmail_workflow = GmailWorkflow(
            config, model_router, profile_manager, security_manager
        )
        self.calendar_workflow = CalendarWorkflow(
            config, model_router, profile_manager, security_manager
        )
        
        # Date/time parser
        self.date_parser = DateTimeParser()
        
        # Workflow state
        self.processed_emails: List[EmailMessage] = []
        self.created_events: List[CalendarEvent] = []
        self.meeting_requests: List[MeetingRequest] = []

    async def validate_prerequisites(self) -> bool:
        """Validate prerequisites for both email and calendar workflows."""
        gmail_valid = await self.gmail_workflow.validate_prerequisites()
        calendar_valid = await self.calendar_workflow.validate_prerequisites()
        
        return gmail_valid and calendar_valid

    async def define_steps(self) -> List[WorkflowStep]:
        """Define combined workflow steps."""
        return [
            WorkflowStep(
                name="initialize_workflows",
                description="Initialize Gmail and Calendar workflows",
                task="Set up both Gmail and Calendar workflows for automation",
                complexity=TaskComplexity.SIMPLE,
                timeout=30.0
            )
        ]

    async def process_meeting_invitations(
        self,
        days_back: int = 7,
        auto_accept: bool = False
    ) -> EmailCalendarWorkflowResult:
        """
        Process meeting invitations from email and update calendar.
        
        Args:
            days_back: Number of days back to search for invitations
            auto_accept: Whether to automatically accept meeting invitations
            
        Returns:
            Combined workflow result
        """
        self.logger.info("Processing meeting invitations from email")
        
        results = EmailCalendarWorkflowResult(
            emails_processed=0,
            events_created=0,
            events_updated=0,
            meetings_scheduled=0,
            errors=[],
            workflow_results={}
        )
        
        try:
            # Search for meeting invitation emails
            search_criteria = EmailSearchCriteria(
                query="meeting OR invitation OR calendar",
                date_after=datetime.now() - timedelta(days=days_back),
                is_unread=True
            )
            
            emails = await self.gmail_workflow.search_emails(search_criteria)
            results.emails_processed = len(emails)
            
            # Process each email for meeting information
            for email in emails:
                try:
                    meeting_request = await self._extract_meeting_from_email(email)
                    if meeting_request:
                        self.meeting_requests.append(meeting_request)
                        
                        # Create calendar event
                        calendar_event = await self._create_event_from_meeting(meeting_request)
                        if calendar_event:
                            success = await self.calendar_workflow.create_event(calendar_event)
                            if success:
                                results.events_created += 1
                                results.meetings_scheduled += 1
                                self.created_events.append(calendar_event)
                                
                                # Reply to email if auto-accept is enabled
                                if auto_accept:
                                    await self._send_meeting_acceptance(email, meeting_request)
                
                except Exception as e:
                    error_msg = f"Failed to process email {email.subject}: {str(e)}"
                    results.errors.append(error_msg)
                    self.logger.error(error_msg)
            
        except Exception as e:
            error_msg = f"Failed to process meeting invitations: {str(e)}"
            results.errors.append(error_msg)
            self.logger.error(error_msg)
        
        return results

    async def schedule_meeting_from_email_request(
        self,
        email_subject_pattern: str = "schedule meeting",
        default_duration: timedelta = timedelta(hours=1)
    ) -> EmailCalendarWorkflowResult:
        """
        Schedule meetings based on email requests.
        
        Args:
            email_subject_pattern: Pattern to search for in email subjects
            default_duration: Default meeting duration
            
        Returns:
            Combined workflow result
        """
        self.logger.info("Scheduling meetings from email requests")
        
        results = EmailCalendarWorkflowResult(
            emails_processed=0,
            events_created=0,
            events_updated=0,
            meetings_scheduled=0,
            errors=[],
            workflow_results={}
        )
        
        try:
            # Search for meeting request emails
            search_criteria = EmailSearchCriteria(
                subject=email_subject_pattern,
                is_unread=True
            )
            
            emails = await self.gmail_workflow.search_emails(search_criteria)
            results.emails_processed = len(emails)
            
            # Process each email
            for email in emails:
                try:
                    # Extract meeting details from email
                    meeting_details = await self._parse_meeting_request_email(email)
                    
                    if meeting_details:
                        # Check availability for proposed times
                        available_time = await self._find_available_time(
                            meeting_details['attendees'],
                            meeting_details['proposed_times'],
                            meeting_details.get('duration', default_duration)
                        )
                        
                        if available_time:
                            # Create calendar event
                            event = CalendarEvent(
                                title=meeting_details['subject'],
                                start_time=available_time,
                                end_time=available_time + meeting_details.get('duration', default_duration),
                                description=meeting_details.get('description'),
                                location=meeting_details.get('location'),
                                attendees=meeting_details['attendees']
                            )
                            
                            success = await self.calendar_workflow.create_event(event)
                            if success:
                                results.events_created += 1
                                results.meetings_scheduled += 1
                                
                                # Send confirmation email
                                await self._send_meeting_confirmation(email, event)
                        else:
                            # Send email about no available time
                            await self._send_no_availability_response(email, meeting_details)
                
                except Exception as e:
                    error_msg = f"Failed to schedule meeting from email {email.subject}: {str(e)}"
                    results.errors.append(error_msg)
                    self.logger.error(error_msg)
        
        except Exception as e:
            error_msg = f"Failed to schedule meetings from email requests: {str(e)}"
            results.errors.append(error_msg)
            self.logger.error(error_msg)
        
        return results

    async def sync_calendar_events_to_email(
        self,
        days_ahead: int = 7,
        send_reminders: bool = True
    ) -> EmailCalendarWorkflowResult:
        """
        Sync calendar events to email (send reminders, updates, etc.).
        
        Args:
            days_ahead: Number of days ahead to check for events
            send_reminders: Whether to send email reminders
            
        Returns:
            Combined workflow result
        """
        self.logger.info("Syncing calendar events to email")
        
        results = EmailCalendarWorkflowResult(
            emails_processed=0,
            events_created=0,
            events_updated=0,
            meetings_scheduled=0,
            errors=[],
            workflow_results={}
        )
        
        try:
            # Get upcoming calendar events
            start_date = date.today()
            end_date = start_date + timedelta(days=days_ahead)
            
            events = await self.calendar_workflow.view_events(start_date, end_date)
            
            # Process each event
            for event in events:
                try:
                    if send_reminders and self._should_send_reminder(event):
                        await self._send_event_reminder(event)
                        results.emails_processed += 1
                
                except Exception as e:
                    error_msg = f"Failed to process event {event.title}: {str(e)}"
                    results.errors.append(error_msg)
                    self.logger.error(error_msg)
        
        except Exception as e:
            error_msg = f"Failed to sync calendar events to email: {str(e)}"
            results.errors.append(error_msg)
            self.logger.error(error_msg)
        
        return results

    async def _extract_meeting_from_email(self, email: EmailMessage) -> Optional[MeetingRequest]:
        """Extract meeting information from an email."""
        # This would use NLP/AI to extract meeting details from email content
        # For now, return a placeholder implementation
        
        # Look for common meeting patterns in email body
        meeting_patterns = [
            r'meeting.*(\d{1,2}:\d{2})',  # Time patterns
            r'schedule.*meeting',
            r'calendar.*invite'
        ]
        
        # Extract proposed times (placeholder logic)
        proposed_times = []
        # This would parse the email body for dates and times
        
        if any(pattern in email.body.lower() for pattern in ['meeting', 'schedule', 'calendar']):
            return MeetingRequest(
                subject=email.subject,
                organizer=email.sender,
                attendees=[email.recipient],
                proposed_times=proposed_times or [datetime.now() + timedelta(days=1)],
                duration=timedelta(hours=1),
                email_id=email.message_id
            )
        
        return None

    async def _create_event_from_meeting(self, meeting_request: MeetingRequest) -> Optional[CalendarEvent]:
        """Create a calendar event from a meeting request."""
        if not meeting_request.proposed_times:
            return None
        
        # Use the first proposed time
        start_time = meeting_request.proposed_times[0]
        end_time = start_time + meeting_request.duration
        
        return CalendarEvent(
            title=meeting_request.subject,
            start_time=start_time,
            end_time=end_time,
            description=meeting_request.description,
            location=meeting_request.location,
            attendees=meeting_request.attendees,
            organizer=meeting_request.organizer
        )

    async def _parse_meeting_request_email(self, email: EmailMessage) -> Optional[Dict[str, Any]]:
        """Parse meeting request details from email."""
        # This would use AI/NLP to extract structured data from email
        # For now, return placeholder data
        
        return {
            'subject': f"Meeting: {email.subject}",
            'attendees': [email.sender],
            'proposed_times': [datetime.now() + timedelta(days=1)],
            'duration': timedelta(hours=1),
            'description': email.body[:200] + "..." if len(email.body) > 200 else email.body
        }

    async def _find_available_time(
        self,
        attendees: List[str],
        proposed_times: List[datetime],
        duration: timedelta
    ) -> Optional[datetime]:
        """Find an available time slot for all attendees."""
        for proposed_time in proposed_times:
            # Check availability for all attendees
            availability = await self.calendar_workflow.check_availability(
                attendees,
                proposed_time,
                proposed_time + duration
            )
            
            # If all attendees are available, return this time
            if all(availability.values()):
                return proposed_time
        
        return None

    async def _send_meeting_acceptance(self, email: EmailMessage, meeting_request: MeetingRequest):
        """Send meeting acceptance email."""
        reply_body = f"""
Thank you for the meeting invitation.

I have accepted the meeting and added it to my calendar:
- Subject: {meeting_request.subject}
- Time: {meeting_request.proposed_times[0].strftime('%Y-%m-%d %H:%M')}
- Duration: {meeting_request.duration}

Looking forward to the meeting.

Best regards
"""
        
        await self.gmail_workflow.reply_to_email(
            email.message_id,
            reply_body.strip()
        )

    async def _send_meeting_confirmation(self, email: EmailMessage, event: CalendarEvent):
        """Send meeting confirmation email."""
        confirmation_body = f"""
Meeting Scheduled Successfully

I have scheduled the meeting as requested:

Subject: {event.title}
Date & Time: {event.start_time.strftime('%Y-%m-%d %H:%M')} - {event.end_time.strftime('%H:%M')}
Location: {event.location or 'TBD'}
Attendees: {', '.join(event.attendees)}

Calendar invitation will be sent separately.

Best regards
"""
        
        await self.gmail_workflow.reply_to_email(
            email.message_id,
            confirmation_body.strip()
        )

    async def _send_no_availability_response(self, email: EmailMessage, meeting_details: Dict[str, Any]):
        """Send response when no time slots are available."""
        response_body = f"""
Meeting Scheduling - No Available Time

I was unable to find a suitable time slot for the requested meeting:

Subject: {meeting_details['subject']}
Requested times: {', '.join([t.strftime('%Y-%m-%d %H:%M') for t in meeting_details['proposed_times']])}

Please suggest alternative times, and I'll check availability again.

Best regards
"""
        
        await self.gmail_workflow.reply_to_email(
            email.message_id,
            response_body.strip()
        )

    def _should_send_reminder(self, event: CalendarEvent) -> bool:
        """Determine if a reminder should be sent for an event."""
        # Send reminder 24 hours before the event
        time_until_event = event.start_time - datetime.now()
        return timedelta(hours=23) <= time_until_event <= timedelta(hours=25)

    async def _send_event_reminder(self, event: CalendarEvent):
        """Send email reminder for an upcoming event."""
        reminder_subject = f"Reminder: {event.title}"
        reminder_body = f"""
Event Reminder

You have an upcoming event:

Subject: {event.title}
Date & Time: {event.start_time.strftime('%Y-%m-%d %H:%M')} - {event.end_time.strftime('%H:%M')}
Location: {event.location or 'TBD'}

{event.description or ''}

This is an automated reminder.
"""
        
        # Send to all attendees
        for attendee in event.attendees:
            await self.gmail_workflow.compose_email(
                to=attendee,
                subject=reminder_subject,
                body=reminder_body.strip()
            )


# Convenience functions for creating common email-calendar workflows

async def create_meeting_processor_workflow(
    workflow_id: Optional[str] = None,
    auto_accept: bool = False
) -> EmailCalendarWorkflow:
    """Create a workflow for processing meeting invitations."""
    config = WorkflowConfig(
        workflow_id=workflow_id or f"meeting_processor_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        name="Meeting Invitation Processor",
        description="Process meeting invitations from email and update calendar",
        browser_profile="default",
        timeout=600.0,
        continue_on_error=True
    )
    
    # This would need to be initialized with actual dependencies
    # For now, return a placeholder
    return None  # EmailCalendarWorkflow(config, model_router, profile_manager, security_manager)


async def create_meeting_scheduler_workflow(
    workflow_id: Optional[str] = None
) -> EmailCalendarWorkflow:
    """Create a workflow for scheduling meetings from email requests."""
    config = WorkflowConfig(
        workflow_id=workflow_id or f"meeting_scheduler_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        name="Meeting Scheduler",
        description="Schedule meetings based on email requests",
        browser_profile="default",
        timeout=600.0,
        continue_on_error=True
    )
    
    # This would need to be initialized with actual dependencies
    # For now, return a placeholder
    return None  # EmailCalendarWorkflow(config, model_router, profile_manager, security_manager)


async def create_calendar_sync_workflow(
    workflow_id: Optional[str] = None
) -> EmailCalendarWorkflow:
    """Create a workflow for syncing calendar events to email."""
    config = WorkflowConfig(
        workflow_id=workflow_id or f"calendar_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        name="Calendar Email Sync",
        description="Sync calendar events to email reminders and updates",
        browser_profile="default",
        timeout=300.0,
        continue_on_error=True
    )
    
    # This would need to be initialized with actual dependencies
    # For now, return a placeholder
    return None  # EmailCalendarWorkflow(config, model_router, profile_manager, security_manager)