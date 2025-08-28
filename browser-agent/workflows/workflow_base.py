"""
Base workflow class for browser automation tasks.

This module provides the abstract base class for all browser automation workflows,
defining the common interface, lifecycle methods, and error handling mechanisms.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from pydantic import BaseModel, Field

from browser_use import Agent
from browser_use.llm import ChatOpenAI, ChatAnthropic, ChatGoogle, ChatOllama
from config.models import TaskComplexity, ModelProvider, ModelConfig
from models.model_router import ModelRouter, TaskRequirements
from config.profiles import BrowserProfileManager
from utils.security import SecurityManager


class WorkflowStatus(str, Enum):
    """Workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class WorkflowPriority(str, Enum):
    """Workflow execution priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class WorkflowStep:
    """Individual step in a workflow."""
    name: str
    description: str
    task: str
    complexity: TaskComplexity = TaskComplexity.MODERATE
    requires_vision: bool = False
    requires_code: bool = False
    timeout: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowResult:
    """Result of workflow execution."""
    workflow_id: str
    status: WorkflowStatus
    steps_completed: int
    total_steps: int
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[timedelta] = None
    results: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkflowConfig(BaseModel):
    """Configuration for workflow execution."""
    workflow_id: str = Field(description="Unique workflow identifier")
    name: str = Field(description="Human-readable workflow name")
    description: str = Field(description="Workflow description")
    priority: WorkflowPriority = Field(default=WorkflowPriority.NORMAL)
    timeout: Optional[float] = Field(default=None, description="Overall workflow timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts for failed steps")
    browser_profile: str = Field(default="default", description="Browser profile to use")
    security_level: str = Field(default="medium", description="Security level for URL validation")
    parallel_execution: bool = Field(default=False, description="Allow parallel step execution")
    continue_on_error: bool = Field(default=False, description="Continue workflow on step failure")
    save_screenshots: bool = Field(default=True, description="Save screenshots during execution")
    save_results: bool = Field(default=True, description="Save workflow results")


def create_browser_use_llm(model_config: ModelConfig):
    """
    Convert a ModelConfig to a browser-use LLM instance.
    
    Args:
        model_config: Our internal model configuration
        
    Returns:
        Browser-use LLM instance
    """
    # Get API key from environment or credentials
    import os
    
    if model_config.provider == ModelProvider.OPENAI:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        return ChatOpenAI(
            model=model_config.model_id,
            api_key=api_key,
            temperature=model_config.temperature,
            max_tokens=model_config.max_tokens,
            timeout=model_config.timeout
        )
    
    elif model_config.provider == ModelProvider.ANTHROPIC:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        return ChatAnthropic(
            model=model_config.model_id,
            api_key=api_key,
            temperature=model_config.temperature,
            max_tokens=model_config.max_tokens,
            timeout=model_config.timeout
        )
    
    elif model_config.provider == ModelProvider.GOOGLE:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")
        return ChatGoogle(
            model=model_config.model_id,
            api_key=api_key,
            temperature=model_config.temperature,
            max_tokens=model_config.max_tokens,
            timeout=model_config.timeout
        )
    
    elif model_config.provider == ModelProvider.OLLAMA:
        return ChatOllama(
            model=model_config.model_id,
            temperature=model_config.temperature,
            timeout=model_config.timeout
        )
    
    else:
        raise ValueError(f"Unsupported model provider: {model_config.provider}")


class BaseWorkflow(ABC):
    """
    Abstract base class for browser automation workflows.
    
    This class provides the common interface and lifecycle methods for all workflows,
    including error handling, recovery mechanisms, and result management.
    """
    
    def __init__(
        self,
        config: WorkflowConfig,
        model_router: ModelRouter,
        profile_manager: BrowserProfileManager,
        security_manager: SecurityManager
    ):
        """
        Initialize the base workflow.
        
        Args:
            config: Workflow configuration
            model_router: Model router for intelligent model selection
            profile_manager: Browser profile manager
            security_manager: Security manager for URL validation
        """
        self.config = config
        self.model_router = model_router
        self.profile_manager = profile_manager
        self.security_manager = security_manager
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Workflow state
        self.status = WorkflowStatus.PENDING
        self.steps: List[WorkflowStep] = []
        self.current_step_index = 0
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.results: Dict[str, Any] = {}
        self.errors: List[str] = []
        self.metadata: Dict[str, Any] = {}
        
        # Event handlers
        self._step_handlers: Dict[str, List[Callable]] = {
            "before_step": [],
            "after_step": [],
            "step_error": [],
            "step_retry": []
        }
        
        # Recovery mechanisms
        self._recovery_strategies: Dict[str, Callable] = {}
        self._checkpoint_data: Dict[str, Any] = {}
        
        self.logger.info(f"Initialized workflow: {config.name} ({config.workflow_id})")

    @abstractmethod
    async def define_steps(self) -> List[WorkflowStep]:
        """
        Define the workflow steps.
        
        Returns:
            List of workflow steps to execute
        """
        pass

    @abstractmethod
    async def validate_prerequisites(self) -> bool:
        """
        Validate workflow prerequisites.
        
        Returns:
            True if prerequisites are met, False otherwise
        """
        pass

    async def execute(self) -> WorkflowResult:
        """
        Execute the complete workflow.
        
        Returns:
            Workflow execution result
        """
        self.logger.info(f"Starting workflow execution: {self.config.name}")
        self.status = WorkflowStatus.RUNNING
        self.start_time = datetime.now()
        
        try:
            # Validate prerequisites
            if not await self.validate_prerequisites():
                raise RuntimeError("Workflow prerequisites not met")
            
            # Define workflow steps
            self.steps = await self.define_steps()
            if not self.steps:
                raise RuntimeError("No workflow steps defined")
            
            self.logger.info(f"Executing {len(self.steps)} workflow steps")
            
            # Execute steps
            if self.config.parallel_execution:
                await self._execute_steps_parallel()
            else:
                await self._execute_steps_sequential()
            
            self.status = WorkflowStatus.COMPLETED
            self.logger.info(f"Workflow completed successfully: {self.config.name}")
            
        except asyncio.CancelledError:
            self.status = WorkflowStatus.CANCELLED
            self.logger.warning(f"Workflow cancelled: {self.config.name}")
            raise
            
        except Exception as e:
            self.status = WorkflowStatus.FAILED
            error_msg = f"Workflow failed: {str(e)}"
            self.errors.append(error_msg)
            self.logger.error(error_msg, exc_info=True)
            
            if not self.config.continue_on_error:
                raise
        
        finally:
            self.end_time = datetime.now()
            
            # Save results if configured
            if self.config.save_results:
                await self._save_workflow_results()
        
        return self._create_workflow_result()

    async def _execute_steps_sequential(self):
        """Execute workflow steps sequentially."""
        for i, step in enumerate(self.steps):
            self.current_step_index = i
            
            # Check dependencies
            if not await self._check_step_dependencies(step):
                error_msg = f"Step dependencies not met: {step.name}"
                self.errors.append(error_msg)
                if not self.config.continue_on_error:
                    raise RuntimeError(error_msg)
                continue
            
            # Execute step with retry logic
            await self._execute_step_with_retry(step)

    async def _execute_steps_parallel(self):
        """Execute workflow steps in parallel where possible."""
        # Build dependency graph
        dependency_graph = self._build_dependency_graph()
        
        # Execute steps in dependency order
        executed_steps = set()
        
        while len(executed_steps) < len(self.steps):
            # Find steps ready to execute
            ready_steps = []
            for step in self.steps:
                if step.name not in executed_steps:
                    if all(dep in executed_steps for dep in step.dependencies):
                        ready_steps.append(step)
            
            if not ready_steps:
                raise RuntimeError("Circular dependency detected in workflow steps")
            
            # Execute ready steps in parallel
            tasks = [self._execute_step_with_retry(step) for step in ready_steps]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Mark steps as executed
            for step in ready_steps:
                executed_steps.add(step.name)

    async def _execute_step_with_retry(self, step: WorkflowStep):
        """Execute a single step with retry logic."""
        for attempt in range(step.max_retries + 1):
            try:
                self.logger.info(f"Executing step: {step.name} (attempt {attempt + 1})")
                
                # Call before_step handlers
                await self._call_event_handlers("before_step", step)
                
                # Create checkpoint before step execution
                await self._create_checkpoint(step.name)
                
                # Execute the step
                step_result = await self._execute_single_step(step)
                
                # Store step result
                self.results[step.name] = step_result
                
                # Call after_step handlers
                await self._call_event_handlers("after_step", step, step_result)
                
                self.logger.info(f"Step completed successfully: {step.name}")
                return step_result
                
            except Exception as e:
                step.retry_count = attempt + 1
                error_msg = f"Step failed: {step.name} - {str(e)}"
                self.logger.warning(error_msg)
                
                # Call step_error handlers
                await self._call_event_handlers("step_error", step, e)
                
                if attempt < step.max_retries:
                    # Try recovery strategy
                    if await self._try_recovery(step, e):
                        continue
                    
                    # Call step_retry handlers
                    await self._call_event_handlers("step_retry", step, attempt + 1)
                    
                    # Wait before retry
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    # Max retries reached
                    self.errors.append(error_msg)
                    if not self.config.continue_on_error:
                        raise
                    break

    async def _execute_single_step(self, step: WorkflowStep) -> Any:
        """
        Execute a single workflow step.
        
        Args:
            step: The workflow step to execute
            
        Returns:
            Step execution result
        """
        # Validate URLs in the task
        await self._validate_step_security(step)
        
        # Select appropriate model for the step
        task_requirements = TaskRequirements(
            complexity=step.complexity,
            requires_vision=step.requires_vision,
            requires_code=step.requires_code,
            max_response_time=step.timeout
        )
        
        model_config = await self.model_router.select_model(task_requirements)
        
        # Convert to browser-use LLM instance
        llm = create_browser_use_llm(model_config)
        
        # Get browser configuration
        browser_config = self.profile_manager.get_browser_config(self.config.browser_profile)
        
        # Create and configure agent
        agent = Agent(
            task=step.task,
            llm=llm,
            **browser_config
        )
        
        # Execute the step with timeout
        if step.timeout:
            result = await asyncio.wait_for(agent.run(), timeout=step.timeout)
        else:
            result = await agent.run()
        
        return result

    async def _validate_step_security(self, step: WorkflowStep):
        """Validate security for a workflow step."""
        # Extract URLs from task description (basic implementation)
        import re
        urls = re.findall(r'https?://[^\s]+', step.task)
        
        for url in urls:
            validation = self.security_manager.validate_and_log_url_access(
                url,
                user_id=f"workflow_{self.config.workflow_id}",
                session_id=f"step_{step.name}"
            )
            
            if validation["recommendation"] == "BLOCK":
                raise SecurityError(f"URL blocked by security policy: {url}")

    async def _check_step_dependencies(self, step: WorkflowStep) -> bool:
        """Check if step dependencies are satisfied."""
        for dep in step.dependencies:
            if dep not in self.results:
                return False
        return True

    def _build_dependency_graph(self) -> Dict[str, List[str]]:
        """Build dependency graph for parallel execution."""
        graph = {}
        for step in self.steps:
            graph[step.name] = step.dependencies.copy()
        return graph

    async def _create_checkpoint(self, step_name: str):
        """Create a checkpoint before step execution."""
        self._checkpoint_data[step_name] = {
            "timestamp": datetime.now(),
            "results": self.results.copy(),
            "current_step": self.current_step_index,
            "metadata": self.metadata.copy()
        }

    async def _try_recovery(self, step: WorkflowStep, error: Exception) -> bool:
        """Try to recover from step failure."""
        recovery_strategy = self._recovery_strategies.get(step.name)
        if recovery_strategy:
            try:
                self.logger.info(f"Attempting recovery for step: {step.name}")
                await recovery_strategy(step, error)
                return True
            except Exception as recovery_error:
                self.logger.warning(f"Recovery failed for step {step.name}: {recovery_error}")
        
        return False

    async def _call_event_handlers(self, event: str, *args):
        """Call registered event handlers."""
        handlers = self._step_handlers.get(event, [])
        for handler in handlers:
            try:
                await handler(*args)
            except Exception as e:
                self.logger.warning(f"Event handler failed for {event}: {e}")

    def register_step_handler(self, event: str, handler: Callable):
        """Register an event handler for workflow steps."""
        if event in self._step_handlers:
            self._step_handlers[event].append(handler)

    def register_recovery_strategy(self, step_name: str, strategy: Callable):
        """Register a recovery strategy for a specific step."""
        self._recovery_strategies[step_name] = strategy

    async def _save_workflow_results(self):
        """Save workflow results to storage."""
        # Implementation would depend on storage backend
        # For now, just log the results
        self.logger.info(f"Workflow results: {len(self.results)} steps completed")

    def _create_workflow_result(self) -> WorkflowResult:
        """Create workflow result object."""
        duration = None
        if self.start_time and self.end_time:
            duration = self.end_time - self.start_time
        
        return WorkflowResult(
            workflow_id=self.config.workflow_id,
            status=self.status,
            steps_completed=len(self.results),
            total_steps=len(self.steps),
            start_time=self.start_time or datetime.now(),
            end_time=self.end_time,
            duration=duration,
            results=self.results,
            errors=self.errors,
            metadata=self.metadata
        )

    def get_step_result(self, step_name: str) -> Optional[Any]:
        """Get result from a specific step."""
        return self.results.get(step_name)

    def get_checkpoint(self, step_name: str) -> Optional[Dict[str, Any]]:
        """Get checkpoint data for a specific step."""
        return self._checkpoint_data.get(step_name)

    async def cancel(self):
        """Cancel workflow execution."""
        self.status = WorkflowStatus.CANCELLED
        self.logger.info(f"Workflow cancelled: {self.config.name}")

    def get_progress(self) -> Dict[str, Any]:
        """Get current workflow progress."""
        return {
            "workflow_id": self.config.workflow_id,
            "status": self.status.value,
            "current_step": self.current_step_index,
            "total_steps": len(self.steps),
            "progress_percentage": (len(self.results) / len(self.steps) * 100) if self.steps else 0,
            "steps_completed": len(self.results),
            "errors_count": len(self.errors),
            "duration": (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        }


class SecurityError(Exception):
    """Security-related workflow error."""
    pass


class WorkflowTimeoutError(Exception):
    """Workflow timeout error."""
    pass


class WorkflowDependencyError(Exception):
    """Workflow dependency error."""
    pass