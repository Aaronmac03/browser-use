"""
Workflows package for browser-agent.

This package contains workflow implementations for browser automation tasks,
including base workflow classes and specific task workflows.
"""

from .workflow_base import (
    BaseWorkflow,
    WorkflowConfig,
    WorkflowStep,
    WorkflowResult,
    WorkflowStatus,
    WorkflowPriority,
    SecurityError,
    WorkflowTimeoutError,
    WorkflowDependencyError
)

# Note: email_calendar module imports are handled separately to avoid circular imports

__all__ = [
    # Base workflow classes
    "BaseWorkflow",
    "WorkflowConfig", 
    "WorkflowStep",
    "WorkflowResult",
    "WorkflowStatus",
    "WorkflowPriority",
    
    # Exceptions
    "SecurityError",
    "WorkflowTimeoutError", 
    "WorkflowDependencyError"
]