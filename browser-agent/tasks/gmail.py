"""
Gmail workflow implementation for email automation tasks.

This module provides specialized workflows for Gmail interactions including
reading, composing, searching emails, and DOM helpers for Gmail's interface.
"""

import re
import asyncio
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from datetime import datetime, timedelta

from workflows.workflow_base import (
    BaseWorkflow, WorkflowStep, WorkflowConfig, 
    TaskComplexity, SecurityError
)
from models.model_router import ModelRouter
from config.profiles import BrowserProfileManager
from utils.security import SecurityManager


@dataclass
class EmailMessage:
    """Represents an email message."""
    subject: str
    sender: str
    recipient: str
    body: str
    timestamp: Optional[datetime] = None
    thread_id: Optional[str] = None
    message_id: Optional[str] = None
    labels: List[str] = None
    attachments: List[str] = None
    is_read: bool = False
    is_important: bool = False

    def __post_init__(self):
        if self.labels is None:
            self.labels = []
        if self.attachments is None:
            self.attachments = []


@dataclass
class EmailSearchCriteria:
    """Search criteria for Gmail emails."""
    query: Optional[str] = None
    sender: Optional[str] = None
    recipient: Optional[str] = None
    subject: Optional[str] = None
    has_attachment: Optional[bool] = None
    is_unread: Optional[bool] = None
    is_important: Optional[bool] = None
    date_after: Optional[datetime] = None
    date_before: Optional[datetime] = None
    labels: Optional[List[str]] = None
    max_results: int = 50


class GmailDOMHelper:
    """Helper class for Gmail DOM interactions."""
    
    # Gmail-specific selectors
    SELECTORS = {
        # Navigation
        "compose_button": "div[gh='cm']",
        "inbox_link": "a[href='#inbox']",
        "sent_link": "a[href='#sent']",
        "drafts_link": "a[href='#drafts']",
        "search_box": "input[name='q']",
        "search_button": "button[aria-label='Search Mail']",
        
        # Email list
        "email_list": "tbody",
        "email_row": "tr.zA",
        "email_checkbox": "span[role='checkbox']",
        "email_subject": "span[id^=':']",
        "email_sender": "span.go span[email]",
        "email_date": "span[title]",
        "unread_indicator": ".yW",
        "important_marker": ".aXw",
        
        # Email view
        "email_content": "div[role='listitem']",
        "email_body": "div[dir='ltr']",
        "reply_button": "span[role='button'][aria-label*='Reply']",
        "forward_button": "span[role='button'][aria-label*='Forward']",
        "delete_button": "div[aria-label='Delete']",
        "archive_button": "div[aria-label='Archive']",
        
        # Compose
        "compose_to": "textarea[name='to']",
        "compose_cc": "textarea[name='cc']",
        "compose_bcc": "textarea[name='bcc']",
        "compose_subject": "input[name='subjectbox']",
        "compose_body": "div[role='textbox'][aria-label='Message Body']",
        "send_button": "div[role='button'][aria-label*='Send']",
        "attach_button": "div[command='Files']",
        
        # Labels and folders
        "label_button": "div[aria-label='Labels']",
        "move_to_button": "div[aria-label='Move to']",
        "more_actions": "div[aria-label='More']",
    }
    
    @staticmethod
    def build_search_query(criteria: EmailSearchCriteria) -> str:
        """Build Gmail search query from criteria."""
        query_parts = []
        
        if criteria.query:
            query_parts.append(criteria.query)
        
        if criteria.sender:
            query_parts.append(f"from:{criteria.sender}")
        
        if criteria.recipient:
            query_parts.append(f"to:{criteria.recipient}")
        
        if criteria.subject:
            query_parts.append(f"subject:{criteria.subject}")
        
        if criteria.has_attachment is not None:
            query_parts.append("has:attachment" if criteria.has_attachment else "-has:attachment")
        
        if criteria.is_unread is not None:
            query_parts.append("is:unread" if criteria.is_unread else "-is:unread")
        
        if criteria.is_important is not None:
            query_parts.append("is:important" if criteria.is_important else "-is:important")
        
        if criteria.date_after:
            date_str = criteria.date_after.strftime("%Y/%m/%d")
            query_parts.append(f"after:{date_str}")
        
        if criteria.date_before:
            date_str = criteria.date_before.strftime("%Y/%m/%d")
            query_parts.append(f"before:{date_str}")
        
        if criteria.labels:
            for label in criteria.labels:
                query_parts.append(f"label:{label}")
        
        return " ".join(query_parts)
    
    @staticmethod
    def extract_email_data_from_dom(email_element_html: str) -> Dict[str, Any]:
        """Extract email data from DOM element HTML."""
        # This would contain logic to parse Gmail's DOM structure
        # For now, return a placeholder structure
        return {
            "subject": "Extracted subject",
            "sender": "sender@example.com",
            "date": "Today",
            "is_read": False,
            "is_important": False
        }
    
    @staticmethod
    def get_compose_task_prompt(to: str, subject: str, body: str, cc: Optional[str] = None) -> str:
        """Generate task prompt for composing an email."""
        task_parts = [
            "Compose and send an email in Gmail with the following details:",
            f"To: {to}",
            f"Subject: {subject}",
            f"Body: {body}"
        ]
        
        if cc:
            task_parts.insert(-1, f"CC: {cc}")
        
        task_parts.extend([
            "",
            "Steps:",
            "1. Click the compose button",
            "2. Fill in the recipient field",
            "3. Add CC if specified",
            "4. Enter the subject",
            "5. Type the email body",
            "6. Click send"
        ])
        
        return "\n".join(task_parts)


class GmailWorkflow(BaseWorkflow):
    """Workflow for Gmail email automation tasks."""
    
    def __init__(
        self,
        config: WorkflowConfig,
        model_router: ModelRouter,
        profile_manager: BrowserProfileManager,
        security_manager: SecurityManager,
        gmail_url: str = "https://mail.google.com"
    ):
        """
        Initialize Gmail workflow.
        
        Args:
            config: Workflow configuration
            model_router: Model router for intelligent model selection
            profile_manager: Browser profile manager
            security_manager: Security manager
            gmail_url: Gmail URL to use
        """
        super().__init__(config, model_router, profile_manager, security_manager)
        self.gmail_url = gmail_url
        self.dom_helper = GmailDOMHelper()
        
        # Gmail-specific state
        self.current_folder = "inbox"
        self.authenticated = False
        
    async def validate_prerequisites(self) -> bool:
        """Validate Gmail workflow prerequisites."""
        # Validate Gmail URL
        validation = self.security_manager.validate_and_log_url_access(
            self.gmail_url,
            user_id=f"workflow_{self.config.workflow_id}",
            session_id="prerequisites_check"
        )
        
        if validation["recommendation"] == "BLOCK":
            self.logger.error(f"Gmail URL blocked by security policy: {self.gmail_url}")
            return False
        
        # Check if we have appropriate browser profile
        profile = self.profile_manager.get_profile(self.config.browser_profile)
        if not profile:
            self.logger.error(f"Browser profile not found: {self.config.browser_profile}")
            return False
        
        return True

    async def define_steps(self) -> List[WorkflowStep]:
        """Define default Gmail workflow steps."""
        return [
            WorkflowStep(
                name="navigate_to_gmail",
                description="Navigate to Gmail",
                task=f"Navigate to {self.gmail_url} and wait for the page to load",
                complexity=TaskComplexity.SIMPLE,
                timeout=30.0
            ),
            WorkflowStep(
                name="verify_authentication",
                description="Verify Gmail authentication",
                task="Check if user is logged into Gmail. Look for the Gmail interface elements like compose button and inbox.",
                complexity=TaskComplexity.SIMPLE,
                timeout=15.0
            )
        ]

    async def read_emails(
        self, 
        criteria: Optional[EmailSearchCriteria] = None,
        folder: str = "inbox"
    ) -> List[EmailMessage]:
        """
        Read emails from Gmail.
        
        Args:
            criteria: Search criteria for filtering emails
            folder: Gmail folder to read from
            
        Returns:
            List of email messages
        """
        self.logger.info(f"Reading emails from {folder}")
        
        # Create workflow steps for reading emails
        steps = []
        
        # Navigate to folder
        if folder != self.current_folder:
            steps.append(WorkflowStep(
                name="navigate_to_folder",
                description=f"Navigate to {folder} folder",
                task=f"Click on the {folder} folder in Gmail navigation to view emails in that folder",
                complexity=TaskComplexity.SIMPLE,
                timeout=15.0
            ))
        
        # Apply search criteria if provided
        if criteria:
            search_query = self.dom_helper.build_search_query(criteria)
            if search_query:
                steps.append(WorkflowStep(
                    name="apply_search_filter",
                    description="Apply search filter",
                    task=f"Use Gmail search to filter emails with query: {search_query}",
                    complexity=TaskComplexity.MODERATE,
                    timeout=20.0
                ))
        
        # Read email list
        steps.append(WorkflowStep(
            name="extract_email_list",
            description="Extract email list from current view",
            task="Extract the list of emails visible in the current Gmail view, including subject, sender, date, and read status",
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
        
        # Parse results into EmailMessage objects
        # This would need to be implemented based on the actual results structure
        emails = self._parse_email_results(results)
        
        self.current_folder = folder
        return emails

    async def compose_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        attachments: Optional[List[str]] = None
    ) -> bool:
        """
        Compose and send an email.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body
            cc: CC recipients (optional)
            bcc: BCC recipients (optional)
            attachments: List of file paths to attach (optional)
            
        Returns:
            True if email was sent successfully
        """
        self.logger.info(f"Composing email to {to}")
        
        # Validate email addresses
        if not self._validate_email_address(to):
            raise ValueError(f"Invalid recipient email address: {to}")
        
        if cc and not self._validate_email_address(cc):
            raise ValueError(f"Invalid CC email address: {cc}")
        
        if bcc and not self._validate_email_address(bcc):
            raise ValueError(f"Invalid BCC email address: {bcc}")
        
        # Create compose task
        compose_task = self.dom_helper.get_compose_task_prompt(to, subject, body, cc)
        
        steps = [
            WorkflowStep(
                name="compose_email",
                description="Compose and send email",
                task=compose_task,
                complexity=TaskComplexity.MODERATE,
                timeout=60.0
            )
        ]
        
        # Add attachment step if needed
        if attachments:
            steps.append(WorkflowStep(
                name="add_attachments",
                description="Add email attachments",
                task=f"Add the following attachments to the email: {', '.join(attachments)}",
                complexity=TaskComplexity.MODERATE,
                timeout=30.0,
                dependencies=["compose_email"]
            ))
        
        # Execute steps
        try:
            for step in steps:
                await self._execute_single_step(step)
            
            self.logger.info("Email sent successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")
            return False

    async def search_emails(self, criteria: EmailSearchCriteria) -> List[EmailMessage]:
        """
        Search for emails based on criteria.
        
        Args:
            criteria: Search criteria
            
        Returns:
            List of matching email messages
        """
        self.logger.info("Searching emails with criteria")
        
        search_query = self.dom_helper.build_search_query(criteria)
        
        step = WorkflowStep(
            name="search_emails",
            description="Search emails",
            task=f"Search Gmail for emails matching: {search_query}. Extract the search results including subject, sender, date, and preview text.",
            complexity=TaskComplexity.MODERATE,
            requires_vision=True,
            timeout=30.0
        )
        
        try:
            result = await self._execute_single_step(step)
            emails = self._parse_email_results([result])
            return emails
            
        except Exception as e:
            self.logger.error(f"Email search failed: {e}")
            return []

    async def reply_to_email(
        self,
        email_id: str,
        reply_body: str,
        reply_all: bool = False
    ) -> bool:
        """
        Reply to an email.
        
        Args:
            email_id: ID of the email to reply to
            reply_body: Reply message body
            reply_all: Whether to reply to all recipients
            
        Returns:
            True if reply was sent successfully
        """
        self.logger.info(f"Replying to email {email_id}")
        
        reply_type = "Reply All" if reply_all else "Reply"
        
        step = WorkflowStep(
            name="reply_to_email",
            description=f"{reply_type} to email",
            task=f"Find and open the email, click {reply_type}, compose the following response: {reply_body}, then send the reply.",
            complexity=TaskComplexity.MODERATE,
            timeout=45.0
        )
        
        try:
            await self._execute_single_step(step)
            self.logger.info("Reply sent successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send reply: {e}")
            return False

    async def delete_emails(self, email_ids: List[str]) -> bool:
        """
        Delete emails by ID.
        
        Args:
            email_ids: List of email IDs to delete
            
        Returns:
            True if emails were deleted successfully
        """
        self.logger.info(f"Deleting {len(email_ids)} emails")
        
        step = WorkflowStep(
            name="delete_emails",
            description="Delete selected emails",
            task=f"Select and delete the specified emails from Gmail. Email IDs: {', '.join(email_ids)}",
            complexity=TaskComplexity.MODERATE,
            timeout=30.0
        )
        
        try:
            await self._execute_single_step(step)
            self.logger.info("Emails deleted successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete emails: {e}")
            return False

    async def organize_emails(
        self,
        email_ids: List[str],
        action: str,
        target: Optional[str] = None
    ) -> bool:
        """
        Organize emails (archive, label, move to folder).
        
        Args:
            email_ids: List of email IDs to organize
            action: Action to perform (archive, label, move)
            target: Target label or folder name (for label/move actions)
            
        Returns:
            True if organization was successful
        """
        self.logger.info(f"Organizing {len(email_ids)} emails with action: {action}")
        
        if action in ["label", "move"] and not target:
            raise ValueError(f"Target required for action: {action}")
        
        task_description = f"Select the specified emails and {action} them"
        if target:
            task_description += f" to {target}"
        
        step = WorkflowStep(
            name="organize_emails",
            description="Organize emails",
            task=f"{task_description}. Email IDs: {', '.join(email_ids)}",
            complexity=TaskComplexity.MODERATE,
            timeout=30.0
        )
        
        try:
            await self._execute_single_step(step)
            self.logger.info("Emails organized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to organize emails: {e}")
            return False

    def _validate_email_address(self, email: str) -> bool:
        """Validate email address format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    def _parse_email_results(self, results: List[Any]) -> List[EmailMessage]:
        """Parse workflow results into EmailMessage objects."""
        # This would need to be implemented based on the actual results structure
        # For now, return placeholder data
        emails = []
        
        for i, result in enumerate(results):
            # Parse the result and create EmailMessage objects
            # This is a placeholder implementation
            email = EmailMessage(
                subject=f"Email Subject {i+1}",
                sender=f"sender{i+1}@example.com",
                recipient="user@example.com",
                body=f"Email body content {i+1}",
                timestamp=datetime.now() - timedelta(hours=i),
                is_read=i % 2 == 0
            )
            emails.append(email)
        
        return emails


# Convenience functions for common Gmail workflows

async def create_gmail_read_workflow(
    criteria: Optional[EmailSearchCriteria] = None,
    folder: str = "inbox",
    workflow_id: Optional[str] = None
) -> GmailWorkflow:
    """Create a workflow for reading Gmail emails."""
    config = WorkflowConfig(
        workflow_id=workflow_id or f"gmail_read_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        name="Gmail Read Emails",
        description=f"Read emails from {folder} folder",
        browser_profile="default",
        timeout=300.0
    )
    
    # This would need to be initialized with actual dependencies
    # For now, return a placeholder
    return None  # GmailWorkflow(config, model_router, profile_manager, security_manager)


async def create_gmail_compose_workflow(
    to: str,
    subject: str,
    body: str,
    workflow_id: Optional[str] = None
) -> GmailWorkflow:
    """Create a workflow for composing Gmail emails."""
    config = WorkflowConfig(
        workflow_id=workflow_id or f"gmail_compose_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        name="Gmail Compose Email",
        description=f"Compose email to {to}",
        browser_profile="default",
        timeout=180.0
    )
    
    # This would need to be initialized with actual dependencies
    # For now, return a placeholder
    return None  # GmailWorkflow(config, model_router, profile_manager, security_manager)