"""
Data contracts and schemas for the hybrid vision system.
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class ElementInfo(BaseModel):
    """Individual UI element information"""
    role: Literal["button", "link", "text", "image", "input", "other"]
    visible_text: str
    attributes: Dict[str, Any] = Field(default_factory=dict)
    selector_hint: str
    bbox: List[int] = Field(description="[x, y, width, height]")
    confidence: float = Field(ge=0.0, le=1.0)


class FieldInfo(BaseModel):
    """Form field information"""
    name_hint: str
    value_hint: str = ""
    bbox: List[int] = Field(description="[x, y, width, height]")
    editable: bool = True


class AffordanceInfo(BaseModel):
    """Interactive affordance information"""
    type: Literal["button", "link", "tab", "menu", "icon"]
    label: str
    selector_hint: str
    bbox: List[int] = Field(description="[x, y, width, height]")


class PageMeta(BaseModel):
    """Page metadata"""
    url: str
    title: str
    scrollY: int = 0
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class VisionState(BaseModel):
    """Complete vision state from local VLM"""
    caption: str = Field(max_length=200)
    elements: List[ElementInfo] = Field(default_factory=list)
    fields: List[FieldInfo] = Field(default_factory=list) 
    affordances: List[AffordanceInfo] = Field(default_factory=list)
    meta: PageMeta


class ActionTarget(BaseModel):
    """Action target specification"""
    selector_hint: str
    text: Optional[str] = None


class Action(BaseModel):
    """Action specification for both local and cloud"""
    op: Literal["click", "type", "scroll", "navigate", "wait", "select", "hover"]
    target: Optional[ActionTarget] = None
    value: Optional[str] = None
    notes: Optional[str] = None


class HistoryItem(BaseModel):
    """History item for tracking actions"""
    action: Action
    result: Literal["ok", "fail"]
    summary: str


class PlannerRequest(BaseModel):
    """Request to cloud planner"""
    task: str
    history: List[HistoryItem] = Field(default_factory=list)
    vision: VisionState
    constraints: Dict[str, Any] = Field(default_factory=dict)


class PlannerResponse(BaseModel):
    """Response from cloud planner"""
    plan: List[Action]
    reasoning_summary: str = Field(max_length=300)
    needs_more_context: bool = False