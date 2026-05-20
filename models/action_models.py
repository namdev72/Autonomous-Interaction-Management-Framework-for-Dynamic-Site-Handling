from pydantic import BaseModel, Field
from typing import Optional, Literal

class AgentAction(BaseModel):
    """
    Represents an action decided by the LLM agent.
    """
    action: Literal["click", "type", "scroll", "wait", "navigate", "extract", "back", "done"] = Field(
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
