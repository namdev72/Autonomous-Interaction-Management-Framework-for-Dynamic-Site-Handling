from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict

class GoalRequirement(BaseModel):
    id: str
    type: str = Field(description="content | page | navigation | state | interaction | extraction | download | comparison | form | custom")
    description: str
    required: bool = True
    status: str = "unknown" # achieved, not_achieved, unknown

class GoalContract(BaseModel):
    task_id: str
    intent: str
    source: Dict[str, str] = Field(default_factory=dict)
    requirements: List[GoalRequirement] = Field(default_factory=list)
    optional_requirements: List[GoalRequirement] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    
class VerificationResult(BaseModel):
    status: str = Field(description="ACHIEVED | NOT_ACHIEVED | UNKNOWN")
    requirements: List[GoalRequirement] = Field(default_factory=list)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0

class ObservedState(BaseModel):
    url: str
    title: str
    page_type: Optional[str] = None
    headings: List[str] = Field(default_factory=list)
    visible_text: List[str] = Field(default_factory=list)
    forms: List[Dict[str, Any]] = Field(default_factory=list)
    scroll_y: int = 0
    selected_states: List[Dict[str, Any]] = Field(default_factory=list)
    checked_states: List[Dict[str, Any]] = Field(default_factory=list)
    links: List[Dict[str, str]] = Field(default_factory=list)
    relevant_content: List[str] = Field(default_factory=list)
