"""
Generic form handling workflow implementation.

This module provides a generic FormHandler class for automating form interactions
with methods for different form field types, validation, and error handling.
"""

import re
import asyncio
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, date

from workflows.workflow_base import (
    BaseWorkflow, WorkflowStep, WorkflowConfig, 
    TaskComplexity, SecurityError
)
from models.model_router import ModelRouter
from config.profiles import BrowserProfileManager
from utils.security import SecurityManager


class FieldType(str, Enum):
    """Form field types."""
    TEXT = "text"
    EMAIL = "email"
    PASSWORD = "password"
    NUMBER = "number"
    PHONE = "phone"
    URL = "url"
    DATE = "date"
    TIME = "time"
    DATETIME = "datetime"
    TEXTAREA = "textarea"
    SELECT = "select"
    MULTISELECT = "multiselect"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    FILE = "file"
    HIDDEN = "hidden"
    BUTTON = "button"
    SUBMIT = "submit"


class ValidationRule(str, Enum):
    """Form validation rules."""
    REQUIRED = "required"
    EMAIL_FORMAT = "email_format"
    PHONE_FORMAT = "phone_format"
    URL_FORMAT = "url_format"
    MIN_LENGTH = "min_length"
    MAX_LENGTH = "max_length"
    PATTERN = "pattern"
    NUMERIC = "numeric"
    DATE_FORMAT = "date_format"
    CUSTOM = "custom"


@dataclass
class FormField:
    """Represents a form field."""
    name: str
    field_type: FieldType
    label: Optional[str] = None
    value: Optional[Any] = None
    placeholder: Optional[str] = None
    required: bool = False
    readonly: bool = False
    disabled: bool = False
    validation_rules: List[ValidationRule] = field(default_factory=list)
    validation_params: Dict[str, Any] = field(default_factory=dict)
    options: List[Dict[str, str]] = field(default_factory=list)  # For select/radio fields
    selector: Optional[str] = None  # CSS selector for the field
    xpath: Optional[str] = None  # XPath selector for the field
    error_message: Optional[str] = None
    help_text: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FormSection:
    """Represents a section of a form."""
    name: str
    title: Optional[str] = None
    description: Optional[str] = None
    fields: List[FormField] = field(default_factory=list)
    conditional: bool = False  # Whether this section appears conditionally
    condition: Optional[str] = None  # Condition for showing this section
    order: int = 0


@dataclass
class FormDefinition:
    """Complete form definition."""
    name: str
    title: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    sections: List[FormSection] = field(default_factory=list)
    submit_button_selector: Optional[str] = None
    success_indicators: List[str] = field(default_factory=list)  # Selectors for success
    error_indicators: List[str] = field(default_factory=list)  # Selectors for errors
    timeout: float = 60.0
    retry_on_error: bool = True
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FormSubmissionResult:
    """Result of form submission."""
    success: bool
    form_name: str
    submitted_data: Dict[str, Any]
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    response_data: Optional[Dict[str, Any]] = None
    redirect_url: Optional[str] = None
    submission_time: datetime = field(default_factory=datetime.now)


class FormValidator:
    """Utility class for form field validation."""
    
    # Validation patterns
    PATTERNS = {
        ValidationRule.EMAIL_FORMAT: r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        ValidationRule.PHONE_FORMAT: r'^\+?[\d\s\-\(\)]{10,}$',
        ValidationRule.URL_FORMAT: r'^https?://[^\s/$.?#].[^\s]*$',
        ValidationRule.NUMERIC: r'^\d+(\.\d+)?$',
        ValidationRule.DATE_FORMAT: r'^\d{4}-\d{2}-\d{2}$'
    }
    
    @classmethod
    def validate_field(cls, field: FormField, value: Any) -> List[str]:
        """
        Validate a form field value.
        
        Args:
            field: Form field definition
            value: Value to validate
            
        Returns:
            List of validation error messages
        """
        errors = []
        
        # Convert value to string for validation
        str_value = str(value) if value is not None else ""
        
        # Required field validation
        if ValidationRule.REQUIRED in field.validation_rules:
            if not str_value.strip():
                errors.append(f"{field.label or field.name} is required")
                return errors  # Don't validate further if required field is empty
        
        # Skip other validations if field is empty and not required
        if not str_value.strip():
            return errors
        
        # Email format validation
        if ValidationRule.EMAIL_FORMAT in field.validation_rules:
            if not re.match(cls.PATTERNS[ValidationRule.EMAIL_FORMAT], str_value):
                errors.append(f"{field.label or field.name} must be a valid email address")
        
        # Phone format validation
        if ValidationRule.PHONE_FORMAT in field.validation_rules:
            if not re.match(cls.PATTERNS[ValidationRule.PHONE_FORMAT], str_value):
                errors.append(f"{field.label or field.name} must be a valid phone number")
        
        # URL format validation
        if ValidationRule.URL_FORMAT in field.validation_rules:
            if not re.match(cls.PATTERNS[ValidationRule.URL_FORMAT], str_value):
                errors.append(f"{field.label or field.name} must be a valid URL")
        
        # Numeric validation
        if ValidationRule.NUMERIC in field.validation_rules:
            if not re.match(cls.PATTERNS[ValidationRule.NUMERIC], str_value):
                errors.append(f"{field.label or field.name} must be a number")
        
        # Length validations
        if ValidationRule.MIN_LENGTH in field.validation_rules:
            min_length = field.validation_params.get('min_length', 0)
            if len(str_value) < min_length:
                errors.append(f"{field.label or field.name} must be at least {min_length} characters")
        
        if ValidationRule.MAX_LENGTH in field.validation_rules:
            max_length = field.validation_params.get('max_length', 1000)
            if len(str_value) > max_length:
                errors.append(f"{field.label or field.name} must be no more than {max_length} characters")
        
        # Pattern validation
        if ValidationRule.PATTERN in field.validation_rules:
            pattern = field.validation_params.get('pattern')
            if pattern and not re.match(pattern, str_value):
                errors.append(f"{field.label or field.name} format is invalid")
        
        # Custom validation
        if ValidationRule.CUSTOM in field.validation_rules:
            custom_validator = field.validation_params.get('custom_validator')
            if custom_validator and callable(custom_validator):
                try:
                    custom_errors = custom_validator(field, value)
                    if custom_errors:
                        errors.extend(custom_errors)
                except Exception as e:
                    errors.append(f"Custom validation failed for {field.label or field.name}: {str(e)}")
        
        return errors
    
    @classmethod
    def validate_form_data(
        cls, 
        form_definition: FormDefinition, 
        form_data: Dict[str, Any]
    ) -> List[str]:
        """
        Validate complete form data.
        
        Args:
            form_definition: Form definition
            form_data: Form data to validate
            
        Returns:
            List of validation error messages
        """
        all_errors = []
        
        for section in form_definition.sections:
            for field in section.fields:
                value = form_data.get(field.name)
                field_errors = cls.validate_field(field, value)
                all_errors.extend(field_errors)
        
        return all_errors


class FormHandler(BaseWorkflow):
    """Generic form handling workflow."""
    
    def __init__(
        self,
        config: WorkflowConfig,
        model_router: ModelRouter,
        profile_manager: BrowserProfileManager,
        security_manager: SecurityManager,
        form_definition: FormDefinition
    ):
        """
        Initialize form handler.
        
        Args:
            config: Workflow configuration
            model_router: Model router for intelligent model selection
            profile_manager: Browser profile manager
            security_manager: Security manager
            form_definition: Definition of the form to handle
        """
        super().__init__(config, model_router, profile_manager, security_manager)
        self.form_definition = form_definition
        self.validator = FormValidator()
        
        # Form-specific state
        self.current_section = 0
        self.form_data: Dict[str, Any] = {}
        self.validation_errors: List[str] = []
        
    async def validate_prerequisites(self) -> bool:
        """Validate form handling prerequisites."""
        # Validate form URL if provided
        if self.form_definition.url:
            validation = self.security_manager.validate_and_log_url_access(
                self.form_definition.url,
                user_id=f"workflow_{self.config.workflow_id}",
                session_id="prerequisites_check"
            )
            
            if validation["recommendation"] == "BLOCK":
                self.logger.error(f"Form URL blocked by security policy: {self.form_definition.url}")
                return False
        
        # Validate form definition
        if not self.form_definition.sections:
            self.logger.error("Form definition has no sections")
            return False
        
        return True

    async def define_steps(self) -> List[WorkflowStep]:
        """Define form handling workflow steps."""
        steps = []
        
        # Navigate to form if URL provided
        if self.form_definition.url:
            steps.append(WorkflowStep(
                name="navigate_to_form",
                description="Navigate to form page",
                task=f"Navigate to {self.form_definition.url} and wait for the form to load",
                complexity=TaskComplexity.SIMPLE,
                timeout=30.0
            ))
        
        # Add steps for each form section
        for i, section in enumerate(self.form_definition.sections):
            steps.append(WorkflowStep(
                name=f"fill_section_{i}_{section.name}",
                description=f"Fill form section: {section.title or section.name}",
                task=self._generate_section_task(section),
                complexity=TaskComplexity.MODERATE,
                timeout=self.form_definition.timeout,
                dependencies=["navigate_to_form"] if self.form_definition.url else []
            ))
        
        # Add form submission step
        steps.append(WorkflowStep(
            name="submit_form",
            description="Submit the form",
            task=self._generate_submit_task(),
            complexity=TaskComplexity.MODERATE,
            timeout=30.0,
            dependencies=[f"fill_section_{i}_{section.name}" for i, section in enumerate(self.form_definition.sections)]
        ))
        
        return steps

    async def fill_form(self, form_data: Dict[str, Any]) -> FormSubmissionResult:
        """
        Fill and submit a form with provided data.
        
        Args:
            form_data: Dictionary of field names to values
            
        Returns:
            Form submission result
        """
        self.logger.info(f"Filling form: {self.form_definition.name}")
        
        # Store form data
        self.form_data = form_data.copy()
        
        # Validate form data
        validation_errors = self.validator.validate_form_data(self.form_definition, form_data)
        if validation_errors:
            self.validation_errors = validation_errors
            if not self.config.continue_on_error:
                return FormSubmissionResult(
                    success=False,
                    form_name=self.form_definition.name,
                    submitted_data=form_data,
                    errors=validation_errors
                )
        
        # Execute the workflow
        try:
            workflow_result = await self.execute()
            
            return FormSubmissionResult(
                success=workflow_result.status.value == "completed",
                form_name=self.form_definition.name,
                submitted_data=form_data,
                errors=workflow_result.errors,
                response_data=workflow_result.results
            )
            
        except Exception as e:
            return FormSubmissionResult(
                success=False,
                form_name=self.form_definition.name,
                submitted_data=form_data,
                errors=[str(e)]
            )

    async def fill_field(
        self,
        field: FormField,
        value: Any,
        validate: bool = True
    ) -> bool:
        """
        Fill a single form field.
        
        Args:
            field: Form field definition
            value: Value to fill
            validate: Whether to validate the value
            
        Returns:
            True if field was filled successfully
        """
        self.logger.info(f"Filling field: {field.name}")
        
        # Validate field value if requested
        if validate:
            errors = self.validator.validate_field(field, value)
            if errors:
                self.logger.error(f"Field validation failed: {errors}")
                return False
        
        # Generate field-specific task
        task = self._generate_field_task(field, value)
        
        step = WorkflowStep(
            name=f"fill_field_{field.name}",
            description=f"Fill field: {field.label or field.name}",
            task=task,
            complexity=TaskComplexity.SIMPLE,
            timeout=15.0
        )
        
        try:
            await self._execute_single_step(step)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to fill field {field.name}: {e}")
            return False

    def _generate_section_task(self, section: FormSection) -> str:
        """Generate task description for filling a form section."""
        task_parts = [
            f"Fill the form section: {section.title or section.name}"
        ]
        
        if section.description:
            task_parts.append(f"Section description: {section.description}")
        
        task_parts.append("Fill the following fields:")
        
        for field in section.fields:
            value = self.form_data.get(field.name, "")
            field_desc = f"- {field.label or field.name}"
            
            if field.field_type == FieldType.TEXT:
                field_desc += f": Enter '{value}'"
            elif field.field_type == FieldType.EMAIL:
                field_desc += f": Enter email '{value}'"
            elif field.field_type == FieldType.PASSWORD:
                field_desc += f": Enter password (value provided)"
            elif field.field_type == FieldType.SELECT:
                field_desc += f": Select '{value}'"
            elif field.field_type == FieldType.CHECKBOX:
                field_desc += f": {'Check' if value else 'Uncheck'} the checkbox"
            elif field.field_type == FieldType.RADIO:
                field_desc += f": Select radio option '{value}'"
            elif field.field_type == FieldType.TEXTAREA:
                field_desc += f": Enter text '{value}'"
            elif field.field_type == FieldType.FILE:
                field_desc += f": Upload file '{value}'"
            else:
                field_desc += f": Enter '{value}'"
            
            if field.required:
                field_desc += " (required)"
            
            task_parts.append(field_desc)
        
        return "\n".join(task_parts)

    def _generate_field_task(self, field: FormField, value: Any) -> str:
        """Generate task description for filling a single field."""
        field_label = field.label or field.name
        
        if field.field_type == FieldType.TEXT:
            return f"Enter '{value}' in the {field_label} text field"
        elif field.field_type == FieldType.EMAIL:
            return f"Enter the email address '{value}' in the {field_label} field"
        elif field.field_type == FieldType.PASSWORD:
            return f"Enter the password in the {field_label} field"
        elif field.field_type == FieldType.NUMBER:
            return f"Enter the number '{value}' in the {field_label} field"
        elif field.field_type == FieldType.PHONE:
            return f"Enter the phone number '{value}' in the {field_label} field"
        elif field.field_type == FieldType.URL:
            return f"Enter the URL '{value}' in the {field_label} field"
        elif field.field_type == FieldType.DATE:
            return f"Select the date '{value}' in the {field_label} date picker"
        elif field.field_type == FieldType.TIME:
            return f"Select the time '{value}' in the {field_label} time picker"
        elif field.field_type == FieldType.TEXTAREA:
            return f"Enter the following text in the {field_label} text area: {value}"
        elif field.field_type == FieldType.SELECT:
            return f"Select '{value}' from the {field_label} dropdown"
        elif field.field_type == FieldType.MULTISELECT:
            options = value if isinstance(value, list) else [value]
            return f"Select the following options from the {field_label} multi-select: {', '.join(options)}"
        elif field.field_type == FieldType.CHECKBOX:
            action = "Check" if value else "Uncheck"
            return f"{action} the {field_label} checkbox"
        elif field.field_type == FieldType.RADIO:
            return f"Select the '{value}' option from the {field_label} radio buttons"
        elif field.field_type == FieldType.FILE:
            return f"Upload the file '{value}' using the {field_label} file input"
        else:
            return f"Fill the {field_label} field with '{value}'"

    def _generate_submit_task(self) -> str:
        """Generate task description for form submission."""
        task_parts = [
            f"Submit the {self.form_definition.name} form"
        ]
        
        if self.form_definition.submit_button_selector:
            task_parts.append(f"Click the submit button (selector: {self.form_definition.submit_button_selector})")
        else:
            task_parts.append("Click the submit button to submit the form")
        
        if self.form_definition.success_indicators:
            task_parts.append("Wait for form submission confirmation or success message")
        
        if self.form_definition.error_indicators:
            task_parts.append("Check for any error messages and report them")
        
        return "\n".join(task_parts)

    def get_field_by_name(self, field_name: str) -> Optional[FormField]:
        """Get a form field by name."""
        for section in self.form_definition.sections:
            for field in section.fields:
                if field.name == field_name:
                    return field
        return None

    def get_section_by_name(self, section_name: str) -> Optional[FormSection]:
        """Get a form section by name."""
        for section in self.form_definition.sections:
            if section.name == section_name:
                return section
        return None

    def add_custom_validation(
        self,
        field_name: str,
        validator_func: Callable[[FormField, Any], List[str]]
    ):
        """Add custom validation to a field."""
        field = self.get_field_by_name(field_name)
        if field:
            field.validation_rules.append(ValidationRule.CUSTOM)
            field.validation_params['custom_validator'] = validator_func


# Utility functions for creating common form definitions

def create_contact_form() -> FormDefinition:
    """Create a standard contact form definition."""
    return FormDefinition(
        name="contact_form",
        title="Contact Form",
        sections=[
            FormSection(
                name="personal_info",
                title="Personal Information",
                fields=[
                    FormField(
                        name="first_name",
                        field_type=FieldType.TEXT,
                        label="First Name",
                        required=True,
                        validation_rules=[ValidationRule.REQUIRED, ValidationRule.MIN_LENGTH],
                        validation_params={"min_length": 2}
                    ),
                    FormField(
                        name="last_name",
                        field_type=FieldType.TEXT,
                        label="Last Name",
                        required=True,
                        validation_rules=[ValidationRule.REQUIRED, ValidationRule.MIN_LENGTH],
                        validation_params={"min_length": 2}
                    ),
                    FormField(
                        name="email",
                        field_type=FieldType.EMAIL,
                        label="Email Address",
                        required=True,
                        validation_rules=[ValidationRule.REQUIRED, ValidationRule.EMAIL_FORMAT]
                    ),
                    FormField(
                        name="phone",
                        field_type=FieldType.PHONE,
                        label="Phone Number",
                        validation_rules=[ValidationRule.PHONE_FORMAT]
                    )
                ]
            ),
            FormSection(
                name="message",
                title="Message",
                fields=[
                    FormField(
                        name="subject",
                        field_type=FieldType.TEXT,
                        label="Subject",
                        required=True,
                        validation_rules=[ValidationRule.REQUIRED]
                    ),
                    FormField(
                        name="message",
                        field_type=FieldType.TEXTAREA,
                        label="Message",
                        required=True,
                        validation_rules=[ValidationRule.REQUIRED, ValidationRule.MIN_LENGTH],
                        validation_params={"min_length": 10}
                    )
                ]
            )
        ]
    )


def create_registration_form() -> FormDefinition:
    """Create a standard user registration form definition."""
    return FormDefinition(
        name="registration_form",
        title="User Registration",
        sections=[
            FormSection(
                name="account_info",
                title="Account Information",
                fields=[
                    FormField(
                        name="username",
                        field_type=FieldType.TEXT,
                        label="Username",
                        required=True,
                        validation_rules=[ValidationRule.REQUIRED, ValidationRule.MIN_LENGTH],
                        validation_params={"min_length": 3}
                    ),
                    FormField(
                        name="email",
                        field_type=FieldType.EMAIL,
                        label="Email Address",
                        required=True,
                        validation_rules=[ValidationRule.REQUIRED, ValidationRule.EMAIL_FORMAT]
                    ),
                    FormField(
                        name="password",
                        field_type=FieldType.PASSWORD,
                        label="Password",
                        required=True,
                        validation_rules=[ValidationRule.REQUIRED, ValidationRule.MIN_LENGTH],
                        validation_params={"min_length": 8}
                    ),
                    FormField(
                        name="confirm_password",
                        field_type=FieldType.PASSWORD,
                        label="Confirm Password",
                        required=True,
                        validation_rules=[ValidationRule.REQUIRED]
                    )
                ]
            ),
            FormSection(
                name="terms",
                title="Terms and Conditions",
                fields=[
                    FormField(
                        name="agree_terms",
                        field_type=FieldType.CHECKBOX,
                        label="I agree to the terms and conditions",
                        required=True,
                        validation_rules=[ValidationRule.REQUIRED]
                    )
                ]
            )
        ]
    )