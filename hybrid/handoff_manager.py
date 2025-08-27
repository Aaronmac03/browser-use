"""
HandoffManager - Routes between local and cloud processing.

Maintains history and handles escalation logic.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from .schemas import (
    VisionState, Action, HistoryItem, PlannerRequest, PlannerResponse
)
from .vision_state_builder import VisionStateBuilder
from .local_action_heuristics import LocalActionHeuristics
from .cloud_planner_client import CloudPlannerClient

logger = logging.getLogger(__name__)


class HandoffManager:
    """Manages the handoff between local and cloud processing"""
    
    def __init__(
        self,
        vision_builder: VisionStateBuilder,
        local_heuristics: LocalActionHeuristics,
        cloud_client: CloudPlannerClient,
        max_history_items: int = 20,
        consecutive_failure_threshold: int = 2,
        cloud_backoff_minutes: int = 5
    ):
        self.vision_builder = vision_builder
        self.local_heuristics = local_heuristics
        self.cloud_client = cloud_client
        self.max_history_items = max_history_items
        self.consecutive_failure_threshold = consecutive_failure_threshold
        self.cloud_backoff_minutes = cloud_backoff_minutes
        
        # State tracking
        self.history: List[HistoryItem] = []
        self.consecutive_failures = 0
        self.last_cloud_call: Optional[datetime] = None
        self.current_vision_state: Optional[VisionState] = None
        self.pending_cloud_plan: List[Action] = []
        self.cloud_plan_index = 0
    
    async def process_intent(
        self,
        intent: str,
        screenshot_data: bytes,
        url: str,
        title: str,
        viewport_dims: tuple = (1280, 720),
        scroll_y: int = 0
    ) -> tuple[Action, str, bool]:
        """
        Process user intent and return next action.
        
        Returns:
            (action, reasoning, used_cloud)
        """
        
        # Step 1: Build current vision state
        self.current_vision_state = await self.vision_builder.build_vision_state(
            screenshot_data, url, title, viewport_dims, scroll_y
        )
        
        # Step 2: Check if we have a pending cloud plan to execute
        if self.pending_cloud_plan and self.cloud_plan_index < len(self.pending_cloud_plan):
            action = self.pending_cloud_plan[self.cloud_plan_index]
            self.cloud_plan_index += 1
            
            return action, f"Executing step {self.cloud_plan_index}/{len(self.pending_cloud_plan)} of cloud plan", True
        
        # Step 3: Try local processing first
        can_handle_locally, local_action, local_reason = self.local_heuristics.can_handle_locally(
            intent, self.current_vision_state
        )
        
        # Step 4: Decide whether to use local or escalate to cloud
        should_escalate = self._should_escalate_to_cloud(can_handle_locally, local_reason)
        
        if not should_escalate and can_handle_locally:
            logger.info(f"Handling locally: {local_reason}")
            return local_action, f"Local: {local_reason}", False
        
        # Step 5: Escalate to cloud
        logger.info(f"Escalating to cloud: {local_reason}")
        cloud_response = await self._get_cloud_plan(intent)
        
        if cloud_response.plan:
            # Start executing the cloud plan
            self.pending_cloud_plan = cloud_response.plan
            self.cloud_plan_index = 1  # We'll return the first action now
            
            first_action = cloud_response.plan[0]
            return first_action, f"Cloud: {cloud_response.reasoning_summary}", True
        else:
            # Cloud planning failed, return a fallback or the local action if available
            if can_handle_locally:
                return local_action, f"Cloud failed, using local: {local_reason}", False
            else:
                # Create a wait action as fallback
                wait_action = Action(
                    op="wait",
                    value="1000",
                    notes="Fallback wait due to planning failure"
                )
                return wait_action, "Both local and cloud planning failed", True
    
    def record_action_result(
        self,
        action: Action,
        result: str,
        summary: str
    ):
        """Record the result of an executed action"""
        
        history_item = HistoryItem(
            action=action,
            result="ok" if result.lower() in ["ok", "success", "completed"] else "fail",
            summary=summary
        )
        
        # Add to history
        self.history.append(history_item)
        
        # Trim history if too long
        if len(self.history) > self.max_history_items:
            self.history = self.history[-self.max_history_items:]
        
        # Update failure tracking
        if history_item.result == "fail":
            self.consecutive_failures += 1
            logger.warning(f"Action failed: {summary} (consecutive failures: {self.consecutive_failures})")
        else:
            self.consecutive_failures = 0
        
        # Clear cloud plan if we had a failure during cloud execution
        if history_item.result == "fail" and self.pending_cloud_plan:
            logger.info("Clearing cloud plan due to failure")
            self.pending_cloud_plan = []
            self.cloud_plan_index = 0
    
    def _should_escalate_to_cloud(self, can_handle_locally: bool, local_reason: str) -> bool:
        """Determine if we should escalate to cloud reasoning"""
        
        # Always escalate if local can't handle
        if not can_handle_locally:
            return True
        
        # Escalate if we have consecutive failures
        if self.consecutive_failures >= self.consecutive_failure_threshold:
            logger.info(f"Escalating due to {self.consecutive_failures} consecutive failures")
            return True
        
        # Escalate if local confidence is low (based on reason text)
        if "low confidence" in local_reason.lower() or "ambiguous" in local_reason.lower():
            return True
        
        # Check if we're in cloud backoff period
        if self.last_cloud_call:
            time_since_cloud = datetime.now() - self.last_cloud_call
            if time_since_cloud < timedelta(minutes=self.cloud_backoff_minutes):
                logger.info("In cloud backoff period, preferring local")
                return False
        
        return False
    
    async def _get_cloud_plan(self, intent: str) -> PlannerResponse:
        """Get planning response from cloud"""
        
        try:
            # Update cloud call timestamp
            self.last_cloud_call = datetime.now()
            
            # Create planner request
            request = PlannerRequest(
                task=intent,
                history=self.history.copy(),  # Send copy of history
                vision=self.current_vision_state,
                constraints={
                    "max_actions": 5,
                    "avoid": ["login if already logged in", "duplicate actions"]
                }
            )
            
            # Get response from cloud
            response = await self.cloud_client.plan_actions(request)
            
            # Reset consecutive failures after successful cloud call
            if response.plan:
                self.consecutive_failures = 0
            
            return response
            
        except Exception as e:
            logger.error(f"Cloud planning failed: {e}")
            return PlannerResponse(
                plan=[],
                reasoning_summary=f"Cloud error: {str(e)}",
                needs_more_context=True
            )
    
    def get_current_state_summary(self) -> Dict[str, Any]:
        """Get summary of current state for debugging/monitoring"""
        
        return {
            "consecutive_failures": self.consecutive_failures,
            "history_length": len(self.history),
            "has_pending_plan": bool(self.pending_cloud_plan),
            "cloud_plan_progress": f"{self.cloud_plan_index}/{len(self.pending_cloud_plan)}" if self.pending_cloud_plan else None,
            "last_cloud_call": self.last_cloud_call.isoformat() if self.last_cloud_call else None,
            "current_url": self.current_vision_state.meta.url if self.current_vision_state else None,
            "elements_detected": len(self.current_vision_state.elements) if self.current_vision_state else 0,
            "recent_actions": [
                f"{h.action.op} -> {h.result}"
                for h in self.history[-3:]
            ] if self.history else []
        }