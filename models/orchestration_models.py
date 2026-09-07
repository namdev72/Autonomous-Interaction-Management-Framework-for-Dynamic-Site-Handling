from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .action_models import AgentAction


class ActionResult(BaseModel):
    """Structured result returned by every browser action."""

    success: bool
    action: str
    step_id: Optional[str] = None
    target: Optional[str] = None
    value: Optional[Any] = None
    error: Optional[str] = None
    recovery_hint: Optional[str] = None
    url_before: Optional[str] = None
    url_after: Optional[str] = None
    screenshot_path: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentState(BaseModel):
    """Snapshot of one reasoning iteration."""

    user_query: str
    iteration: int
    current_url: str
    page_key: Optional[str] = None
    view_signature: Optional[str] = None
    # Kept so a step can record what its pw-id target actually was. Indices do
    # not survive to the next run; the element's descriptor does.
    elements: List[Dict[str, Any]] = Field(default_factory=list)
    page_context: str
    memory_context: str
    # What memory recalled about this page, already rendered for the prompt.
    recalled_context: str = ""
    semantic_memory: List[str] = Field(default_factory=list)
    last_action: Optional[AgentAction] = None
    last_result: Optional[ActionResult] = None


class StepDecision(BaseModel):
    """LLM action plus orchestration metadata."""

    action: AgentAction
    source: str = "llm"
    needs_verification: bool = False


class AgentRunResult(BaseModel):
    """Final summary returned by ReasoningAgent.execute_task."""

    completed: bool
    iterations: int
    reason: str
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    last_url: Optional[str] = None
