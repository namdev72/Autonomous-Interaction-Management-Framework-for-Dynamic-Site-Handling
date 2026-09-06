from pydantic import BaseModel, Field
from typing import Optional, Literal

class AgentAction(BaseModel):
    """
    Represents an action decided by the LLM agent.
    """
    action: Literal["click", "type", "scroll", "wait", "navigate", "extract", "back", "done", "hover", "drag_to", "press_key", "select"] = Field(
        description="The type of action to perform."
    )
    
    # Target can be a playwright_index, an ID, or a descriptive semantic selector
    target: Optional[str] = Field(
        default=None, 
        description="The target element to act on. Prefer using the numeric 'playwright_index' if available."
    )
    
    value: Optional[str] = Field(
        default=None, 
        description="The value to type or URL to navigate to, or information to extract."
    )
    
    reasoning: Optional[str] = Field(
        default=None, 
        description="A brief reasoning for why this action was chosen based on the current context."
    )
    
    fallback_to_vision: Optional[bool] = Field(
        default=False,
        description="Set to true if the target is not in the DOM and you need a screenshot vision fallback."
    )
    
    x: Optional[int] = Field(default=None, description="X coordinate for vision-based click.")
    y: Optional[int] = Field(default=None, description="Y coordinate for vision-based click.")
